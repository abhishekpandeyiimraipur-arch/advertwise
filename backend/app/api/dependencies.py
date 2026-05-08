import json
from functools import wraps
from fastapi import Request
from fastapi.responses import JSONResponse
from app.infra_gateway import AdvertWiseException, ECMCode

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

# Re-export auth dependencies for unified import path
from app.auth import get_current_user

# DB pool dependency
from fastapi import Request

async def get_db(request: Request):
    return getattr(request.app.state, "db_pool",
                   getattr(request.app.state, "db", None))
