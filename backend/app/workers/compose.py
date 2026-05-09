"""
WorkerCompose — Assembles the 15s fractional render.
[TDD-WORKERS]-H

MVP pattern: Hook(3s) + I2V(9s) + CTA(3s)
Applies LUT color grade based on product benefit.
Burns SGI watermark per IT Rules 2026.
No DB access. No state transitions.
All temp files written to /tmp/{gen_id}_*.
Cleanup runs in finally block — always executes.
"""
import asyncio
import logging
import os
import shutil
from pathlib import Path
from app.core.exceptions import ComposeError, ComposeDurationError

logger = logging.getLogger(__name__)

CANONICAL_DURATION_S = 15.0
MAX_SEGMENT_DURATION_S = 10.0

# LUT directory — relative to this file's location
# backend/app/luts/*.cube
LUT_DIR = Path(__file__).parent.parent / "luts"

BENEFIT_LUT_MAP: dict[str, str] = {
    "premium":  "premium_warm.cube",
    "trending": "trending_vivid.cube",
    "gift":     "gift_festive.cube",
    "natural":  "natural_green.cube",
}
DEFAULT_LUT = "neutral_balanced.cube"

SGI_WATERMARK_TEXT = "AI Generated Content"
SGI_WATERMARK_FILTER = (
    "drawtext=text='AI Generated Content | AdvertWise':"
    "fontsize=16:fontcolor=white@0.8:"
    "x=10:y=h-40:"
    "box=1:boxcolor=black@0.3:boxpadding=4"
)


class WorkerCompose:
    """
    Assembles the 15s fractional render.
    MVP pattern: Hook(3s) + I2V(9s) + CTA(3s)
    Applies LUT color grade based on product benefit.
    Burns SGI watermark per IT Rules 2026.
    No DB access. No state transitions.
    All temp files written to /tmp/{gen_id}_*.
    Cleanup runs in finally block — always executes.
    """

    def __init__(self, r2_client):
        self.r2_client = r2_client

    def _select_lut(self, benefit: str) -> Path:
        """
        Pure function. Maps benefit string to absolute LUT path.
        Falls back to DEFAULT_LUT for unknown benefit.
        Returns absolute Path object.
        LUT files live at backend/app/luts/*.cube
        """
        filename = BENEFIT_LUT_MAP.get(benefit, DEFAULT_LUT)
        return LUT_DIR / filename

    def _get_temp_path(self, gen_id: str, suffix: str) -> str:
        """
        Returns /tmp/{gen_id}_{suffix} string.
        e.g. _get_temp_path("abc-123", "hook.mp4")
             → "/tmp/abc-123_hook.mp4"
        """
        return f"/tmp/{gen_id}_{suffix}"

    def _cleanup_temp_files(self, paths: list[str]) -> None:
        """
        Deletes all temp files in paths list.
        Silently ignores missing files.
        Called in finally block — must never raise.
        """
        for path in paths:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception as e:
                logger.warning(f"Temp cleanup failed for {path}: {e}")

    def _build_filter_graph(
        self,
        hook_duration: float,
        i2v_duration: float,
        cta_duration: float,
        lut_path: str,
    ) -> str:
        """
        Builds FFmpeg filter_complex string for 15s composition.

        Input stream mapping:
          [0:v] = hook clip  (3s B-Roll)
          [1:v] = i2v clip   (9s AI video)
          [2:v] = cta clip   (3s B-Roll)
          [3:a] = tts audio  (variable duration)

        Filter chain:
        1. Pad + trim each video segment to exact target duration.
        2. Concat 3 segments → apply LUT → burn watermark.
        3. Trim + pad audio to exactly 15s.
        """
        # Compute pad amounts (never negative)
        hook_pad = max(0.0, 3.0 - hook_duration)
        i2v_pad  = max(0.0, 9.0 - i2v_duration)
        cta_pad  = max(0.0, 3.0 - cta_duration)

        # FFmpeg requires forward slashes even on Windows
        lut_path_fwd = str(lut_path).replace(os.sep, "/")

        fg = (
            # ── 1. Pad + trim each segment ──────────────────────
            f"[0:v]tpad=stop_mode=clone:stop_duration={hook_pad:.3f},"
            f"trim=end=3.0,setpts=PTS-STARTPTS[hook_v];"

            f"[1:v]tpad=stop_mode=clone:stop_duration={i2v_pad:.3f},"
            f"trim=end=9.0,setpts=PTS-STARTPTS[i2v_v];"

            f"[2:v]tpad=stop_mode=clone:stop_duration={cta_pad:.3f},"
            f"trim=end=3.0,setpts=PTS-STARTPTS[cta_v];"

            # ── 2. Concat 3 video streams ────────────────────────
            f"[hook_v][i2v_v][cta_v]concat=n=3:v=1:a=0[concat_v];"

            # ── 3. Apply LUT color grade ─────────────────────────
            f"[concat_v]lut3d={lut_path_fwd}[graded_v];"

            # ── 4. Burn SGI watermark (after LUT — mandatory) ────
            f"[graded_v]{SGI_WATERMARK_FILTER}[watermarked_v];"

            # ── 5. Trim + pad audio to exactly 15s ───────────────
            f"[3:a]atrim=end=15.0,apad=whole_dur=15.0[padded_a]"
        )
        return fg

    def _build_ffmpeg_cmd(
        self,
        hook_path: str,
        i2v_path: str,
        cta_path: str,
        tts_path: str,
        output_path: str,
        filter_graph: str,
    ) -> list[str]:
        """
        Builds complete FFmpeg command list for subprocess execution.
        The shortest-stream flag is explicitly excluded.
        Always includes -t 15 (explicit duration cap).
        Returns list of strings for asyncio.create_subprocess_exec.
        """
        return [
            "ffmpeg", "-y",
            "-i", hook_path,
            "-i", i2v_path,
            "-i", cta_path,
            "-i", tts_path,
            "-filter_complex", filter_graph,
            "-map", "[watermarked_v]",
            "-map", "[padded_a]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-t", "15",
            output_path,
        ]

    async def _probe_duration(self, file_path: str) -> float:
        """
        Uses ffprobe to get video/audio duration in seconds.
        Returns float duration.
        On failure → raise ComposeError.
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                "ffprobe",
                "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                file_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                raise ComposeError(
                    f"ffprobe non-zero exit for {file_path}: "
                    f"{stderr.decode().strip()}"
                )
            return float(stdout.decode().strip())
        except ComposeError:
            raise
        except Exception as e:
            raise ComposeError(f"ffprobe failed: {e}") from e

    async def process(
        self,
        gen_id: str,
        i2v_r2_key: str,
        tts_r2_key: str,
        b_roll_plan: list[dict],
        benefit: str,
        plan_tier: str,
    ) -> str:
        """
        Assembles 15s MP4: Hook(3s) + I2V(9s) + CTA(3s) + TTS audio.
        Applies LUT color grade + SGI watermark.
        Uploads result to R2. Returns R2 key string.

        b_roll_plan[0] = hook clip dict (r2_url = R2 object key)
        b_roll_plan[1] = cta clip dict  (r2_url = R2 object key)

        Raises ComposeError on any unrecoverable failure.
        Raises ComposeDurationError if segment durations out of bounds.
        Temp files always cleaned up in finally block.
        """
        # ── Temp file paths ──────────────────────────────────────
        hook_path   = self._get_temp_path(gen_id, "hook.mp4")
        i2v_path    = self._get_temp_path(gen_id, "i2v.mp4")
        cta_path    = self._get_temp_path(gen_id, "cta.mp4")
        tts_path    = self._get_temp_path(gen_id, "tts.mp3")
        output_path = self._get_temp_path(gen_id, "preview.mp4")
        temp_files  = [hook_path, i2v_path, cta_path,
                       tts_path, output_path]

        try:
            # ── Step 1: Validate b_roll_plan ─────────────────────
            if not b_roll_plan or len(b_roll_plan) < 2:
                raise ComposeError(
                    f"b_roll_plan requires 2 clips for gen={gen_id}. "
                    f"Got {len(b_roll_plan) if b_roll_plan else 0}."
                )

            hook_clip = b_roll_plan[0]
            cta_clip  = b_roll_plan[1]

            # ── Step 2: Download all 4 assets from R2 ────────────
            bucket = os.environ["R2_BUCKET_NAME"]

            async def download_and_write(
                r2_key: str, local_path: str
            ):
                resp = await asyncio.to_thread(
                    self.r2_client.get_object,
                    Bucket=bucket,
                    Key=r2_key,
                )
                data = resp["Body"].read()
                await asyncio.to_thread(
                    Path(local_path).write_bytes, data
                )

            # All 4 downloads concurrently — saves 3-4 seconds
            await asyncio.gather(
                download_and_write(hook_clip["r2_url"], hook_path),
                download_and_write(i2v_r2_key,          i2v_path),
                download_and_write(cta_clip["r2_url"],  cta_path),
                download_and_write(tts_r2_key,           tts_path),
            )
            logger.info(f"Compose assets downloaded gen={gen_id}")

            # ── Step 3: Probe durations ───────────────────────────
            hook_dur, i2v_dur, cta_dur = await asyncio.gather(
                self._probe_duration(hook_path),
                self._probe_duration(i2v_path),
                self._probe_duration(cta_path),
            )

            for name, dur in [("hook", hook_dur),
                               ("i2v",  i2v_dur),
                               ("cta",  cta_dur)]:
                if dur > MAX_SEGMENT_DURATION_S:
                    raise ComposeDurationError(
                        f"Segment {name} duration {dur:.1f}s "
                        f"exceeds max {MAX_SEGMENT_DURATION_S}s "
                        f"gen={gen_id}"
                    )

            logger.info(
                f"Compose durations gen={gen_id} "
                f"hook={hook_dur:.2f}s i2v={i2v_dur:.2f}s "
                f"cta={cta_dur:.2f}s"
            )

            # ── Step 4: Build filter graph ────────────────────────
            lut_path = self._select_lut(benefit)
            lut_str  = str(lut_path).replace(os.sep, "/")

            filter_graph = self._build_filter_graph(
                hook_dur, i2v_dur, cta_dur, lut_str
            )

            # ── Step 5: Run FFmpeg ────────────────────────────────
            cmd = self._build_ffmpeg_cmd(
                hook_path, i2v_path, cta_path,
                tts_path, output_path, filter_graph,
            )

            logger.info(
                f"Compose FFmpeg starting gen={gen_id} "
                f"lut={lut_path.name} "
                f"watermark='AI Generated Content | AdvertWise'"
            )

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await process.communicate()

            if process.returncode != 0:
                raise ComposeError(
                    f"FFmpeg failed gen={gen_id} "
                    f"rc={process.returncode}: "
                    f"{stderr.decode()[:500]}"
                )

            logger.info(f"Compose FFmpeg done gen={gen_id}")

            # ── Step 6: Upload preview to R2 ─────────────────────
            r2_key        = f"{gen_id}/compose/preview_15s.mp4"
            preview_bytes = await asyncio.to_thread(
                Path(output_path).read_bytes
            )

            await asyncio.to_thread(
                self.r2_client.put_object,
                Bucket=bucket,
                Key=r2_key,
                Body=preview_bytes,
                ContentType="video/mp4",
            )

            logger.info(
                f"Compose uploaded gen={gen_id} key={r2_key}"
            )
            return r2_key

        except (ComposeError, ComposeDurationError):
            raise

        except Exception as e:
            raise ComposeError(
                f"Compose unexpected error gen={gen_id}: {e}"
            ) from e

        finally:
            self._cleanup_temp_files(temp_files)

