"""
[TDD-ENUMS] · Backend Python ENUMs
Fulfills: [PRD-FSM], [PRD-PLAYBOOK], [PRD-GREENZONE], [PRD-PRICING],
          [PRD-PAYMENT-FSM], [PRD-ERROR-COPY]

Mirrors Postgres ENUM types exactly. Each Python StrEnum value matches
the Postgres ENUM label verbatim. No invented values.
"""

from enum import StrEnum


class JobStatus(StrEnum):
    """22-state FSM. Mirrors Postgres `job_status` ENUM.
    Transitions enforced by `trg_enforce_state_transition` trigger."""

    # Phase 1: Ingestion
    QUEUED = "queued"
    EXTRACTING = "extracting"
    BRIEF_READY = "brief_ready"

    # Phase 2: Strategy
    SCRIPTING = "scripting"
    CRITIQUING = "critiquing"
    SAFETY_CHECKING = "safety_checking"
    SCRIPTS_READY = "scripts_ready"
    REGENERATING = "regenerating"

    # Phase 3: Intent Gate
    STRATEGY_PREVIEW = "strategy_preview"
    AWAITING_FUNDS = "awaiting_funds"
    FUNDS_LOCKED = "funds_locked"

    # Phase 4: Production
    RENDERING = "rendering"
    REFLECTING = "reflecting"
    COMPOSING = "composing"
    PREVIEW_READY = "preview_ready"
    EXPORT_QUEUED = "export_queued"
    EXPORT_READY = "export_ready"

    # Terminal Failures
    FAILED_CATEGORY = "failed_category"
    FAILED_COMPLIANCE = "failed_compliance"
    FAILED_SAFETY = "failed_safety"
    FAILED_RENDER = "failed_render"
    FAILED_EXPORT = "failed_export"


class PreTopupStatus(StrEnum):
    """Origin-screen preservation. Non-NULL IFF status='awaiting_funds'.
    Mirrors the constrained subset of `job_status` used by `pre_topup_status` column."""

    STRATEGY_PREVIEW = "strategy_preview"
    FAILED_EXPORT = "failed_export"


class PlanTier(StrEnum):
    """Pricing plan tiers. Mirrors Postgres `plan_tier` ENUM."""

    STARTER = "starter"
    ESSENTIAL = "essential"
    PRO = "pro"


class PaymentStatus(StrEnum):
    """Razorpay webhook FSM. Applies ONLY to wallet_transactions.type='topup'.
    Mirrors Postgres `payment_status` ENUM."""

    PENDING = "pending"
    CAPTURED = "captured"
    FAILED = "failed"
    REFUNDED = "refunded"


class WalletStatus(StrEnum):
    """Lock lifecycle FSM. Applies ONLY to wallet_transactions.type IN ('lock','consume','refund').
    Mirrors Postgres `wallet_status` ENUM."""

    LOCKED = "locked"
    CONSUMED = "consumed"
    REFUNDED = "refunded"


class AdFramework(StrEnum):
    """12-framework Dynamic Playbook. Mirrors Postgres `ad_framework` ENUM.
    Source: [PRD-PLAYBOOK]."""

    # Problem/Efficacy — logic angle
    PAS_MICRO = "pas_micro"
    CLINICAL_FLEX = "clinical_flex"
    MYTH_BUSTER = "myth_buster"

    # Sensory/Desire — emotion angle
    ASMR_TRIGGER = "asmr_trigger"
    USAGE_RITUAL = "usage_ritual"
    HYPER_LOCAL_COMFORT = "hyper_local_comfort"

    # Status/Value — logic or emotion angle
    SPEC_DROP_FLEX = "spec_drop_flex"
    PREMIUM_UPGRADE = "premium_upgrade"
    ROI_DURABILITY_FLEX = "roi_durability_flex"

    # Urgency/Conversion — conversion angle
    FESTIVAL_OCCASION_HOOK = "festival_occasion_hook"
    SCARCITY_DROP = "scarcity_drop"
    SOCIAL_PROOF = "social_proof"


class FrameworkAngle(StrEnum):
    """Derived angle from framework family. 3 canonical values."""

    LOGIC = "logic"
    EMOTION = "emotion"
    CONVERSION = "conversion"


# Canonical framework → angle mapping per [PRD-PLAYBOOK]
FRAMEWORK_ANGLE_MAP: dict[AdFramework, FrameworkAngle] = {
    AdFramework.PAS_MICRO: FrameworkAngle.LOGIC,
    AdFramework.CLINICAL_FLEX: FrameworkAngle.LOGIC,
    AdFramework.MYTH_BUSTER: FrameworkAngle.LOGIC,
    AdFramework.ASMR_TRIGGER: FrameworkAngle.EMOTION,
    AdFramework.USAGE_RITUAL: FrameworkAngle.EMOTION,
    AdFramework.HYPER_LOCAL_COMFORT: FrameworkAngle.EMOTION,
    AdFramework.SPEC_DROP_FLEX: FrameworkAngle.LOGIC,
    AdFramework.PREMIUM_UPGRADE: FrameworkAngle.EMOTION,
    AdFramework.ROI_DURABILITY_FLEX: FrameworkAngle.LOGIC,
    AdFramework.FESTIVAL_OCCASION_HOOK: FrameworkAngle.CONVERSION,
    AdFramework.SCARCITY_DROP: FrameworkAngle.CONVERSION,
    AdFramework.SOCIAL_PROOF: FrameworkAngle.CONVERSION,
}

# SAFE_TRIO — default fallback when evidence is weak per [PRD-PLAYBOOK]
SAFE_TRIO: tuple[AdFramework, AdFramework, AdFramework] = (
    AdFramework.PAS_MICRO,
    AdFramework.USAGE_RITUAL,
    AdFramework.SOCIAL_PROOF,
)


class GreenZoneCategory(StrEnum):
    """Approved product categories for I2V physics reliability.
    Mirrors Postgres `green_zone_category` ENUM."""

    D2C_BEAUTY = "d2c_beauty"
    PACKAGED_FOOD = "packaged_food"
    HARD_ACCESSORIES = "hard_accessories"
    ELECTRONICS = "electronics"
    HOME_KITCHEN = "home_kitchen"


class RedZoneCategory(StrEnum):
    """Rejected categories — I2V physics unreliable.
    Not stored in Postgres; used for classification gating only."""

    APPAREL = "apparel"
    FOOTWEAR = "footwear"
    FABRIC_HOME = "fabric_home"
    ORGANIC_PRODUCE = "organic_produce"


class SupportedTTSLanguage(StrEnum):
    """TTS language routing. Source: [TDD-WORKERS]-H."""

    HINDI = "hindi"
    HINGLISH = "hinglish"
    MARATHI = "marathi"
    PUNJABI = "punjabi"
    BENGALI = "bengali"
    TAMIL = "tamil"
    TELUGU = "telugu"
    ENGLISH = "english"


# TTS language → provider mapping per [TDD-WORKERS]-H
TTS_PROVIDER_MAP: dict[SupportedTTSLanguage, str] = {
    SupportedTTSLanguage.HINDI: "sarvam",
    SupportedTTSLanguage.HINGLISH: "sarvam",
    SupportedTTSLanguage.MARATHI: "sarvam",
    SupportedTTSLanguage.PUNJABI: "sarvam",
    SupportedTTSLanguage.BENGALI: "sarvam",
    SupportedTTSLanguage.TAMIL: "sarvam",
    SupportedTTSLanguage.TELUGU: "sarvam",
    SupportedTTSLanguage.ENGLISH: "elevenlabs",
}


class ECMCode(StrEnum):
    """Error Copy Matrix codes. Source: [PRD-ERROR-COPY].
    20 canonical error codes — each mapped to HTTP status, screen, and recovery."""

    FAILED_CATEGORY = "ECM-001"
    FAILED_COMPLIANCE = "ECM-002"
    FAILED_SAFETY = "ECM-003"
    FAILED_RENDER = "ECM-004"
    FAILED_EXPORT = "ECM-005"
    STARTER_RENDER_BLOCKED = "ECM-006"
    INSUFFICIENT_FUNDS = "ECM-007"
    CHAT_LIMIT_REACHED = "ECM-008"
    CHAT_CEILING_HIT = "ECM-009"
    CHAT_SAFETY_REJECT = "ECM-010"
    CHAT_COMPLIANCE_REJECT = "ECM-011"
    CROSS_TAB_CONFLICT = "ECM-012"
    HYDRATION_FAILED = "ECM-013"
    UPLOAD_TOO_LARGE = "ECM-014"
    FIRECRAWL_TIMEOUT = "ECM-015"
    C2PA_SIGN_FAILED = "ECM-016"
    DECLARATION_INVALID = "ECM-017"
    EXPORT_ASSETS_EXPIRED = "ECM-018"
    EXPORT_RETRY_EXHAUSTED = "ECM-019"
    DECLARATION_REFRESH_REQUIRED = "ECM-020"
