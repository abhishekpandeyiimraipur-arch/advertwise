from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
import logging

# Infra imports (collision-proof)
from .infra_redis import RedisManager
from .infra_gateway import add_exception_handlers
from .api.routes import router
from app.routes.generations import router as generations_router
from app.routes.generation_advance import router as advance_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Redis Manager (singleton for app lifecycle)
redis_mgr = RedisManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing application lifecycle...")

    # Connect to Redis
    await redis_mgr.connect()

    # Inject into app.state (DI contract)
    app.state.redis_db0 = redis_mgr.db0
    app.state.redis_db2 = redis_mgr.db2
    app.state.redis_db5 = redis_mgr.db5
    app.state.redis_mgr = redis_mgr

    logger.info("Application wiring complete. Redis loaded.")

    yield

    logger.info("Tearing down application lifecycle...")
    await redis_mgr.disconnect()


# Initialize FastAPI
app = FastAPI(
    title="AdvertWise Wiring Proof",
    lifespan=lifespan
)

# Register global exception handlers
add_exception_handlers(app)

# Include API routes
app.include_router(router)
app.include_router(generations_router)
app.include_router(advance_router)


