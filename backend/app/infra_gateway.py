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

def idempotent(ttl: int = 300, action_key: str = "default", cache_only_2xx: bool = True):
    """
    Idempotency & Concurrency Decorator [TDD-CONCURRENCY]-A.
    Prevents double-clicks via a short-lived 'actlock' fence.
    Caches successful (2xx) responses.
    Requires 'redis_db5' to be available on the request.app state.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request: Request = kwargs.get("request")
            gen_id = kwargs.get("gen_id")
            
            if not request or not gen_id:
                # If we cannot uniquely identify the request, fallback to un-cached execution
                return await func(*args, **kwargs)

            redis_db5 = request.app.state.redis_db5
            idem_key = f"idem:{gen_id}:{action_key}"
            lock_key = f"actlock:{gen_id}:{action_key}"

            # 1. Idempotency Cache Check
            cached = await redis_db5.get(idem_key)
            if cached:
                return JSONResponse(content=json.loads(cached))

            # 2. Advisory Lock (Double-click defense)
            # nx=True ensures it only sets if the key DOES NOT exist
            acquired = await redis_db5.set(lock_key, "1", nx=True, ex=10)
            if not acquired:
                raise AdvertWiseException(ECMCode.ACTION_IN_PROGRESS, status_code=409)

            try:
                # Execute the wrapped core route logic
                response = await func(*args, **kwargs)
                
                # 3. Cache Result if 2xx
                if cache_only_2xx:
                    # In FastAPI, response could be a model or a Response object. 
                    # Assuming we wrap endpoints returning JSON encodable objects.
                    # For simplicity in this architectural stub, we assume a dict is returned.
                    if isinstance(response, dict):
                        await redis_db5.set(idem_key, json.dumps(response), ex=ttl)
                        
                return response
            finally:
                # 4. Always release the advisory lock
                await redis_db5.delete(lock_key)

        return wrapper
    return decorator
