import json
import logging
from functools import wraps
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# Canonical subset of ECM codes extracted from the TDD
# (Full definitions live in shared/types/ecm_codes.ts)
class ECMCode:
    PRODUCT_NOT_SUPPORTED = "ECM-001"
    COMPLIANCE_FLAGGED = "ECM-002"
    INSUFFICIENT_FUNDS = "ECM-007"
    BUDGET_LIMIT = "ECM-009"
    ACTION_IN_PROGRESS = "ECM-012"
    CONNECTION_LOST = "ECM-013"
    DECLARATION_REQUIRED = "ECM-017"

class AdvertWiseException(Exception):
    """
    Centralized exception class mapped exclusively to PRD-ERROR-MATRIX codes.
    Prevents raw exceptions from leaking to the client.
    """
    def __init__(self, code: str, status_code: int = 400, context: dict = None):
        self.code = code
        self.status_code = status_code
        self.context = context or {}

def add_exception_handlers(app: FastAPI):
    """
    Registers global exception handlers to enforce ECM code compliance.
    """
    @app.exception_handler(AdvertWiseException)
    async def advertwise_exception_handler(request: Request, exc: AdvertWiseException):
        logger.warning(f"AdvertWiseException: {exc.code} at {request.url.path}")
        return JSONResponse(
            status_code=exc.status_code,
            content={"error_code": exc.code, "context": exc.context}
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        # Prevent raw exception leakage; fallback to generic ECM-013 (Connection Lost/Server Error)
        logger.error(f"Unhandled server error: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error_code": ECMCode.CONNECTION_LOST, "context": {"message": "Internal Server Error"}}
        )

