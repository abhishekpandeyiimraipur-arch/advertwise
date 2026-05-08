from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import logging
import os
import boto3
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env.local")

import asyncpg
from .infra_redis import RedisManager
from .infra_gateway import add_exception_handlers
from .api.routes import router
from app.api.routes.generations import router as generations_router
from app.api.routes.advance import router as advance_router
from app.api.routes.regenerate import router as regenerate_router
from app.api.routes.edit_back import router as edit_back_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

redis_mgr = RedisManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing application lifecycle...")

    # Database pool
    app.state.db_pool = await asyncpg.create_pool(
        dsn=os.environ["DATABASE_URL"],
        min_size=2,
        max_size=10,
        statement_cache_size=0,
    )
    logger.info("Database pool created.")

    # Redis
    await redis_mgr.connect()
    app.state.redis_db0 = redis_mgr.db0
    app.state.redis_db2 = redis_mgr.db2
    app.state.redis_db5 = redis_mgr.db5
    app.state.redis_mgr = redis_mgr
    logger.info("Application wiring complete. Redis + DB loaded.")

    app.state.db = app.state.db_pool

    app.state.r2_client = boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT_URL"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )

    from arq import create_pool as arq_create_pool
    from arq.connections import RedisSettings
    app.state.arq_pool = await arq_create_pool(
        RedisSettings.from_dsn(os.environ["REDIS_URL"])
    )

    yield

    logger.info("Tearing down application lifecycle...")
    await app.state.db_pool.close()
    await redis_mgr.disconnect()

app = FastAPI(
    title="AdvertWise API",
    lifespan=lifespan
)

add_exception_handlers(app)

# Dev UI
_static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(_static_dir, exist_ok=True)
app.mount("/dev-ui-static", StaticFiles(directory=_static_dir), name="static")

@app.get("/dev-ui")
async def dev_ui():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "dev_ui.html"))

app.include_router(router)
app.include_router(generations_router)
app.include_router(advance_router)
app.include_router(regenerate_router)
app.include_router(edit_back_router)