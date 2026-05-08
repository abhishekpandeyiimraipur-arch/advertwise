import uuid
import json
import logging
import os
from typing import Annotated, Any
from fastapi import APIRouter, Request, Depends, HTTPException, Header
from app.api.dependencies import idempotent, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["generations"])


@router.post("/generations/{gen_id}/approve-strategy")
@idempotent(ttl=300, action_key="approve-strategy", cache_only_2xx=True)
async def approve_strategy(
    gen_id: str,
    request: Request,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    user: Annotated[Any, Depends(get_current_user)] = None,
) -> dict:
    """
    HD-4 credit lock and phase4 dispatch.

    Happy path:
      strategy_preview → funds_locked → phase4_coordinator enqueued

    No-credit path:
      strategy_preview → awaiting_funds (pre_topup_status='strategy_preview')
      SQL trigger enforces paired write — cannot be done in two UPDATEs.

    Starter plan:
      → 403 ECM-006 (upgrade required)

    actlock + idempotency cache owned by @idempotent decorator.
    """
    db_pool = getattr(request.app.state, "db_pool",
                      getattr(request.app.state, "db", None))
    redis_mgr = request.app.state.redis_mgr
    redis_db0 = redis_mgr.db0

    # ── STEP 1: DB fetch + ownership + state guard ──
    async with db_pool.acquire() as conn:
        gen = await conn.fetchrow(
            """SELECT status, plan_tier
               FROM generations
               WHERE gen_id = $1 AND user_id = $2
               FOR UPDATE""",
            uuid.UUID(gen_id), user.id
        )
    if not gen:
        raise HTTPException(status_code=404, detail={"error_code": "ECM-001"})
    if gen["status"] != "strategy_preview":
        raise HTTPException(status_code=409, detail={"error_code": "ECM-012"})

    # ── STEP 2: Starter plan guard ──
    # Starter users cannot render. They must upgrade first.
    # Strategy card shows "Upgrade" button — this 403 is the server enforcement.
    if gen["plan_tier"] == "starter":
        raise HTTPException(status_code=403, detail={"error_code": "ECM-006"})

    # ── STEP 3: Ledger-first atomic credit lock ──
    # INSERT wallet row BEFORE Lua lock (audit trail first).
    # If Lua fails → DELETE the optimistic ledger row.
    # Both operations wrapped in a single DB transaction.
    async with db_pool.acquire() as conn:
        async with conn.transaction():

            # 3a: Insert optimistic ledger row
            txn_id = await conn.fetchval(
                """INSERT INTO wallet_transactions
                       (user_id, type, credits, status, gen_id)
                   VALUES ($1, 'lock', -1, 'locked'::wallet_status, $2)
                   RETURNING txn_id""",
                user.id, uuid.UUID(gen_id)
            )

            # 3b: Execute Redis Lua wallet lock (atomic debit)
            # Returns 1 = success (credits deducted)
            # Returns 0 = failure (insufficient credits)
            try:
                lua_result = await redis_mgr.execute_wallet_lock(
                    str(user.id), gen_id, credits=1
                )
            except Exception as e:
                logger.error(
                    "wallet_lock_lua_error",
                    extra={"gen_id": gen_id, "error": str(e)}
                )
                raise HTTPException(
                    status_code=503,
                    detail={"error_code": "ECM-013"}
                )

            if lua_result == 0:
                # ── NO-CREDIT PATH ──
                # Delete the optimistic ledger row — lock never happened
                await conn.execute(
                    "DELETE FROM wallet_transactions WHERE txn_id = $1",
                    txn_id
                )
                # Atomic paired write — SQL trigger REQUIRES pre_topup_status
                # to be set in the SAME UPDATE as status='awaiting_funds'
                # Cannot be two separate UPDATEs — trigger will reject.
                await conn.execute(
                    """UPDATE generations SET
                           status           = 'awaiting_funds',
                           pre_topup_status = 'strategy_preview',
                           updated_at       = NOW()
                       WHERE gen_id = $1
                         AND status = 'strategy_preview'""",
                    uuid.UUID(gen_id)
                )
                # SSE push — frontend opens payment drawer
                await redis_db0.lpush(
                    f"sse:{gen_id}",
                    json.dumps({
                        "type": "state_change",
                        "status": "awaiting_funds",
                        "restore_screen": "HD-4"
                    })
                )
                await redis_db0.expire(f"sse:{gen_id}", 300)
                raise HTTPException(
                    status_code=402,
                    detail={"error_code": "ECM-007"}
                )

            # ── HAPPY PATH ──
            # Lua lock succeeded — transition to funds_locked
            await conn.execute(
                """UPDATE generations SET
                       status     = 'funds_locked',
                       updated_at = NOW()
                   WHERE gen_id = $1
                     AND status  = 'strategy_preview'""",
                uuid.UUID(gen_id)
            )

    # ── STEP 4: Dispatch phase4_coordinator (AFTER transaction commits) ──
    # Must be outside the transaction block — enqueue only on commit success.
    try:
        from arq import create_pool
        from arq.connections import RedisSettings
        arq_redis = await create_pool(
            RedisSettings.from_dsn(
                os.environ.get("REDIS_URL", "redis://localhost:6379/1")
            )
        )
        await arq_redis.enqueue_job(
            "phase4_coordinator",
            gen_id=gen_id,
            _queue_name="phase4_workers",
            _job_id=f"phase4:{gen_id}",
        )
        await arq_redis.aclose()
    except Exception as e:
        # funds_locked state is already committed.
        # Log but do not fail — phase4 can be re-triggered via retry.
        logger.error(
            "phase4_enqueue_failed",
            extra={"gen_id": gen_id, "error": str(e)}
        )

    # ── STEP 5: SSE push + return ──
    await redis_db0.lpush(
        f"sse:{gen_id}",
        json.dumps({"type": "state_change", "status": "funds_locked"})
    )
    await redis_db0.expire(f"sse:{gen_id}", 300)

    logger.info(
        "approve_strategy_complete",
        extra={"gen_id": gen_id, "user_id": str(user.id)}
    )
    return {
        "gen_id": gen_id,
        "status": "funds_locked",
    }
