import re
import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class OutputGuardResult:
    safe: bool
    reason: Optional[str] = None   # e.g. "moderation", "pii:phone",
                                   # "competitor:patanjali", "schema"


# PII patterns — India-specific
# Duplicated from WorkerSafety intentionally — guards must not
# import from workers (import graph rule).
# TODO: consolidate to app/guards/safety_patterns.py post-beta
_PII_PATTERNS = {
    "phone":   re.compile(r'\b[6-9]\d{9}\b'),
    "email":   re.compile(r'[\w.\-]+@[\w.\-]+\.\w{2,}'),
    "aadhaar": re.compile(r'\b\d{4}\s?\d{4}\s?\d{4}\b'),
}

# Competitor denylist — duplicated from WorkerSafety intentionally
_COMPETITOR_DENYLIST = [
    "patanjali", "baidyanath", "himalaya", "mamaearth",
    "wow skincare", "plum", "nykaa", "mcaffeine",
    "forest essentials", "biotique", "khadi",
    "creatify", "invideo", "pictory", "synthesia",
    "canva", "kapwing", "vidyo",
]


class OutputGuard:
    """
    Output-side guard for the /chat route 5-stage chain (Stage 5).
    Validates LLM-refined script text after generation.

    CostGuard.record() MUST fire before OutputGuard runs (Stage 4).
    If OutputGuard rejects: COGS are preserved, turn NOT counted.
    """

    def __init__(self, gateway):
        self.gateway = gateway

    async def check_output(self, text: str) -> OutputGuardResult:
        """
        Runs 3 checks on refined script text.
        Returns OutputGuardResult(safe=True) if all pass.
        Returns OutputGuardResult(safe=False, reason=...) on first failure.
        """

        # ── Check 1: AI Moderation ───────────────────────────────
        try:
            mod_response = await self.gateway.route(
                capability="moderation",
                input_data={"text": text, "gen_id": "output_guard"},
            )
            is_safe = mod_response.text.strip().lower().startswith("safe")
            if not is_safe:
                logger.info(f"OutputGuard: moderation rejected output")
                return OutputGuardResult(safe=False, reason="moderation")
        except Exception as e:
            # Fail-open: moderation provider outage does not block user
            logger.warning(
                f"OutputGuard: moderation call failed ({e}). "
                f"Treating as safe (fail-open policy)."
            )

        # ── Check 2: PII Regex ───────────────────────────────────
        for pii_type, pattern in _PII_PATTERNS.items():
            if pattern.search(text):
                logger.info(f"OutputGuard: PII detected ({pii_type})")
                return OutputGuardResult(safe=False, reason=f"pii:{pii_type}")

        # ── Check 3: Competitor Denylist ─────────────────────────
        text_lower = text.lower()
        for competitor in _COMPETITOR_DENYLIST:
            if competitor in text_lower:
                logger.info(f"OutputGuard: competitor detected ({competitor})")
                return OutputGuardResult(
                    safe=False, reason=f"competitor:{competitor}"
                )

        return OutputGuardResult(safe=True, reason=None)
