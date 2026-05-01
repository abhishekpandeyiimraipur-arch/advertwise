"""
[TDD-TYPES]-B · Backend Pydantic Models
Fulfills: [PRD-COPILOT], [PRD-HD3], [PRD-HD4], [PRD-HD6],
          [PRD-FEATURES-CREATIVE], [PRD-FEATURES-INTENT],
          [PRD-FEATURES-PRODUCTION], [PRD-IDEMPOTENCY]

Strict request/response validation models for the L2 FastAPI surface.
All models use `extra='forbid'` to prevent data leaking into the system.

These models have absolute parity with the TypeScript interfaces
in shared/types/.
"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ──────────────────────────────────────────────────────────────────────
# Chat (HD-3 Co-Pilot — 5-stage chain)
# Source: [TDD-API]-C, [PRD-COPILOT]
# ──────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    """Client → server chat refinement payload.
    Max 500 chars, max 20 words per [PRD-COPILOT]."""

    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=500)

    @field_validator("message")
    @classmethod
    def validate_word_count(cls, v: str) -> str:
        if len(v.split()) > 20:
            raise ValueError("Chat message must be ≤ 20 words")
        return v


class ChatResponse(BaseModel):
    """Server → client chat turn result."""

    model_config = ConfigDict(extra="forbid")
    refined_script: dict
    turns_used: int
    turns_remaining: int
    cost_inr: float


# ──────────────────────────────────────────────────────────────────────
# Edit-Back (HD-4 [Edit] targets)
# Source: [TDD-API]-E
# ──────────────────────────────────────────────────────────────────────

class EditBackRequest(BaseModel):
    """4 valid edit targets: product, targeting, script, style.
    target_state determines the FSM rewind destination."""

    model_config = ConfigDict(extra="forbid")
    target_state: Literal["brief_ready", "scripts_ready"]
    target_field: Literal["product", "targeting", "script", "style"]


# ──────────────────────────────────────────────────────────────────────
# Approve Strategy (HD-4 credit gate)
# Source: [TDD-API]-D
# ──────────────────────────────────────────────────────────────────────

class ApproveStrategyRequest(BaseModel):
    """Simple boolean confirmation for the Lua wallet lock."""

    model_config = ConfigDict(extra="forbid")
    approved: bool = True


# ──────────────────────────────────────────────────────────────────────
# Selections (HD-3 chip/enum selections)
# Source: [TDD-TYPES]-B
# ──────────────────────────────────────────────────────────────────────

class SelectionsRequest(BaseModel):
    """HD-3 chip selections: audience, benefit, emotion, language."""

    model_config = ConfigDict(extra="forbid")
    audience: str
    benefit: str
    emotion: str
    language: str


# ──────────────────────────────────────────────────────────────────────
# Declaration (HD-6 provenance capture)
# Source: [TDD-API]-F, [PRD-HD6]
# ──────────────────────────────────────────────────────────────────────

class DeclarationRequest(BaseModel):
    """3 legally non-negotiable checkboxes. All must be True."""

    model_config = ConfigDict(extra="forbid")
    declaration_accepted: bool = True
    confirms_commercial_use: bool
    confirms_image_rights: bool
    confirms_ai_disclosure: bool

    @field_validator(
        "confirms_commercial_use",
        "confirms_image_rights",
        "confirms_ai_disclosure",
    )
    @classmethod
    def must_be_true(cls, v: bool) -> bool:
        if not v:
            raise ValueError("All three declarations must be checked")
        return v


# ──────────────────────────────────────────────────────────────────────
# Retry Export (HD-6 9-step atomic chain)
# Source: [TDD-API]-G, [PRD-HD6]
# ──────────────────────────────────────────────────────────────────────

class RetryExportRequest(BaseModel):
    """Optional declarations for stale-declaration re-sign (ECM-020).
    When present, must be exactly [True, True, True]."""

    model_config = ConfigDict(extra="forbid")
    declarations: Optional[list[bool]] = None

    @field_validator("declarations")
    @classmethod
    def validate_declarations(cls, v: Optional[list[bool]]) -> Optional[list[bool]]:
        if v is None:
            return v
        if len(v) != 3 or not all(v):
            raise ValueError("declarations must be [True, True, True] when present")
        return v


# ──────────────────────────────────────────────────────────────────────
# Framework Routing Output (Worker-COPY router result)
# Source: [TDD-TYPES]-B, [TDD-WORKERS]-C
# ──────────────────────────────────────────────────────────────────────

class FrameworkRoutingOutput(BaseModel):
    """LLM framework router output. Must select exactly 3 distinct frameworks.
    extra='forbid' — any leaked fields crash validation (stub safety)."""

    model_config = ConfigDict(extra="forbid")
    selected: list[str] = Field(min_length=3, max_length=3)
    rationale: dict[str, str]
    fallback_triggered: bool = False

    @field_validator("selected")
    @classmethod
    def must_be_distinct(cls, v: list[str]) -> list[str]:
        if len(set(v)) != 3:
            raise ValueError("Must select 3 distinct frameworks")
        return v


# ──────────────────────────────────────────────────────────────────────
# Razorpay Webhook
# Source: [TDD-API]-H
# ──────────────────────────────────────────────────────────────────────

class RazorpayWebhookPayload(BaseModel):
    """Razorpay webhook event payload. Only 'payment.captured' and
    'payment.failed' are processed; all others are ignored."""

    event: Literal["payment.captured", "payment.failed"]
    payload: dict


# ──────────────────────────────────────────────────────────────────────
# B-Roll Clip (deterministic planner output)
# Source: [TDD-WORKERS]-C2, [TDD-TYPES]-B
# ──────────────────────────────────────────────────────────────────────

class BRollClip(BaseModel):
    """Single B-roll clip from the deterministic planner.
    Up to 3 clips per generation (Postgres CHECK constraint)."""

    model_config = ConfigDict(extra="forbid")
    clip_id: str
    archetype: str
    duration_ms: int
    r2_url: str


# ──────────────────────────────────────────────────────────────────────
# Strategy Card Output (HD-4 data packet)
# Source: [TDD-WORKERS]-G, [TDD-TYPES]-B
# ──────────────────────────────────────────────────────────────────────

class StrategyCardOutput(BaseModel):
    """Server-side projection of [TDD-WORKERS]-G strategist output.
    Strict — extra='forbid' so leaked UI fields fail validation."""

    model_config = ConfigDict(extra="forbid")

    gen_id: str
    status: str
    selected_framework: str
    full_text: str
    rationale: str
    motion_archetype: int
    environment_preset: int

    # F-405: deterministic shot-mix from B-roll planner
    b_roll_plan: list[BRollClip] = Field(default_factory=list, max_length=3)

    is_refined: bool = False


# ──────────────────────────────────────────────────────────────────────
# Idempotency Meta (Redis DB5 cache shape)
# Source: [TDD-CONCURRENCY]-A
# ──────────────────────────────────────────────────────────────────────

class IdempotencyMeta(BaseModel):
    """Cached 2xx response for idempotent replay."""

    status_code: int
    body: dict
    created_at: str


# ──────────────────────────────────────────────────────────────────────
# Grievance Request (IT Rules 2026 takedown entry point)
# Source: [TDD-TAKEDOWN]-A
# ──────────────────────────────────────────────────────────────────────

class GrievanceRequest(BaseModel):
    """Public-facing grievance/takedown submission."""

    model_config = ConfigDict(extra="forbid")
    type: Literal["content_violation", "privacy", "ip_infringement", "other"]
    gen_id: Optional[str] = None
    description: str = Field(min_length=10, max_length=2000)
    contact_email: str = Field(min_length=5, max_length=320)
