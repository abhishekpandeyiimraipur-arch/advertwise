class AdvertWiseException(Exception):
    """
    Base exception for all AdvertWise system errors.
    Hard invariant: no raw exceptions leak to the API gateway.
    All worker and service exceptions inherit from this class.
    The DLQ handler and route error middleware catch this type only.
    """
    def __init__(
        self,
        message: str = "",
        ecm_code: str = None,
        code: str = None,
        status_code: int = 500,
        context: dict = None,
    ):
        # Accept both `code=` and `ecm_code=` — routes use both patterns
        self.ecm_code = ecm_code or code
        self.status_code = status_code
        self.context = context or {}
        # message falls back to ecm_code string if not provided
        self.message = message or self.ecm_code or "Internal error"
        super().__init__(self.message)


class ProviderUnavailableError(AdvertWiseException):
    """Raised when a provider call fails after all retries.
    Caught by phase2_chain to trigger SAFE_TRIO fallback."""
    pass


class SafetyError(AdvertWiseException):
    """Raised by WorkerSafety when all 3 scripts fail safety checks.
    Caught by phase2_chain which auto-retries once with SAFE_TRIO."""
    pass


# ── Phase 4 Worker Exceptions ─────────────────────────────────────
# Pre-declared here so DLQ handler imports one module only.
# Each worker imports its own exception from this file.

class TTSError(AdvertWiseException):
    """WorkerTTS: audio generation or R2 upload failure."""
    pass


class I2VError(AdvertWiseException):
    """WorkerI2V: image-to-video generation failure."""
    pass


class ReflectError(AdvertWiseException):
    """WorkerReflect: no candidate passed SSIM + deformation guard."""
    pass


class ComposeError(AdvertWiseException):
    """WorkerCompose: FFmpeg composition failure."""
    pass


class ComposeDurationError(ComposeError):
    """WorkerCompose: input duration out of bounds."""
    pass


class C2PASignError(AdvertWiseException):
    """WorkerExport: c2patool non-zero returncode or timeout."""
    pass


class ExportPreconditionError(AdvertWiseException):
    """WorkerExport: declaration missing or preview purged."""
    pass
