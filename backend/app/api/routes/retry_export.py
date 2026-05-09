"""
/retry-export route — re-queue a failed export.
[TDD-API]-G

POST /api/generations/{gen_id}/retry-export

Called when worker_export fails and status = failed_export.
Re-locks credit, increments retry counter, re-enqueues worker_export.
Max 3 retry attempts enforced at DB level.
"""
import asyncio
import hashlib
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from arq import create_pool
from arq.connections import RedisSettings

from app.api.dependencies import idempotent, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

DECLARATION_FRESHNESS_SECONDS = 24 * 3600   # 24 hours


class RetryExportRequest(BaseModel):
    # Re-sign fields — only required when declaration is stale (>24h)
    # All three must be True if resign=True
    commercial_use: bool = False
    image_rights:   bool = False
    ai_disclosure:  bool = False
    resign:         bool = False  # True = user is re-signing


@router.post("/generations/{gen_id}/retry-export")
@idempotent(ttl=300, action_key="retry-export", cache_only_2xx=True)
async def retry_export(
    gen_id: str,
    body: RetryExportRequest,
    request: Request,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: Annotated[Any, Depends(get_current_user)] = None,
):
    """
    9-step retry chain for failed exports.
    Re-locks credit, increments retry count, re-enqueues worker_export.
    Monotonic job ID prevents duplicate workers.
    Max 3 retries enforced. Declaration freshness checked.
    """
    db_pool   = request.app.state.db_pool
    redis_mgr = request.app.state.redis_mgr
    user_id   = str(current_user.id)
    r2_public_url = os.environ.get(
        "R2_PUBLIC_URL",
        "https://pub-dfacf0a5eece46e4ac8e5aaaf5da5368.r2.dev"
    )

    # ── Step 1: Auth + read generation row ───────────────────────
    async with db_pool.acquire() as conn:
        gen = await conn.fetchrow(
            """SELECT gen_id, user_id, status, plan_tier,
                      preview_url, declaration_accepted,
                      declaration_accepted_at, declaration_hash,
                      export_retry_count
               FROM generations
               WHERE gen_id = $1 AND user_id = $2""",
            gen_id, user_id,
        )

    if not gen:
        raise HTTPException(
            status_code=404,
            detail="Generation not found"
        )

    # ── Step 2: Status guard ──────────────────────────────────────
    # export_ready = already done → idempotent success
    if gen["status"] == "export_ready":
        return {
            "gen_id":  gen_id,
            "status":  "export_ready",
            "message": "Export already completed.",
        }

    if gen["status"] != "failed_export":
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "ECM-STATE-CONFLICT",
                "message": (
                    f"Generation is in state '{gen['status']}'. "
                    f"Expected 'failed_export'."
                ),
            }
        )

    # ── Step 3: Retry count guard ─────────────────────────────────
    current_retry_count = gen["export_retry_count"]

    if current_retry_count >= 3:
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "ECM-019",
                "message": (
                    "Maximum export retries (3) exhausted. "
                    "Please contact support."
                ),
                "export_retry_count": current_retry_count,
            }
        )

    # ── Step 4: Declaration precondition ──────────────────────────
    if not gen["declaration_accepted"]:
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "ECM-DECLARATION-MISSING",
                "message": "Declaration was never accepted.",
            }
        )

    # ── Step 5: Declaration freshness check ───────────────────────
    # If declaration is older than 24h, user must re-sign.
    now = datetime.now(timezone.utc)
    declaration_at = gen["declaration_accepted_at"]

    # Make timezone-aware if DB returns naive datetime
    if declaration_at is not None and declaration_at.tzinfo is None:
        declaration_at = declaration_at.replace(tzinfo=timezone.utc)

    declaration_age_s = (
        (now - declaration_at).total_seconds()
        if declaration_at else DECLARATION_FRESHNESS_SECONDS + 1
    )
    is_stale = declaration_age_s > DECLARATION_FRESHNESS_SECONDS

    if is_stale and not body.resign:
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "ECM-DECLARATION-STALE",
                "message": (
                    "Declaration expired (>24h). "
                    "Please re-accept the declaration to continue."
                ),
                "requires_resign": True,
            }
        )

    if is_stale and body.resign:
        # Validate re-sign checkboxes
        if not (body.commercial_use and
                body.image_rights and
                body.ai_disclosure):
            raise HTTPException(
                status_code=422,
                detail={
                    "error_code": "ECM-DECLARATION-INCOMPLETE",
                    "message": (
                        "All three declaration checkboxes must "
                        "be accepted."
                    ),
                }
            )

    # ── Step 6: R2 HEAD check — preview still exists? ────────────
    preview_r2_key = gen["preview_url"].replace(
        f"{r2_public_url}/", ""
    )

    try:
        import boto3
        r2_client = boto3.client(
            "s3",
            endpoint_url=os.environ["R2_ENDPOINT_URL"],
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
            region_name="auto",
        )
        await asyncio.to_thread(
            r2_client.head_object,
            Bucket=os.environ["R2_BUCKET_NAME"],
            Key=preview_r2_key,
        )
    except Exception:
        # Preview purged by retention sweep — ECM-018
        async with db_pool.acquire() as conn:
            await conn.execute(
                """UPDATE generations
                   SET status     = 'failed_export',
                       updated_at = NOW()
                   WHERE gen_id = $1""",
                gen_id,
            )
        raise HTTPException(
            status_code=410,
            detail={
                "error_code": "ECM-018",
                "message": (
                    "Preview asset has expired. "
                    "Please start a new generation."
                ),
            }
        )

    # ── Step 7: Re-lock credit ────────────────────────────────────
    lock_result = await redis_mgr.execute_wallet_lock(
        user_id, gen_id, credits=1
    )
    if not lock_result:
        raise HTTPException(
            status_code=402,
            detail={
                "error_code": "ECM-INSUFFICIENT-CREDITS",
                "message": "Insufficient credits to retry export.",
            }
        )

    # ── Step 8: Compute new declaration hash if re-signed ─────────
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", "unknown")
    timestamp  = now.isoformat()

    if is_stale and body.resign:
        new_declaration_hash = hashlib.sha256(
            f"{gen_id}|{user_id}|{ip_address}|{user_agent}"
            f"|{timestamp}|resigned"
            .encode()
        ).hexdigest()
        freshness_status = "resigned"
    else:
        new_declaration_hash = gen["declaration_hash"]
        freshness_status = "valid"

    # ── Step 9: Atomic DB UPDATE ──────────────────────────────────
    new_retry_count = current_retry_count + 1

    async with db_pool.acquire() as conn:
        async with conn.transaction():

            result = await conn.execute(
                """UPDATE generations
                   SET status               = 'export_queued',
                       export_retry_count   = $2,
                       declaration_hash     = $3,
                       declaration_accepted_at = CASE
                           WHEN $4 THEN NOW()
                           ELSE declaration_accepted_at
                       END,
                       updated_at           = NOW()
                   WHERE gen_id = $1
                     AND status = 'failed_export'""",
                gen_id,
                new_retry_count,
                new_declaration_hash,
                is_stale and body.resign,
            )

            if result == "UPDATE 0":
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error_code": "ECM-STATE-CONFLICT",
                        "message": "State changed concurrently.",
                    }
                )

            # Write compliance_log freshness_check row
            await conn.execute(
                """INSERT INTO compliance_log
                       (gen_id, check_type, result, details, created_at)
                   VALUES ($1, 'freshness_check', 'pass',
                           $2::jsonb, NOW())""",
                gen_id,
                json.dumps({
                    "freshness":              freshness_status,
                    "retry_count":            new_retry_count,
                    "declaration_age_seconds": int(declaration_age_s),
                }),
            )

    logger.info(
        f"retry-export gen={gen_id} user={user_id} "
        f"retry_count={new_retry_count} "
        f"freshness={freshness_status}"
    )

    # ── Step 10: SSE push export_queued ──────────────────────────
    try:
        sse_key = f"sse:{gen_id}"
        await redis_mgr.db0.lpush(
            sse_key,
            json.dumps({
                "type":        "state_change",
                "state":       "export_queued",
                "retry_count": new_retry_count,
            })
        )
        await redis_mgr.db0.expire(sse_key, 300)
    except Exception as e:
        logger.warning(f"SSE push failed gen={gen_id}: {e}")

    # ── Step 11: Enqueue worker_export (monotonic job ID) ─────────
    # Monotonic job ID = export:{gen_id}:{retry_count}
    # Prevents duplicate workers if user clicks retry twice rapidly
    arq_redis = await create_pool(
        RedisSettings.from_dsn(
            os.environ.get("REDIS_URL", "redis://localhost:6379/1")
        )
    )
    await arq_redis.enqueue_job(
        "worker_export",
        gen_id=gen_id,
        _queue_name="phase4_workers",
        _job_id=f"export:{gen_id}:{new_retry_count}",
    )
    await arq_redis.aclose()

    logger.info(
        f"worker_export re-enqueued gen={gen_id} "
        f"attempt={new_retry_count}"
    )

    return {
        "gen_id":             gen_id,
        "status":             "export_queued",
        "export_retry_count": new_retry_count,
        "freshness":          freshness_status,
        "message":            "Export retry queued.",
    }
