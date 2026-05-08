from fastapi import APIRouter, Request, Depends
from typing import Dict, Any
import logging

# Standardized Infrastructure Imports
# We use 'app.infra_gateway' to bypass the folder shadowing issue
from app.api.dependencies import idempotent
from app.infra_gateway import AdvertWiseException, ECMCode
from app.services.compliance_gate import ComplianceGate
from app.services.cost_guard import CostGuard

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize the ComplianceGate (Checks for prompt safety)
compliance_gate = ComplianceGate()

@router.post("/generate")
# IDEMPOTENCY: Prevents duplicate generations if the user clicks 'submit' twice
@idempotent(ttl=300, action_key="generate", cache_only_2xx=True)
async def generate_stub(request: Request, payload: Dict[str, Any], gen_id: str = "mock-gen-123", user_id: str = "mock-user"):
    """
    Primary endpoint for AdvertWise video generation. 
    Flow: Compliance -> Cost Check -> Wallet Lock -> Mock Success
    """
    logger.info(f"==> Received /generate request for gen_id={gen_id}")
    
    # --- 1. COMPLIANCE GATE (Foundational Requirement) ---
    # We check the prompt immediately to avoid wasting resources on unsafe content
    text = payload.get("prompt", "")
    comp_res = await compliance_gate.check_input(text)
    logger.info(f"Compliance check result: safe={comp_res.safe}")
    
    if not comp_res.safe:
        # Raises custom Exception mapped to ECM code for clear debugging
        raise AdvertWiseException(ECMCode.COMPLIANCE_FLAGGED, 400, {"reason": comp_res.reason})

    # --- 2. COST GUARD (Budget Control) ---
    # Verifies if the request fits within the user's plan limits
    redis_mgr = request.app.state.redis_mgr
    # Note: db_pool is None here as we are in a 'Stub' mode for Gate 1
    cost_guard = CostGuard(redis_db2=redis_mgr.db2, db_pool=None) 
    
    est_cost = 0.50 # Mocked cost for validation
    plan_tier = "essential"
    
    cost_res = await cost_guard.pre_check(gen_id, est_cost, plan_tier)
    logger.info(f"CostGuard pre_check result: ok={cost_res.ok}")
    
    if not cost_res.ok:
        raise AdvertWiseException(ECMCode.BUDGET_LIMIT, 429)

    # --- 3. REDIS LUA WALLET LOCK (Concurrency Safety) ---
    # Uses high-speed Lua scripting in Redis to lock credits before the heavy AI work begins
    # This prevents 'Double Spending' of credits
    lock_success = await redis_mgr.execute_wallet_lock(user_id, gen_id, credits=1)
    logger.info(f"wallet_lock.lua execution result: {lock_success}")
    
    if lock_success == 0:
        raise AdvertWiseException(ECMCode.INSUFFICIENT_FUNDS, 402)

    # --- 4. SUCCESS RESPONSE ---
    # If we reached here, the full backend wiring (Redis + Postgres logic) is validated
    return {
        "status": "success", 
        "gen_id": gen_id, 
        "message": "AdvertWise Foundation wired and validated!"
    }

@router.post("/chat")
@idempotent(ttl=300, action_key="chat", cache_only_2xx=True)
async def chat_stub(request: Request, payload: Dict[str, Any], gen_id: str = "mock-gen-chat", user_id: str = "mock-user"):
    """
    Lightweight chat endpoint for agentic interaction validation.
    """
    logger.info(f"==> Received /chat request for gen_id={gen_id}")
    
    # 1. ComplianceGate check for chat messages
    text = payload.get("message", "")
    comp_res = await compliance_gate.check_input(text)
    
    if not comp_res.safe:
        raise AdvertWiseException(ECMCode.COMPLIANCE_FLAGGED, 400)

    return {"status": "success", "message": "Chat module wired correctly"}