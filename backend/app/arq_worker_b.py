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


async def on_job_dead(ctx: dict, job_id: str, score: int) -> None:
    import json, uuid, logging
    logger = logging.getLogger(__name__)
    db_pool   = ctx.get("db_pool")
    redis_mgr = ctx.get("redis_mgr")
    redis_db0 = ctx.get("redis_db0")
    # job_id format: "phase4:{gen_id}" or "export:{gen_id}"
    parts = job_id.split(":")
    gen_id = parts[1] if len(parts) >= 2 else None
    if not gen_id:
        logger.error(f"on_job_dead: no gen_id in job_id={job_id}")
        return
    logger.warning(f"on_job_dead: gen_id={gen_id} job_id={job_id}")
    try:
        async with db_pool.acquire() as conn:
            gen = await conn.fetchrow(
                "SELECT user_id, status FROM generations WHERE gen_id = $1",
                uuid.UUID(gen_id)
            )
        if not gen:
            logger.error(f"on_job_dead: gen_id={gen_id} not found")
            return
        user_id = str(gen["user_id"])
        refund_result = await redis_mgr.execute_wallet_refund(user_id, gen_id)
        logger.info(f"on_job_dead: refund={refund_result} gen={gen_id}")
        async with db_pool.acquire() as conn:
            await conn.execute(
                """UPDATE generations SET status='failed_render',
                   error_code='ECM-013', updated_at=NOW()
                   WHERE gen_id=$1 AND status NOT IN (
                   'failed_render','failed_export','failed_safety',
                   'failed_compliance','failed_category','export_ready')""",
                uuid.UUID(gen_id)
            )
            await conn.execute(
                """INSERT INTO audit_log (user_id, gen_id, action, payload)
                   VALUES ($1, $2, 'dlq_failure', $3::jsonb)""",
                uuid.UUID(user_id), uuid.UUID(gen_id),
                json.dumps({"job_id": job_id,
                            "refund_result": refund_result})
            )
        if redis_db0:
            await redis_db0.lpush(f"sse:{gen_id}", json.dumps({
                "type": "state_change", "state": "failed_render",
                "error_code": "ECM-013"
            }))
            await redis_db0.expire(f"sse:{gen_id}", 300)
        logger.info(f"on_job_dead: complete gen={gen_id}")
    except Exception as e:
        logger.error(f"on_job_dead FAILED gen={gen_id}: {e}", exc_info=True)


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
    on_job_dead = on_job_dead

    max_jobs = 6          # hard cap per §8.8 — do not increase without PRD change
    job_timeout = 300     # coordinator max — export has its own 45s cap

    health_check_interval = 30
