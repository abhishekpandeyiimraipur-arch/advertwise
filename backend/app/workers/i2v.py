"""
WorkerI2V — Image-to-video generation with model-based routing.
[TDD-WORKERS]-H (corrected architecture)

Deep module: animates isolated product PNG into a 9s video.
Input:  isolated_png_url — full public CDN URL (passed as-is to gateway/Fal.ai)
Output: R2 key string of uploaded MP4

Gateway handles Fal.ai submission + polling.
Worker handles video download (urllib stdlib) + R2 upload (boto3).
No boto3 download — isolated_png_url is a public CDN URL, passed directly.

Adding a new I2V model = edit ARCHETYPE_MODEL_MAP only.
"""
import asyncio
import logging
import os
import urllib.request
from app.core.exceptions import I2VError

logger = logging.getLogger(__name__)


# ── Motion / Environment Constants ───────────────────────────────────────────

MOTION_ARCHETYPES: dict[int, str] = {
    1: "orbit",
    2: "drift",
    3: "hero_zoom",
    4: "unbox",
    5: "liquid_pour",
}

ENV_PRESETS: dict[int, str] = {
    1: "clean white background, minimal studio",
    2: "dark minimal studio, neutral tones",
    3: "warm kitchen, morning natural light",
    4: "outdoor natural setting, soft daylight",
    5: "warm living room interior",
    6: "outdoor fashion setting",
    7: "home interior, warm tones",
    8: "pure product on surface, focused lighting",
}

# Fal.ai model IDs — all accessed via single FAL_KEY.
# Kling: best for stable geometric motion (orbit, hero_zoom).
# Wan:   best for organic fluid motion + cheapest (drift, unbox, liquid).
# Fallback is always Wan — never fail completely.
ARCHETYPE_MODEL_MAP: dict[str, list[str]] = {
    "orbit":       ["fal-ai/kling-video/v1.6/standard/image-to-video",
                    "fal-ai/wan-i2v"],
    "drift":       ["fal-ai/wan-i2v",
                    "fal-ai/minimax-video/image-to-video"],
    "hero_zoom":   ["fal-ai/kling-video/v1.6/standard/image-to-video",
                    "fal-ai/wan-i2v"],
    "unbox":       ["fal-ai/wan-i2v",
                    "fal-ai/minimax-video/image-to-video"],
    "liquid_pour": ["fal-ai/wan-i2v",
                    "fal-ai/minimax-video/image-to-video"],
}

DEFAULT_MODELS = [
    "fal-ai/wan-i2v",
    "fal-ai/minimax-video/image-to-video",
]

I2V_TIMEOUT_S = 180.0


# ── Worker ────────────────────────────────────────────────────────────────────

class WorkerI2V:
    """
    Deep module: animates isolated product PNG into 9s video.
    Input:  isolated_png_url — full public CDN URL (passed as-is to Fal.ai)
    Output: R2 key string of uploaded MP4
    Gateway handles Fal.ai submission + polling.
    Worker handles download (urllib stdlib) + R2 upload (boto3).
    """

    def __init__(self, gateway, r2_client):
        self.gateway = gateway
        self.r2_client = r2_client
        self._bucket = os.environ.get("R2_BUCKET_NAME", "advertwise-dev-assets")

    def _select_models(self, motion_archetype_id: int) -> list[str]:
        """
        Pure function. Maps archetype ID → [primary_model, fallback_model].
        Returns DEFAULT_MODELS for unknown archetype_id.
        """
        archetype_name = MOTION_ARCHETYPES.get(motion_archetype_id)
        if archetype_name and archetype_name in ARCHETYPE_MODEL_MAP:
            return ARCHETYPE_MODEL_MAP[archetype_name]
        return DEFAULT_MODELS

    def _build_prompt(
        self,
        motion_archetype_id: int,
        environment_preset_id: int,
        optimized_prompt: str,
    ) -> str:
        """
        Pure function. Builds Fal.ai generation prompt.
        Unknown IDs use "smooth" and "neutral studio" as fallbacks.
        """
        motion = MOTION_ARCHETYPES.get(motion_archetype_id, "smooth")
        env = ENV_PRESETS.get(environment_preset_id, "neutral studio")
        return (
            f"{optimized_prompt}. {motion} motion. "
            f"{env} environment. "
            f"Smooth camera movement. Commercial product quality. "
            f"No people. No text overlays. No watermarks."
        )

    def _generate_seed(self, attempt: int) -> int:
        """attempt 1 → 42. attempt 2 → 137. Other → 42."""
        if attempt == 2:
            return 137
        return 42

    async def _download_video(self, video_url: str, gen_id: str) -> bytes:
        """
        Downloads video bytes from provider CDN URL.
        Uses urllib.request (stdlib — not banned).
        Runs in thread to avoid blocking event loop.
        On failure → raise I2VError.
        """
        try:
            video_bytes = await asyncio.to_thread(
                urllib.request.urlopen(video_url).read
            )
            return video_bytes
        except Exception as e:
            raise I2VError(f"Video download failed: {e}") from e

    async def process(
        self,
        gen_id: str,
        isolated_png_url: str,
        motion_archetype_id: int,
        environment_preset_id: int,
        optimized_prompt: str,
        attempt: int = 1,
    ) -> str:
        """
        Called by phase4_coordinator. Returns R2 key of MP4.

        isolated_png_url: full public CDN URL — passed as-is to gateway.
        Returns: R2 object key string (credentialed path, not presigned).
        Raises: I2VError on any failure — propagates to coordinator.
        Never raises anything except I2VError.
        """
        # Step 1 — Select model order
        models = self._select_models(motion_archetype_id)
        primary, fallback = models[0], models[1]

        # Step 2 — Build prompt
        prompt = self._build_prompt(
            motion_archetype_id,
            environment_preset_id,
            optimized_prompt,
        )

        # Step 3 — Try primary model
        response = None
        used_model = primary
        try:
            response = await asyncio.wait_for(
                self.gateway.route(
                    capability="i2v",
                    input_data={
                        "image_url": isolated_png_url,
                        "model":     primary,
                        "prompt":    prompt,
                        "duration":  9,
                        "seed":      self._generate_seed(attempt),
                        "gen_id":    gen_id,
                    },
                ),
                timeout=I2V_TIMEOUT_S,
            )
        except asyncio.TimeoutError:
            logger.warning(
                f"I2V primary timeout gen={gen_id} attempt={attempt} "
                f"model={primary}. Trying fallback={fallback}."
            )

        # Step 4 — Try fallback if primary failed
        if response is None:
            used_model = fallback
            try:
                response = await asyncio.wait_for(
                    self.gateway.route(
                        capability="i2v",
                        input_data={
                            "image_url": isolated_png_url,
                            "model":     fallback,
                            "prompt":    prompt,
                            "duration":  9,
                            "seed":      self._generate_seed(attempt),
                            "gen_id":    gen_id,
                        },
                    ),
                    timeout=I2V_TIMEOUT_S,
                )
            except (asyncio.TimeoutError, Exception) as e:
                raise I2VError(
                    f"I2V failed gen={gen_id} attempt={attempt}: "
                    f"both {primary} and {fallback} exhausted"
                ) from e

        # video_url is a provider CDN URL returned in GatewayResponse.video_url
        video_url = response.video_url

        # Step 5 — Download video bytes from provider CDN (urllib stdlib)
        video_bytes = await self._download_video(video_url, gen_id)

        # Step 6 — Upload to R2 (credentialed boto3, never presigned)
        r2_key = f"{gen_id}/i2v/candidate_{attempt}.mp4"
        try:
            await asyncio.to_thread(
                self.r2_client.put_object,
                Key=r2_key,
                Body=video_bytes,
                Bucket=self._bucket,
            )
        except Exception as e:
            raise I2VError(f"R2 upload failed: {e}") from e

        # Step 7 — Log success
        logger.info(
            f"I2V done gen={gen_id} attempt={attempt} "
            f"model={used_model} key={r2_key}"
        )

        # Step 8 — Return R2 key
        return r2_key
