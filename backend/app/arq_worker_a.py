from arq import cron
from arq.connections import RedisSettings
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env.local")
import os

from app.workers.worker_extract import phase1_extract

async def startup(ctx: dict) -> None:
    """
    Warm up all shared resources once per process lifetime.
    These are injected into every job via ctx.
    """
    import asyncpg
    import boto3
    from app.infra_redis import RedisManager

    # DB connection pool
    ctx["db_pool"] = await asyncpg.create_pool(
        dsn=os.environ["DATABASE_URL"],
        min_size=2,
        max_size=10,
    )

    # Redis DB0 (SSE + wallet cache)
    redis_mgr = RedisManager()
    await redis_mgr.connect()
    ctx["redis_db0"] = redis_mgr.db0
    ctx["redis_mgr"] = redis_mgr

    # R2 client (boto3 S3-compatible)
    ctx["r2_client"] = boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT_URL"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )

    from app.gateway import get_gateway
    ctx["gateway"] = get_gateway()


async def shutdown(ctx: dict) -> None:
    """Release resources on graceful shutdown."""
    if "db_pool" in ctx and ctx["db_pool"]:
        await ctx["db_pool"].close()
    if "redis_mgr" in ctx and ctx["redis_mgr"]:
        await ctx["redis_mgr"].disconnect()


# ── ARQ WorkerSettings ────────────────────────────────────────────────────────
class WorkerSettings:
    """
    Process A — Interactive workers.
    Queue: phase1_to_3_workers
    Hosts: phase1_extract + all cron maintenance jobs.
    Phase 2 and Phase 3 workers will be added here as they are built.
    """
    queue_name = "phase1_to_3_workers"

    # Redis connection for ARQ's own job queue (DB1)
    redis_settings = RedisSettings.from_dsn(
        os.environ.get("REDIS_URL", "redis://localhost:6379/1")
    )

    # Registered job functions
    # ADD new workers here as each slice is built — never remove
    functions = [
        phase1_extract,
        # phase2_chain will be added in Slice C/Phase 2 build
        # retention_sweep, partition_rotator etc. added in cross-cutting slice
    ]

    # Cron jobs (registered but implementations are stubs until cross-cutting slice)
    # cron_jobs = [
    #     cron(retention_sweep,    hour=20, minute=30),   # 02:00 IST = 20:30 UTC
    #     cron(partition_rotator,  hour=20, minute=45),   # 02:15 IST = 20:45 UTC
    #     cron(r2_orphan_sweep,    weekday=0, hour=21),   # Mon 02:30 IST = Mon 21:00 UTC
    # ]
    # Uncomment when cross-cutting jobs are implemented.

    on_startup = startup
    on_shutdown = shutdown

    # Concurrency: tunable via env var, default 4 for MVP single-server
    max_jobs = int(os.environ.get("WORKER_A_MAX_JOBS", "4"))

    # Health check poll interval
    health_check_interval = 30
