class ProviderUnavailableError(Exception):
    """Raised when a provider call fails after all retries.
    Caught by phase2_chain to trigger SAFE_TRIO fallback.
    ECM wrapping happens at the route handler level, not here.
    Never import from infra_gateway or any worker.
    """
    pass


class SafetyError(Exception):
    """
    Raised by WorkerSafety when all 3 scripts fail safety checks.
    Caught by phase2_chain which auto-retries once with SAFE_TRIO.
    If SAFE_TRIO also fails, generation enters failed_safety state.
    """
    pass
