from arq.connections import RedisSettings
import os
from app.workers.phase4_coordinator import phase4_coordinator
from app.workers.export import worker_export

# Phase 4 workers do not exist yet — they are built in Micro-phase 4.
# This file is a locked placeholder that defines the Process B bulkhead.
# DO NOT add Phase 1-3 functions here. Ever.

async def startup(ctx: dict) -> None:
    """Process B startup — same resource init pattern as Process A."""
    import asyncpg
    import boto3
    from app.infra_redis import RedisManager

    ctx["db_pool"] = await asyncpg.create_pool(
        dsn=os.environ["DATABASE_URL"],
        min_size=1,
        max_size=4,
    )
    
    redis_mgr = RedisManager()
    await redis_mgr.connect()
    ctx["redis_db0"] = redis_mgr.db0
    ctx["redis_mgr"] = redis_mgr
    
    ctx["r2_client"] = boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT_URL"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )
    
    from app.gateway import ModelGateway
    ctx["gateway"] = ModelGateway(redis_client=ctx["redis_db0"])


async def shutdown(ctx: dict) -> None:
    if "db_pool" in ctx and ctx["db_pool"]:
        await ctx["db_pool"].close()
    if "redis_mgr" in ctx and ctx["redis_mgr"]:
        await ctx["redis_mgr"].disconnect()


class WorkerSettings:
    """
    Process B — Heavy render workers.
    Queue: phase4_workers
    Hosts: phase4_coordinator, worker_export (added in Micro-phase 4).
    Max 6 concurrent jobs — GPU/I2V bound.
    """
    queue_name = "phase4_workers"

    redis_settings = RedisSettings.from_dsn(
        os.environ.get("REDIS_URL", "redis://localhost:6379/1")
    )

    functions = [
        phase4_coordinator,
        worker_export,
    ]

    on_startup = startup
    on_shutdown = shutdown

    max_jobs = 6          # hard cap per §8.8 — do not increase without PRD change
    job_timeout = 300     # coordinator max — export has its own 45s cap

    health_check_interval = 30
