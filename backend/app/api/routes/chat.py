from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from app.api.dependencies import idempotent, get_current_user, get_db
from app.gateway import ModelGateway
from app.services.compliance_gate import ComplianceGate
from app.services.cost_guard import CostGuard
from app.services.output_guard import OutputGuard
from app.services.prompt_catalog import PromptCatalog
from app.workers.copilot import CopilotChain, CopilotChainError, CopilotResult
from app.types.script import Script
import json, logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Module-level singletons ──
gateway = ModelGateway()
compliance_gate = ComplianceGate()
prompt_catalog = PromptCatalog()

# ── Request model ──
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)

@router.post("/api/generations/{gen_id}/chat")
@idempotent(ttl=300, action_key="chat", cache_only_2xx=True)
async def chat(
    gen_id: UUID,
    req: ChatRequest,
    request: Request,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    user=Depends(get_current_user),
    db=Depends(get_db),
) -> dict:
    """
    5-stage Co-Pilot refinement turn.
    actlock + idempotency cache owned by @idempotent decorator.
    COMMIT owned by this route. Chain stages owned by CopilotChain.
    """

    # ── STEP 1: DB fetch with state validation ──
    gen = await db.fetchrow(
        """SELECT status, chat_turns_used, refined_script, safe_scripts,
                  selected_script_id, product_brief, tts_language, plan_tier
           FROM generations
           WHERE gen_id=$1 AND user_id=$2
           FOR UPDATE""",
        gen_id, user.id
    )
    if not gen:
        raise HTTPException(status_code=404, detail={"error_code": "ECM-001"})
    if gen["status"] != "scripts_ready":
        raise HTTPException(status_code=409, detail={"error_code": "ECM-012"})
    if gen["chat_turns_used"] >= 3:
        raise HTTPException(status_code=429, detail={"error_code": "ECM-008"})

    # ── STEP 2: Resolve current_script ──
    # Use refined_script if a prior turn exists.
    # Otherwise fall back to top-scored safe script.
    if gen["refined_script"]:
        current_script = Script(**json.loads(gen["refined_script"]))
    else:
        idx = (gen["selected_script_id"] or 1) - 1
        safe_scripts = json.loads(gen["safe_scripts"])
        current_script = Script(**safe_scripts[idx])

    # ── STEP 3: Instantiate and run CopilotChain ──
    cost_guard = CostGuard(
        redis_db2=request.app.state.redis_db2,
        db_pool=request.app.state.db_pool,
    )
    output_guard = OutputGuard(gateway=gateway)
    chain = CopilotChain(
        gateway=gateway,
        compliance_gate=compliance_gate,
        cost_guard=cost_guard,
        output_guard=output_guard,
        prompt_catalog=prompt_catalog,
        db=db,
    )
    chain_result = await chain.run(
        gen_id=str(gen_id),
        message=req.message,
        current_script=current_script,
        product_brief=json.loads(gen["product_brief"]),
        tts_language=gen["tts_language"],
        plan_tier=gen["plan_tier"],
    )

    # ── STEP 4: Handle CopilotChainError ──
    if isinstance(chain_result, CopilotChainError):
        logger.warning(
            "copilot_chain_rejected",
            extra={
                "gen_id": str(gen_id),
                "stage": chain_result.stage,
                "error_code": chain_result.error_code,
            }
        )
        raise HTTPException(
            status_code=chain_result.http_status,
            detail={"error_code": chain_result.error_code},
        )

    # ── STEP 5: Atomic state-guarded COMMIT ──
    # WHERE clause double-guards against state drift and turn overflow.
    # If another request snuck in, rowcount=0 → 409. Never silently double-commit.
    result = await db.fetchrow(
        """UPDATE generations SET
               refined_script  = $2::jsonb,
               chat_turns_used = chat_turns_used + 1,
               chat_history    = chat_history || $3::jsonb || $4::jsonb,
               cogs_total      = cogs_total + $5
           WHERE gen_id=$1
             AND status='scripts_ready'
             AND chat_turns_used < 3
           RETURNING chat_turns_used""",
        gen_id,
        json.dumps(chain_result.refined_script.__dict__),
        json.dumps({
            "role": "user",
            "content": req.message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }),
        json.dumps({
            "role": "assistant",
            "content": chain_result.refined_script.full_text,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }),
        chain_result.cost_inr,
    )

    # State drifted between fetch and commit → 409
    if not result:
        raise HTTPException(status_code=409, detail={"error_code": "ECM-012"})

    # ── STEP 6: Audit log (for CI assertion in test_chat_chain_order.py) ──
    logger.info(
        "chat_chain_complete",
        extra={
            "gen_id": str(gen_id),
            "chain_stages_traversed": chain_result.stages_traversed,
            "turns_used": result["chat_turns_used"],
            "cost_inr": chain_result.cost_inr,
            "model_used": chain_result.model_used,
        }
    )

    # ── STEP 7: Return (decorator caches this dict for ttl=300s) ──
    return {
        "refined_script": chain_result.refined_script.__dict__,
        "turns_used": result["chat_turns_used"],
        "turns_remaining": 3 - result["chat_turns_used"],
        "cost_inr": chain_result.cost_inr,
    }
