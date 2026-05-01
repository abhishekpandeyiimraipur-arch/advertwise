from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging

from app.redis_client import RedisManager
from app.gateway import add_exception_handlers
from app.api.routes import router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

redis_mgr = RedisManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing application lifecycle...")
    await redis_mgr.connect()
    
    # Expose connections for decorators and routes
    app.state.redis_db0 = redis_mgr.db0
    app.state.redis_db2 = redis_mgr.db2
    app.state.redis_db5 = redis_mgr.db5
    app.state.redis_mgr = redis_mgr
    
    logger.info("Application wiring complete. Redis loaded.")
    yield
    
    logger.info("Tearing down application lifecycle...")
    await redis_mgr.disconnect()

app = FastAPI(title="AdvertWise Wiring Proof", lifespan=lifespan)

# 1. Register global exception handlers mapping to ECM codes
add_exception_handlers(app)

# 2. Include the stub routes
app.include_router(router)
