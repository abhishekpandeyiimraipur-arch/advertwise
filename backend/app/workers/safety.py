import asyncio
import logging
import re
from prometheus_client import Counter
from app.types.script import Script
from app.core.exceptions import SafetyError

logger = logging.getLogger(__name__)

# PII patterns — India-specific
# Phone: Indian mobiles start with 6-9, 10 digits
PII_PATTERNS = {
    "phone":   re.compile(r'\b[6-9]\d{9}\b'),
    "email":   re.compile(r'[\w.\-]+@[\w.\-]+\.\w{2,}'),
    "aadhaar": re.compile(r'\b\d{4}\s?\d{4}\s?\d{4}\b'),
}

# Competitor denylist — checked against script full_text
# TODO: move to app/guards/competitor_denylist.yaml post-beta
COMPETITOR_DENYLIST = [
    # Indian FMCG / D2C competitors
    "patanjali", "baidyanath", "himalaya", "mamaearth",
    "wow skincare", "plum", "nykaa", "mcaffeine",
    "forest essentials", "biotique", "khadi",
    # Ad generation platform competitors (never mention in ads)
    "creatify", "invideo", "pictory", "synthesia",
    "canva", "kapwing", "vidyo",
]

SAFETY_TOTAL = Counter(
    'aw_safety_total',
    'Scripts processed by WorkerSafety')
SAFETY_REJECTED_TOTAL = Counter(
    'aw_safety_rejected_total',
    'Scripts rejected by WorkerSafety', ['reason'])
SAFETY_AUTORETRY_TOTAL = Counter(
    'aw_safety_autoretry_total',
    'WorkerSafety SafetyError triggers (all 3 failed)')

class WorkerSafety:
    def __init__(self, gateway, gen_id: str):
        self.gateway = gateway
        self.gen_id = gen_id

    async def _check_one_script(self, script: Script) -> dict:
        """
        Runs all 3 safety checks on one script.
        Short-circuits: if moderation fails, skips PII + competitor.

        Returns:
            {
                "framework": str,
                "safe": bool,
                "reason": str | None   # e.g. "moderation",
                                       # "pii:phone", "competitor:patanjali"
            }
        """
        text = script.full_text

        # ── Check 1: AI Moderation ───────────────────────────────
        try:
            mod_response = await self.gateway.route(
                capability="moderation",
                input_data={"text": text, "gen_id": self.gen_id},
            )
            # Llama Guard returns "safe" or "unsafe\n<category>"
            is_safe = mod_response.text.strip().lower().startswith("safe")
            if not is_safe:
                SAFETY_REJECTED_TOTAL.labels(reason="moderation").inc()
                return {
                    "framework": script.framework,
                    "safe": False,
                    "reason": "moderation",
                }
        except Exception as e:
            logger.warning(
                f"Moderation call failed for {script.framework}: {e}. "
                f"Treating as safe to avoid blocking generation."
            )
            # Moderation API failure → treat as safe (fail-open)
            # Rationale: provider outage should not block all generations

        # ── Check 2: PII Regex ───────────────────────────────────
        for pii_type, pattern in PII_PATTERNS.items():
            if pattern.search(text):
                SAFETY_REJECTED_TOTAL.labels(reason=f"pii:{pii_type}").inc()
                return {
                    "framework": script.framework,
                    "safe": False,
                    "reason": f"pii:{pii_type}",
                }

        # ── Check 3: Competitor Denylist ─────────────────────────
        text_lower = text.lower()
        for competitor in COMPETITOR_DENYLIST:
            if competitor in text_lower:
                SAFETY_REJECTED_TOTAL.labels(reason="competitor").inc()
                return {
                    "framework": script.framework,
                    "safe": False,
                    "reason": f"competitor:{competitor}",
                }

        # All checks passed
        return {
            "framework": script.framework,
            "safe": True,
            "reason": None,
        }

    async def process(self, scripts: list[Script]) -> dict:
        flags = await asyncio.gather(
            *[self._check_one_script(s) for s in scripts],
            return_exceptions=True
        )

        processed_flags = []
        for script, flag in zip(scripts, flags):
            if isinstance(flag, Exception):
                logger.warning(
                    f"Safety check completely failed for {script.framework}: {flag}. "
                    f"Treating as safe to avoid blocking generation."
                )
                processed_flags.append({
                    "framework": script.framework,
                    "safe": True,
                    "reason": None
                })
            else:
                processed_flags.append(flag)

        safe_scripts = [s for s, f in zip(scripts, processed_flags) if f["safe"]]

        rejected_frameworks = [
            {"framework": f["framework"], "reason": f["reason"]}
            for f in processed_flags
            if not f["safe"]
        ]

        if len(safe_scripts) == 0:
            SAFETY_AUTORETRY_TOTAL.inc()
            raise SafetyError(
                f"All 3 scripts failed safety checks. "
                f"Rejected: {rejected_frameworks}"
            )

        SAFETY_TOTAL.inc()

        return {
            "safe_scripts": safe_scripts,
            "safety_flags": [
                {
                    "framework": f["framework"],
                    "safe": f["safe"],
                    "reason": f["reason"],
                }
                for f in processed_flags
            ],
            "scripts_available": len(safe_scripts) > 0,
            "rejected_frameworks": rejected_frameworks,
        }
