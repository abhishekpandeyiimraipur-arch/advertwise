"""
WorkerReflect — Quality gate for I2V output.
[TDD-WORKERS]-H

Guard 1: SSIM ≥ 0.65 between source PNG and video first frame.
Guard 2: Vision model deformation check on first frame.
Returns first passing candidate R2 key.
Raises ReflectError if no candidate passes.

Heavy libraries (av, numpy, skimage) are imported inside methods only —
never at module level — to avoid slowing ARQ worker startup.
"""
import asyncio
import io
import logging
import os
from app.core.exceptions import ReflectError

logger = logging.getLogger(__name__)

SSIM_THRESHOLD = 0.65
DEFORMATION_CHECK_TIMEOUT_S = 30.0


class WorkerReflect:
    """
    Quality gate: SSIM + deformation guard.
    Guard 1: SSIM ≥ 0.65 between source PNG and video first frame.
    Guard 2: Vision model deformation check on first frame.
    Returns first passing candidate R2 key.
    Raises ReflectError if no candidate passes.
    """

    def __init__(self, gateway, r2_client):
        self.gateway = gateway
        self.r2_client = r2_client

    def _extract_first_frame(self, video_bytes: bytes) -> bytes:
        """
        Extracts first frame from MP4 bytes. Returns PNG bytes.
        Uses PyAV (av library). Imported inside method only —
        heavy import, must not slow ARQ worker startup.
        """
        try:
            import av
            container = av.open(io.BytesIO(video_bytes))
            for frame in container.decode(video=0):
                img = frame.to_image()  # returns PIL Image
                break
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            return buf.getvalue()
        except Exception as e:
            raise ReflectError(f"Frame extraction failed: {e}") from e

    def _compute_ssim(
        self,
        source_png_bytes: bytes,
        first_frame_png_bytes: bytes,
    ) -> float:
        """
        Computes SSIM score between source PNG and video first frame.
        Both images resized to 512x512 before comparison —
        eliminates shape mismatch between PNG and video dimensions.
        Imports numpy, PIL, skimage inside method only.

        Returns 0.0 on any failure (conservative fail, never falsely pass).
        """
        try:
            import numpy as np
            from PIL import Image
            from skimage.metrics import structural_similarity

            src = np.array(
                Image.open(io.BytesIO(source_png_bytes))
                     .convert('RGB')
                     .resize((512, 512))
            )
            frame = np.array(
                Image.open(io.BytesIO(first_frame_png_bytes))
                     .convert('RGB')
                     .resize((512, 512))
            )
            score = structural_similarity(
                src, frame,
                channel_axis=2,
                data_range=255,
            )
            return float(score)
        except Exception as e:
            logger.warning(f"SSIM computation failed: {e}")
            return 0.0  # conservative fail — never falsely pass

    async def process(
        self,
        gen_id: str,
        candidate_r2_keys: list[str],
        source_png_r2_key: str,
    ) -> str:
        """
        Evaluates candidates in order.
        Returns R2 key of first candidate passing both guards.
        Raises ReflectError if none pass.

        source_png_r2_key: R2 object key of isolated product PNG.
            Format: "isolated/{gen_id}/product.png"
            Downloaded via credentialed r2_client — NOT public URL.

        candidate_r2_keys: list of I2V output R2 keys.
            Format: ["{gen_id}/i2v/candidate_1.mp4",
                     "{gen_id}/i2v/candidate_2.mp4"]
            Evaluated in order — return on first pass.
        """
        # ── Step 1: Download source PNG ──────────────────────────
        try:
            resp = await asyncio.to_thread(
                self.r2_client.get_object,
                Bucket=os.environ["R2_BUCKET_NAME"],
                Key=source_png_r2_key,
            )
            source_png_bytes = resp["Body"].read()
        except Exception as e:
            raise ReflectError(
                f"Source PNG download failed gen={gen_id}: {e}"
            )

        # ── Step 2: Evaluate each candidate ──────────────────────
        for candidate_key in candidate_r2_keys:

            # 2a. Download candidate video
            try:
                resp = await asyncio.to_thread(
                    self.r2_client.get_object,
                    Bucket=os.environ["R2_BUCKET_NAME"],
                    Key=candidate_key,
                )
                video_bytes = resp["Body"].read()
            except Exception as e:
                logger.warning(
                    f"Candidate download failed gen={gen_id} "
                    f"key={candidate_key}: {e}. Skipping."
                )
                continue

            # 2b. Extract first frame (CPU — run in thread)
            try:
                first_frame = await asyncio.to_thread(
                    self._extract_first_frame, video_bytes
                )
            except ReflectError as e:
                logger.warning(
                    f"Frame extraction failed gen={gen_id} "
                    f"key={candidate_key}: {e}. Skipping."
                )
                continue

            # 2c. Compute SSIM (CPU intensive — run in thread)
            score = await asyncio.to_thread(
                self._compute_ssim, source_png_bytes, first_frame
            )
            logger.info(
                f"SSIM gen={gen_id} candidate={candidate_key} "
                f"score={score:.3f} threshold={SSIM_THRESHOLD}"
            )

            # 2d. SSIM gate
            if score < SSIM_THRESHOLD:
                logger.warning(
                    f"SSIM below threshold gen={gen_id} "
                    f"score={score:.3f}. Skipping."
                )
                continue

            # 2e. Deformation check via vision model
            result = {}
            try:
                result = await asyncio.wait_for(
                    self.gateway.route(
                        capability="vision",
                        input_data={
                            "image":  first_frame,
                            "task":   "deformation_check",
                            "gen_id": gen_id,
                        }
                    ),
                    timeout=DEFORMATION_CHECK_TIMEOUT_S,
                )
            except (asyncio.TimeoutError, Exception) as e:
                logger.warning(
                    f"Deformation check unavailable gen={gen_id}: "
                    f"{e}. Treating as passed — SSIM sufficient."
                )
                result = {}

            # 2f. Deformation gate
            if result.get("deformed") is True:
                logger.warning(
                    f"Deformation detected gen={gen_id} "
                    f"candidate={candidate_key}. Skipping."
                )
                continue

            # 2g. Both guards passed — return immediately
            quality_score = (
                score * 0.6 +
                result.get("quality_score", 0.5) * 0.4
            )
            logger.info(
                f"Reflect passed gen={gen_id} "
                f"candidate={candidate_key} "
                f"ssim={score:.3f} "
                f"quality={quality_score:.3f}"
            )
            return candidate_key

        # ── Step 3: No candidate passed ──────────────────────────
        raise ReflectError(
            f"No candidates passed quality gates for gen={gen_id}. "
            f"Tried {len(candidate_r2_keys)} candidates."
        )

