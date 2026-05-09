"""
WorkerTTS — Text-to-speech synthesis with rule-based provider routing.
[TDD-WORKERS]-H

Deep module: phase4_coordinator calls process() and never knows which
provider was used. All routing intelligence lives in _select_provider().
Gateway is the executor only.

Adding a new TTS provider = edit _select_provider() and PROVIDER_ROUTING only.
No changes to gateway required.
"""
import asyncio
import logging
from app.core.exceptions import TTSError

logger = logging.getLogger(__name__)




# ── Language / Framework Constants ───────────────────────────────────────────

INDIAN_LANGUAGES = {
    "hindi", "hinglish", "marathi",
    "punjabi", "bengali", "tamil", "telugu"
}

EMOTIONAL_FRAMEWORKS = {"emotion"}

# Provider routing table — rule-based, deterministic.
# Each entry: routing_key → [primary, fallback]
# Expand this dict post-MVP to add new providers.
# Never move routing logic into the gateway — keep it here.
PROVIDER_ROUTING: dict[str, list[str]] = {
    "indian_any":           ["sarvam", "elevenlabs"],
    "english_emotion":      ["elevenlabs", "google"],
    "english_logic":        ["google", "elevenlabs"],
    "english_conversion":   ["elevenlabs", "google"],
    "english_default":      ["elevenlabs", "google"],
}


# ── Worker ────────────────────────────────────────────────────────────────────

class WorkerTTS:
    """
    Deep module: converts script text to audio, uploads to R2.
    Caller (phase4_coordinator) sees only process().
    Provider selection is internal — never exposed upward.
    Adding a new TTS provider = edit _select_provider() only.
    """

    def __init__(self, gateway, r2_client):
        self.gateway = gateway
        self.r2_client = r2_client

    def _select_provider(
        self,
        language: str,
        framework_angle: str,
        category: str,
    ) -> list[str]:
        """
        Pure function. No external calls. No DB access.
        Returns [primary_provider, fallback_provider].

        Rules (evaluated in order, first match wins):
        1. language in INDIAN_LANGUAGES
               → PROVIDER_ROUTING["indian_any"]
        2. language == "english" AND framework_angle == "emotion"
               → PROVIDER_ROUTING["english_emotion"]
        3. language == "english" AND framework_angle == "logic"
               → PROVIDER_ROUTING["english_logic"]
        4. language == "english" AND framework_angle == "conversion"
               → PROVIDER_ROUTING["english_conversion"]
        5. any other language
               → PROVIDER_ROUTING["english_default"]

        category is accepted as a parameter for future use
        (e.g. d2c_beauty may prefer a warmer voice post-MVP)
        but is not used in routing logic at MVP.
        """
        if language in INDIAN_LANGUAGES:
            return PROVIDER_ROUTING["indian_any"]

        if language == "english":
            if framework_angle == "emotion":
                return PROVIDER_ROUTING["english_emotion"]
            if framework_angle == "logic":
                return PROVIDER_ROUTING["english_logic"]
            if framework_angle == "conversion":
                return PROVIDER_ROUTING["english_conversion"]

        return PROVIDER_ROUTING["english_default"]

    async def process(
        self,
        gen_id: str,
        script_text: str,
        language: str,
        context: dict,
    ) -> str:
        """
        Called by phase4_coordinator inside asyncio.gather.

        context keys used:
            framework_angle: str  — "emotion" | "logic" | "conversion"
            category: str         — GreenZoneCategory value

        Returns: R2 object key string (credentialed path, not presigned).
        Raises: TTSError on any failure — propagates to coordinator.
        """
        framework_angle = context.get("framework_angle", "")
        category = context.get("category", "")

        # Step 1 — Select provider order
        providers = self._select_provider(language, framework_angle, category)
        primary, fallback = providers[0], providers[1]

        # Step 2 — Try primary provider
        response = None
        used_provider = primary
        try:
            response = await asyncio.wait_for(
                self.gateway.route(
                    capability="tts",
                    input_data={
                        "text":     script_text,
                        "language": language,
                        "provider": primary,
                        "gen_id":   gen_id,
                    },
                ),
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            logger.warning(
                f"TTS primary timeout gen={gen_id} provider={primary}. "
                f"Trying fallback={fallback}."
            )

        # Step 3 — Try fallback if primary failed
        if response is None:
            used_provider = fallback
            try:
                response = await asyncio.wait_for(
                    self.gateway.route(
                        capability="tts",
                        input_data={
                            "text":     script_text,
                            "language": language,
                            "provider": fallback,
                            "gen_id":   gen_id,
                        },
                    ),
                    timeout=30.0,
                )
            except (asyncio.TimeoutError, Exception) as e:
                raise TTSError(
                    f"TTS failed for {gen_id}: both {primary} and {fallback} failed"
                ) from e

        # Step 4 — Extract audio bytes
        audio_bytes = response.audio_bytes

        # Step 5 — Upload to R2 (credentialed boto3, never presigned)
        r2_key = f"{gen_id}/tts/voiceover.mp3"
        try:
            self.r2_client.put_object(
                Body=audio_bytes,
                Key=r2_key,
            )
        except Exception as e:
            raise TTSError(f"R2 upload failed: {e}") from e

        # Step 6 — Log success
        logger.info(
            f"TTS done gen={gen_id} provider={used_provider} "
            f"language={language} key={r2_key}"
        )

        # Step 7 — Return R2 key
        return r2_key
