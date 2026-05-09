import uuid
import json
import logging
from typing import Annotated, Any
from fastapi import APIRouter, Request, Depends, HTTPException, Header
from pydantic import BaseModel, Field
from app.api.dependencies import idempotent, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["generations"])


# Valid rewind targets the user can request
VALID_REWIND_TARGETS = {
    "brief_ready",      # HD-3 → HD-2: change product brief
    "queued",           # HD-3 → HD-1: re-upload image entirely
    "scripts_ready",    # HD-4 → HD-3: change script selection
}

# Which statuses are allowed to request each target
ALLOWED_REWIND_MAP = {
    "brief_ready":   {"scripts_ready"},
    "queued":        {"scripts_ready"},
    "scripts_ready": {"strategy_ready", "awaiting_funds"},
}


class EditBackRequest(BaseModel):
    target_status: str = Field(
        ...,
        description="The status to rewind to. Must be a valid backwards transition."
    )


@router.post("/generations/{gen_id}/edit-back")
@idempotent(ttl=60, action_key="edit_back", cache_only_2xx=True)
async def edit_back(
    gen_id: str,
    req: EditBackRequest,
    request: Request,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    user: Annotated[Any, Depends(get_current_user)] = None,
) -> dict:
    """
    FSM rewind route. Handles 4 backward transition paths.
    actlock + idempotency cache owned by @idempotent decorator.
    Never moves state forward — only backwards.
    """
    db_pool = getattr(request.app.state, "db_pool",
                      getattr(request.app.state, "db", None))
    redis_mgr = request.app.state.redis_mgr
    redis_db0 = redis_mgr.db0

    # ── STEP 1: Validate target_status is a known rewind target ──
    if req.target_status not in VALID_REWIND_TARGETS:
        raise HTTPException(status_code=400, detail={
            "error_code": "ECM-002",
            "message": f"Invalid rewind target: {req.target_status}"
        })

    # ── STEP 2: DB fetch + ownership check ──
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT gen_id, status, pre_topup_status
               FROM generations
               WHERE gen_id = $1 AND user_id = $2""",
            uuid.UUID(gen_id), user.id
        )
    if not row:
        raise HTTPException(status_code=404, detail={"error_code": "ECM-001"})

    current_status = row["status"]

    # ── STEP 3: Validate transition is allowed ──
    allowed_sources = ALLOWED_REWIND_MAP.get(req.target_status, set())
    if current_status not in allowed_sources:
        raise HTTPException(status_code=409, detail={
            "error_code": "ECM-012",
            "message": f"Cannot rewind to {req.target_status} from {current_status}"
        })

    # ── STEP 4: Execute the correct rewind path ──

    if req.target_status == "brief_ready":
        # ── PATH A: HD-3 → HD-2 ──
        # User wants to change product brief. Keep image, null scripts onwards.
        async with db_pool.acquire() as conn:
            result = await conn.execute(
                """UPDATE generations SET
                       status             = 'brief_ready',
                       raw_scripts        = NULL,
                       critic_scores      = NULL,
                       safe_scripts       = NULL,
                       selected_script_id = NULL,
                       refined_script     = NULL,
                       chat_history       = '[]'::jsonb,
                       chat_turns_used    = 3,
                       strategy_card      = NULL,
                       motion             = NULL,
                       environment        = NULL,
                       b_roll_plan        = NULL,
                       updated_at         = NOW()
                   WHERE gen_id = $1
                     AND status = 'scripts_ready'""",
                uuid.UUID(gen_id)
            )
        if result == "UPDATE 0":
            raise HTTPException(status_code=409, detail={"error_code": "ECM-012"})

    elif req.target_status == "queued":
        # ── PATH B: HD-3 → HD-1 ──
        # User wants to re-upload image entirely. Null everything including brief.
        async with db_pool.acquire() as conn:
            result = await conn.execute(
                """UPDATE generations SET
                       status                  = 'queued',
                       isolated_png_url        = NULL,
                       confidence_score        = NULL,
                       product_brief           = NULL,
                       agent_motion_suggestion = NULL,
                       raw_scripts             = NULL,
                       critic_scores           = NULL,
                       safe_scripts            = NULL,
                       selected_script_id      = NULL,
                       refined_script          = NULL,
                       chat_history            = '[]'::jsonb,
                       chat_turns_used         = 3,
                       strategy_card           = NULL,
                       motion                  = NULL,
                       environment             = NULL,
                       b_roll_plan             = NULL,
                       regenerate_count        = 0,
                       updated_at              = NOW()
                   WHERE gen_id = $1
                     AND status = 'scripts_ready'""",
                uuid.UUID(gen_id)
            )
        if result == "UPDATE 0":
            raise HTTPException(status_code=409, detail={"error_code": "ECM-012"})

    elif req.target_status == "scripts_ready" and current_status == "strategy_ready":
        # ── PATH C: HD-4 → HD-3 (no wallet involved) ──
        # User didn't like strategy card. Null strategy only.
        async with db_pool.acquire() as conn:
            result = await conn.execute(
                """UPDATE generations SET
                       status        = 'scripts_ready',
                       strategy_card = NULL,
                       updated_at    = NOW()
                   WHERE gen_id = $1
                     AND status = 'strategy_ready'""",
                uuid.UUID(gen_id)
            )
        if result == "UPDATE 0":
            raise HTTPException(status_code=409, detail={"error_code": "ECM-012"})

    elif req.target_status == "scripts_ready" and current_status == "awaiting_funds":
        # ── PATH D: HD-4 → HD-3 (wallet refund required) ──
        # User backed out of payment. Must refund wallet lock via Lua script.
        # SQL trigger enforces: awaiting_funds exit MUST clear pre_topup_status
        # and MUST restore to pre_topup_status value (strategy_preview here).
        try:
            await redis_mgr.execute_wallet_refund(str(user.id), gen_id)
        except Exception as e:
            logger.error(
                "wallet_refund_failed",
                extra={"gen_id": gen_id, "error": str(e)}
            )
            raise HTTPException(status_code=503, detail={"error_code": "ECM-013"})

        # Trigger requires: pre_topup_status cleared + status = pre_topup_status value
        # pre_topup_status was 'strategy_preview' when entering awaiting_funds
        async with db_pool.acquire() as conn:
            result = await conn.execute(
                """UPDATE generations SET
                       status             = 'strategy_preview',
                       pre_topup_status   = NULL,
                       strategy_card      = NULL,
                       updated_at         = NOW()
                   WHERE gen_id = $1
                     AND status = 'awaiting_funds'
                     AND pre_topup_status = 'strategy_preview'""",
                uuid.UUID(gen_id)
            )
        if result == "UPDATE 0":
            raise HTTPException(status_code=409, detail={"error_code": "ECM-012"})

    # ── STEP 5: SSE push ──
    await redis_db0.lpush(
        f"sse:{gen_id}",
        json.dumps({"type": "state_change", "status": req.target_status})
    )
    await redis_db0.expire(f"sse:{gen_id}", 300)

    # ── STEP 6: Return ──
    logger.info(
        "edit_back_complete",
        extra={
            "gen_id": gen_id,
            "from_status": current_status,
            "to_status": req.target_status,
        }
    )
    return {
        "gen_id": gen_id,
        "previous_status": current_status,
        "status": req.target_status,
    }
