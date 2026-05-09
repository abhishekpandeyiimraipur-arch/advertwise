from app.types.script import Script
from app.workers.copy import WorkerCopy
from app.services.compliance_gate import ComplianceGate
from app.services.cost_guard import CostGuard
from app.services.output_guard import OutputGuard
from app.services.prompt_catalog import PromptCatalog
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class CopilotResult:
    refined_script: Script          # from app/types/script.py
    cost_inr: float                 # actual cost of the LLM call
    model_used: str                 # which model gateway selected
    stages_traversed: list[str]     # for CI assertion in test_chat_chain_order.py

@dataclass 
class CopilotChainError:
    stage: str                      # which stage rejected
    error_code: str                 # ECM code string e.g. "ECM-011"
    http_status: int                # 400 / 422 / 429 / 503

class CopilotChain:
    def __init__(
        self,
        gateway,          # ModelGateway instance (app/infra_gateway.py)
        compliance_gate,  # ComplianceGate instance (app/services/compliance_gate.py)
        cost_guard,       # CostGuard instance (app/services/cost_guard.py)
        output_guard,     # OutputGuard instance (app/services/output_guard.py)
        prompt_catalog,   # PromptCatalog instance (app/services/prompt_catalog.py)
        db,               # asyncpg pool (passed in, not imported globally)
    ):
        self.gateway = gateway
        self.compliance_gate = compliance_gate
        self.cost_guard = cost_guard
        self.output_guard = output_guard
        self.prompt_catalog = prompt_catalog
        self.db = db

    async def run(
        self,
        gen_id: str,
        message: str,               # raw user message, ≤500 chars
        current_script: Script,     # the script to refine (refined or safe_scripts[selected])
        product_brief: dict,
        tts_language: str,
        plan_tier: str,
    ) -> CopilotResult | CopilotChainError:
        stages_traversed = []

        # STAGE 1 — compliance_gate
        stages_traversed.append("compliance_gate")
        result = await self.compliance_gate.check_input(message)
        if not result.safe:
            return CopilotChainError(stage="compliance_gate", error_code="ECM-011", http_status=400)

        # STAGE 2 — cost_guard_pre
        stages_traversed.append("cost_guard_pre")
        pre = await self.cost_guard.pre_check(gen_id, 0.08, plan_tier)
        if not pre.ok:
            return CopilotChainError(stage="cost_guard_pre", error_code="ECM-009", http_status=429)

        # STAGE 3 — llm_refine
        stages_traversed.append("llm_refine")
        try:
            worker = WorkerCopy(gateway=self.gateway, prompt_catalog=self.prompt_catalog, gen_id=gen_id)
            refined = await worker.refine(current_script, message, product_brief, tts_language)
        except Exception as e:
            logger.error("copilot_llm_error", extra={"gen_id": gen_id, "error": str(e)})
            return CopilotChainError(stage="llm_refine", error_code="ECM-013", http_status=503)

        last_cost = float(self.gateway.last_call_cost)
        model_used = self.gateway.last_model_used

        # STAGE 4 — cost_guard_record
        stages_traversed.append("cost_guard_record")
        await self.cost_guard.record(gen_id, last_cost, worker="chat", model_used=model_used)

        # STAGE 5 — output_guard
        stages_traversed.append("output_guard")
        og = await self.output_guard.check_output(refined.full_text)
        if not og.safe:
            # Sync Postgres ledger — Redis was already updated in Stage 4
            await self.db.execute(
                "UPDATE generations SET cogs_total = cogs_total + $2 WHERE gen_id = $1",
                gen_id, last_cost
            )
            return CopilotChainError(stage="output_guard", error_code="ECM-010", http_status=422)

        return CopilotResult(
            refined_script=refined,
            cost_inr=last_cost,
            model_used=model_used,
            stages_traversed=stages_traversed,
        )
