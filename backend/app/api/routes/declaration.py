"""
/declaration route — IT Rules 2026 compliance declaration.
[TDD-API]-F

POST /api/generations/{gen_id}/declaration

ONLY legal enqueue point for worker_export in the codebase.
Captures provenance, writes compliance records,
transitions preview_ready → export_queued.
"""
import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from arq import create_pool
from arq.connections import RedisSettings

from app.api.dependencies import idempotent, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


class DeclarationRequest(BaseModel):
    commercial_use: bool
    image_rights:   bool
    ai_disclosure:  bool


@router.post("/generations/{gen_id}/declaration")
@idempotent(ttl=300, action_key="declaration", cache_only_2xx=True)
async def submit_declaration(
    gen_id: str,
    body: DeclarationRequest,
    request: Request,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: Annotated[Any, Depends(get_current_user)] = None,
):
    """
    IT Rules 2026 compliance declaration.
    Captures provenance, writes audit trail,
    transitions to export_queued, enqueues worker_export.

    Returns 200 with export_queued state on success.
    Returns 409 if not in preview_ready state.
    Returns 422 if any checkbox is False.
    """
    db_pool = request.app.state.db_pool
    user_id = str(current_user.id)

    # ── Step 1: Validate all 3 checkboxes ────────────────────────
    # All must be True — any False → 422 (L7 invariant)
    if not (body.commercial_use and
            body.image_rights and
            body.ai_disclosure):
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "ECM-DECLARATION-INCOMPLETE",
                "message": (
                    "All three declaration checkboxes must be "
                    "accepted to proceed."
                ),
            }
        )

    # ── Step 2: Verify generation ownership + state ───────────────
    async with db_pool.acquire() as conn:
        gen = await conn.fetchrow(
            """SELECT gen_id, user_id, status, plan_tier
               FROM generations
               WHERE gen_id = $1
                 AND user_id = $2""",
            gen_id, user_id,
        )

    if not gen:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "ECM-001", "message": "Generation not found."}
        )

    if gen["status"] != "preview_ready":
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "ECM-STATE-CONFLICT",
                "message": (
                    f"Generation is in state '{gen['status']}'. "
                    f"Expected 'preview_ready'."
                ),
            }
        )

    # ── Step 3: Capture declaration provenance ────────────────────
    ip_address = request.client.host if request.client else None  # NULL-safe for INET column
    user_agent = request.headers.get("user-agent", "unknown")
    timestamp  = datetime.now(timezone.utc).isoformat()

    # SHA-256 of provenance chain per TDD [TDD-API]-F
    declaration_sha256 = hashlib.sha256(
        f"{gen_id}|{user_id}|{ip_address}|{user_agent}|{timestamp}"
        .encode()
    ).hexdigest()

    # ── Step 4: Atomic DB writes ──────────────────────────────────
    async with db_pool.acquire() as conn:
        async with conn.transaction():

            # 4a. Update generations row — declaration + FSM transition
            result = await conn.execute(
                """UPDATE generations
                   SET declaration_accepted    = TRUE,
                       declaration_accepted_at = NOW(),
                       declaration_hash        = $2,
                       status                  = 'export_queued',
                       updated_at              = NOW()
                   WHERE gen_id = $1
                     AND status = 'preview_ready'""",
                gen_id,
                declaration_sha256,
            )

            if result == "UPDATE 0":
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error_code": "ECM-STATE-CONFLICT",
                        "message": "State changed concurrently.",
                    }
                )

            # 4b. Write compliance_log row
            # Schema: gen_id, check_type, result ('pass'/'fail'/'warn'),
            #         details JSONB — no user_id/ip_address columns
            await conn.execute(
                """INSERT INTO compliance_log
                       (gen_id, check_type, result, details, created_at)
                   VALUES ($1, 'declaration_capture', 'pass',
                           $2::jsonb, NOW())""",
                gen_id,
                json.dumps({
                    "commercial_use":     body.commercial_use,
                    "image_rights":       body.image_rights,
                    "ai_disclosure":      body.ai_disclosure,
                    "declaration_sha256": declaration_sha256,
                    "user_id":            user_id,
                    "ip_address":         ip_address,
                }),
            )

            # 4c. Write audit_log row (immutable record)
            # Schema: gen_id, user_id, action, payload JSONB,
            #         ip_address INET, user_agent, declaration_sha256
            await conn.execute(
                """INSERT INTO audit_log
                       (gen_id, user_id, action, payload,
                        ip_address, user_agent,
                        declaration_sha256, created_at)
                   VALUES ($1, $2, 'declaration_accepted',
                           $3::jsonb, $4::inet, $5, $6, NOW())""",
                gen_id,
                user_id,
                json.dumps({
                    "commercial_use": body.commercial_use,
                    "image_rights":   body.image_rights,
                    "ai_disclosure":  body.ai_disclosure,
                    "timestamp":      timestamp,
                }),
                ip_address,
                user_agent,
                declaration_sha256,
            )

    logger.info(
        f"Declaration accepted gen={gen_id} user={user_id} "
        f"hash={declaration_sha256[:16]}..."
    )

    # ── Step 5: SSE push export_queued ───────────────────────────
    try:
        redis_mgr = request.app.state.redis_mgr
        sse_key   = f"sse:{gen_id}"
        await redis_mgr.db0.lpush(
            sse_key,
            json.dumps({
                "type":  "state_change",
                "state": "export_queued",
            })
        )
        await redis_mgr.db0.expire(sse_key, 300)
    except Exception as e:
        logger.warning(f"SSE push failed gen={gen_id}: {e}")

    # ── Step 6: Enqueue worker_export ────────────────────────────
    # ONLY legal enqueue point for worker_export in the codebase.
    # Runs AFTER transaction commits — never inside transaction.
    arq_redis = await create_pool(
        RedisSettings.from_dsn(
            os.environ.get("REDIS_URL", "redis://localhost:6379/1")
        )
    )
    await arq_redis.enqueue_job(
        "worker_export",
        gen_id=gen_id,
        _queue_name="phase4_workers",
        _job_id=f"export:{gen_id}",
    )
    await arq_redis.aclose()

    logger.info(f"worker_export enqueued gen={gen_id}")

    return {
        "gen_id":            gen_id,
        "status":            "export_queued",
        "declaration_hash":  declaration_sha256,
        "message":           "Declaration accepted. Export in progress.",
    }
