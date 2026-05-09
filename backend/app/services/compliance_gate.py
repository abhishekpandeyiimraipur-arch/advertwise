import re
from typing import Optional

class ComplianceResult:
    def __init__(self, safe: bool, reason: Optional[str] = None):
        self.safe = safe
        self.reason = reason

class ComplianceGate:
    """
    Input-side guard. 
    Runs as Stage 1 of the 5-stage chat chain + on every /generate request.
    """
    
    # ── BLOCK 1: MALICIOUS PATTERNS ──
    # Standard heuristic patterns to catch 95% of casual prompt injection attempts.
    INJECTION_PATTERNS = [
        r"ignore (?:previous|all|above) (?:instructions?|rules?)",
        r"you are (?:now )?(?:a |an )?(?:different|new) (?:ai|assistant|model)",
        r"system (?:prompt|message|instruction)[\s:]",
        r"</?(?:system|user|assistant)>",
        r"<\|(?:system|user|assistant)\|>",
    ]

    # ── BLOCK 2: THE MAIN VALIDATOR ──
    async def check_input(self, text: str) -> ComplianceResult:
        """
        Validates user input. Completely synchronous/CPU-bound logic inside an async def.
        """
        # 1. Control Character Sanitization
        # Prevents users from using invisible unicode to bypass filters or break parsers.
        sanitized = text.translate(str.maketrans('', '', ''.join(chr(c) for c in range(0, 32) if c not in (9, 10, 13))))
        sanitized = re.sub(r'[\u200b-\u200f\u202a-\u202e]', '', sanitized)
        
        if sanitized != text:
            return ComplianceResult(safe=False, reason="control_chars")

        # 2. Injection Pattern Detection
        low = text.lower()
        for pat in self.INJECTION_PATTERNS:
            if re.search(pat, low):
                return ComplianceResult(safe=False, reason="prompt_injection")

        # Note: Word count constraints (e.g., max 500 chars) are handled 
        # upstream by FastAPI/Pydantic validation, not here.
        
        return ComplianceResult(safe=True, reason=None)
