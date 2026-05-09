import uuid
import json
import logging
from typing import Annotated, Any, Optional
from fastapi import APIRouter, Request, Depends, HTTPException, Header
from pydantic import BaseModel, Field
from app.api.dependencies import idempotent, get_current_user
from app.infra_gateway import AdvertWiseException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["generations"])


class RegenerateRequest(BaseModel):
    # Optional chip change — user may change framework hint before regenerating
    # If None, re-runs with existing product_brief unchanged
    framework_hint: Optional[str] = Field(
        None,
        description="Optional new framework hint to store before re-running"
    )


@router.post("/generations/{gen_id}/regenerate")
@idempotent(ttl=60, action_key="regenerate", cache_only_2xx=True)
async def regenerate(
    gen_id: str,
    req: RegenerateRequest,
    request: Request,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    user: Annotated[Any, Depends(get_current_user)] = None,
) -> dict:
    """
    HD-3 chip-change re-run.
    Validates state, enforces 2-regeneration limit,
    nulls downstream fields, re-enqueues phase2_chain.
    actlock + idempotency cache owned by @idempotent decorator.
    """
    db_pool = getattr(request.app.state, "db_pool", 
                      getattr(request.app.state, "db", None))
    redis_mgr = request.app.state.redis_mgr
    redis_db0 = redis_mgr.db0
    redis_db5 = redis_mgr.db5

    # ── STEP 1: DB fetch + ownership check ──
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT gen_id, status, regenerate_count, product_brief
               FROM generations
               WHERE gen_id = $1 AND user_id = $2""",
            uuid.UUID(gen_id), user.id
        )
    if not row:
        raise HTTPException(status_code=404, detail={"error_code": "ECM-001"})

    # ── STEP 2: State guard ──
    if row["status"] != "scripts_ready":
        raise HTTPException(status_code=409, detail={"error_code": "ECM-012"})

    # ── STEP 3: Regeneration limit (max 2) ──
    if row["regenerate_count"] >= 2:
        raise HTTPException(status_code=429, detail={
            "error_code": "ECM-008",
            "message": "Maximum regenerations reached. Use Co-Pilot to refine or go back to edit brief."
        })

    # ── STEP 4: State-guarded UPDATE ──
    # Atomically:
    #   - Store optional framework_hint if provided
    #   - NULL all downstream fields (scripts, scores, chat, strategy)
    #   - Reset chat_turns_used to 3 (fresh turns on new scripts)
    #   - Increment regenerate_count
    #   - Transition status → regenerating
    async with db_pool.acquire() as conn:
        result = await conn.execute(
            """UPDATE generations SET
                   status              = 'regenerating',
                   framework_hint      = COALESCE($2, framework_hint),
                   raw_scripts         = NULL,
                   critic_scores       = NULL,
                   safe_scripts        = NULL,
                   selected_script_id  = NULL,
                   refined_script      = NULL,
                   chat_history        = '[]'::jsonb,
                   chat_turns_used     = 3,
                   motion              = NULL,
                   environment         = NULL,
                   b_roll_plan         = NULL,
                   strategy_card       = NULL,
                   regenerate_count    = regenerate_count + 1,
                   updated_at          = NOW()
               WHERE gen_id = $1
                 AND status = 'scripts_ready'
                 AND regenerate_count < 2""",
            uuid.UUID(gen_id),
            req.framework_hint,
        )
    # rowcount=0 means state drifted or limit was hit at DB level
    if result == "UPDATE 0":
        raise HTTPException(status_code=409, detail={"error_code": "ECM-012"})

    # ── STEP 5: ARQ enqueue phase2_chain ──
    try:
        import os
        from arq import create_pool
        from arq.connections import RedisSettings
        arq_redis = await create_pool(
            RedisSettings.from_dsn(
                os.environ.get("REDIS_URL", "redis://localhost:6379/1")
            )
        )
        await arq_redis.enqueue_job(
            "phase2_chain",
            gen_id=gen_id,
            _queue_name="phase1_to_3_workers",
        )
        await arq_redis.aclose()
    except Exception as e:
        # State is already regenerating — log but don't fail the request
        logger.error(
            "regenerate_arq_enqueue_failed",
            extra={"gen_id": gen_id, "error": str(e)}
        )

    # ── STEP 6: SSE push ──
    await redis_db0.lpush(
        f"sse:{gen_id}",
        json.dumps({"type": "state_change", "status": "regenerating"})
    )
    await redis_db0.expire(f"sse:{gen_id}", 300)

    # ── STEP 7: Return ──
    remaining = 2 - (row["regenerate_count"] + 1)
    return {
        "gen_id": gen_id,
        "status": "regenerating",
        "regenerate_count": row["regenerate_count"] + 1,
        "regenerations_remaining": remaining,
        "framework_hint_applied": req.framework_hint is not None,
    }
