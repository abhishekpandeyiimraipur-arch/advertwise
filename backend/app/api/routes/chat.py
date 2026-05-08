from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from app.api.dependencies import idempotent, get_current_user, get_db
from app.infra_gateway import ModelGateway
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

# ── Module-level singletons (instantiated once, shared across requests) ──
gateway = ModelGateway()
compliance_gate = ComplianceGate()
cost_guard = CostGuard()
output_guard = OutputGuard()
prompt_catalog = PromptCatalog()

# ── Request model ──
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
