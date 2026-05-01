from fastapi import APIRouter, Request, Depends
from typing import Dict, Any
import logging
from app.gateway import idempotent, AdvertWiseException, ECMCode
from app.guards.compliance_gate import ComplianceGate
from app.guards.cost_guard import CostGuard

logger = logging.getLogger(__name__)
router = APIRouter()
compliance_gate = ComplianceGate()

@router.post("/generate")
@idempotent(ttl=300, action_key="generate", cache_only_2xx=True)
async def generate_stub(request: Request, payload: Dict[str, Any], gen_id: str = "mock-gen-123", user_id: str = "mock-user"):
    logger.info(f"==> Received /generate request for gen_id={gen_id}")
    
    # 1. ComplianceGate (FIRST in flow)
    text = payload.get("prompt", "")
    comp_res = await compliance_gate.check_input(text)
    logger.info(f"Compliance check result: safe={comp_res.safe}")
    if not comp_res.safe:
        raise AdvertWiseException(ECMCode.COMPLIANCE_FLAGGED, 400, {"reason": comp_res.reason})

    # 2. CostGuard pre_check
    redis_mgr = request.app.state.redis_mgr
    cost_guard = CostGuard(redis_db2=redis_mgr.db2, db_pool=None) # Mock db_pool as we don't insert here
    est_cost = 0.50
    plan_tier = "essential"
    cost_res = await cost_guard.pre_check(gen_id, est_cost, plan_tier)
    logger.info(f"CostGuard pre_check result: ok={cost_res.ok}")
    if not cost_res.ok:
        raise AdvertWiseException(ECMCode.BUDGET_LIMIT, 429)

    # 3. Redis Lua wallet_lock
    lock_success = await redis_mgr.execute_wallet_lock(user_id, gen_id, credits=1)
    logger.info(f"wallet_lock.lua execution result: {lock_success}")
    if lock_success == 0:
        raise AdvertWiseException(ECMCode.INSUFFICIENT_FUNDS, 402)

    # 4. Dummy response
    return {"status": "success", "gen_id": gen_id, "message": "Generation wired and validated!"}

@router.post("/chat")
@idempotent(ttl=300, action_key="chat", cache_only_2xx=True)
async def chat_stub(request: Request, payload: Dict[str, Any], gen_id: str = "mock-gen-chat", user_id: str = "mock-user"):
    logger.info(f"==> Received /chat request for gen_id={gen_id}")
    
    # 1. ComplianceGate
    text = payload.get("message", "")
    comp_res = await compliance_gate.check_input(text)
    if not comp_res.safe:
        raise AdvertWiseException(ECMCode.COMPLIANCE_FLAGGED, 400)

    return {"status": "success", "message": "Chat wired"}
