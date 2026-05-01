-- ==============================================================================
-- Migration: 001_initial.sql
-- Description: Core Schema Initialization for AdvertWise
-- Applies: [TDD-SCHEMA], [TDD-FSM], [TDD-MIGRATION-SAFETY]
-- Requirements: 
--  - pgvector enabled
--  - All ENUMs implemented
--  - JSONB shape constraints on `generations`
--  - Partitioned `audit_log`
--  - FSM transitions via triggers
-- ==============================================================================

BEGIN;

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;

-- ═══════════════════════════════════════════════════════════════════════
-- ENUM Definitions
-- ═══════════════════════════════════════════════════════════════════════

CREATE TYPE job_status AS ENUM (
    -- Phase 1
    'queued', 'extracting', 'brief_ready',
    -- Phase 2
    'scripting', 'critiquing', 'safety_checking', 'scripts_ready', 'regenerating',
    -- Phase 3
    'strategy_preview',
    'awaiting_funds',
    'funds_locked',
    -- Phase 4
    'rendering', 'reflecting', 'composing', 'preview_ready',
    'export_queued', 'export_ready',
    -- Terminal
    'failed_category', 'failed_compliance', 'failed_safety',
    'failed_render', 'failed_export'
);

CREATE TYPE plan_tier AS ENUM ('starter', 'essential', 'pro');

CREATE TYPE payment_status AS ENUM ('pending', 'captured', 'failed', 'refunded');

CREATE TYPE wallet_status AS ENUM (
    'locked',
    'consumed',
    'refunded'
);

CREATE TYPE ad_framework AS ENUM (
    'pas_micro', 'clinical_flex', 'myth_buster',
    'asmr_trigger', 'usage_ritual', 'hyper_local_comfort',
    'spec_drop_flex', 'premium_upgrade', 'roi_durability_flex',
    'festival_occasion_hook', 'scarcity_drop', 'social_proof'
);

CREATE TYPE green_zone_category AS ENUM (
    'd2c_beauty', 'packaged_food', 'hard_accessories',
    'electronics', 'home_kitchen'
);

-- ═══════════════════════════════════════════════════════════════════════
-- TABLE: users
-- ═══════════════════════════════════════════════════════════════════════
CREATE TABLE users (
    user_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    google_id           VARCHAR(255) UNIQUE NOT NULL,
    email               VARCHAR(255) UNIQUE NOT NULL,
    name                VARCHAR(255),
    plan_tier           plan_tier DEFAULT 'starter',
    credits_remaining   INTEGER DEFAULT 0,
    plan_expires_at     TIMESTAMPTZ,
    generation_count    INTEGER DEFAULT 0,
    session_version     INTEGER DEFAULT 1,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════════════════
-- TABLE: generations (Pillar 4: Deep Module / JSONB god-table)
-- ═══════════════════════════════════════════════════════════════════════
CREATE TABLE generations (
    gen_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(user_id),
    status              job_status DEFAULT 'queued',
    pre_topup_status    job_status NULL,
    plan_tier           plan_tier NOT NULL,

    -- Phase 1
    source_url          VARCHAR(2048) CHECK (char_length(source_url) <= 2048),
    source_image_url    TEXT,
    isolated_png_url    TEXT,
    confidence_score    DECIMAL(3, 2),
    product_brief       JSONB,
    product_shape       VARCHAR(20),
    agent_crop_suggestion TEXT,
    agent_motion_suggestion INTEGER,

    -- Phase 2
    campaign_brief      JSONB,
    routed_frameworks   ad_framework[],
    routing_rationale   JSONB,
    raw_scripts         JSONB,
    critic_scores       JSONB,
    safety_flags        JSONB,
    safe_scripts        JSONB,
    selected_script_id  INTEGER,
    motion_archetype_id INTEGER,
    environment_preset_id INTEGER,
    b_roll_plan         JSONB DEFAULT '[]',

    -- Co-Pilot Chat
    chat_history        JSONB DEFAULT '[]' CHECK (jsonb_typeof(chat_history) = 'array'
                                                  AND jsonb_array_length(chat_history) <= 6),
    chat_turns_used     INTEGER DEFAULT 0 CHECK (chat_turns_used BETWEEN 0 AND 3),
    refined_script      JSONB,

    -- Phase 3
    strategy_card       JSONB,
    strategy_approved_at TIMESTAMPTZ,

    -- Phase 4
    tts_language        VARCHAR(20) DEFAULT 'hindi',
    tts_audio_url       TEXT,
    i2v_candidates      JSONB,
    selected_i2v_url    TEXT,
    preview_url         TEXT,
    exports             JSONB,
    fallback_events     JSONB DEFAULT '[]',

    export_retry_count  INTEGER NOT NULL DEFAULT 0 CHECK (export_retry_count BETWEEN 0 AND 3),

    -- Economics
    cogs_total          DECIMAL(10, 4) DEFAULT 0,

    -- Compliance
    declaration_accepted BOOLEAN DEFAULT FALSE,
    declaration_accepted_at TIMESTAMPTZ,
    declaration_ip      INET,
    declaration_ua      TEXT,
    declaration_hash    VARCHAR(64),
    c2pa_manifest_hash  VARCHAR(64),

    -- Errors & DLQ
    error_code          VARCHAR(50),
    error_message       TEXT,
    retry_count         INTEGER DEFAULT 0,
    dlq_dead_at         TIMESTAMPTZ,
    dlq_original_task   VARCHAR(50),

    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT chk_pre_topup_coupling CHECK (
        (status = 'awaiting_funds' AND pre_topup_status IN ('strategy_preview','failed_export'))
        OR
        (status <> 'awaiting_funds' AND pre_topup_status IS NULL)
    ),

    CONSTRAINT chk_routed_frameworks_cardinality CHECK (
        routed_frameworks IS NULL OR
        (array_length(routed_frameworks, 1) = 3 AND
         array_length(routed_frameworks, 1) = (SELECT COUNT(DISTINCT v) FROM unnest(routed_frameworks) v))
    ),

    CONSTRAINT chk_product_brief_shape CHECK (
        product_brief IS NULL OR (
            jsonb_typeof(product_brief) = 'object'
            AND product_brief ? 'product_name'
            AND product_brief ? 'category'
            AND product_brief ? 'key_features'
            AND jsonb_typeof(product_brief->'key_features') = 'array'
        )
    ),
    CONSTRAINT chk_exports_shape CHECK (
        exports IS NULL OR (
            jsonb_typeof(exports) = 'object'
            AND exports ? 'square_url'
            AND exports ? 'vertical_url'
            AND exports ? 'c2pa_manifest_hash'
            AND exports ? 'finalized_at'
        )
    ),
    CONSTRAINT chk_strategy_card_shape CHECK (
        strategy_card IS NULL OR (
            jsonb_typeof(strategy_card) = 'object'
            AND strategy_card ? 'product_summary'
            AND strategy_card ? 'script_summary'
            AND strategy_card ? 'voice'
            AND strategy_card ? 'motion'
            AND strategy_card ? 'environment'
            AND strategy_card ? 'compliance'
        )
    ),
    CONSTRAINT chk_b_roll_plan_shape CHECK (
        jsonb_typeof(b_roll_plan) = 'array'
        AND jsonb_array_length(b_roll_plan) <= 3
    )
);

-- ═══════════════════════════════════════════════════════════════════════
-- TABLE: wallet_transactions
-- ═══════════════════════════════════════════════════════════════════════
CREATE TABLE wallet_transactions (
    txn_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(user_id),
    type                VARCHAR(20) NOT NULL
                        CHECK (type IN ('topup', 'lock', 'consume', 'refund', 'expire')),
    credits             INTEGER NOT NULL,
    razorpay_payment_id VARCHAR(100),

    payment_status      payment_status,
    status              wallet_status,

    gen_id              UUID REFERENCES generations(gen_id),
    created_at          TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT chk_wallet_status_coupling CHECK (
        (type = 'topup'  AND status IS NULL AND payment_status IS NOT NULL)
        OR
        (type IN ('lock','consume','refund') AND payment_status IS NULL AND status IS NOT NULL)
        OR
        (type = 'expire' AND payment_status IS NULL AND status IS NULL)
    )
);

CREATE UNIQUE INDEX ux_wallet_topup_dedup
    ON wallet_transactions (razorpay_payment_id)
    WHERE type = 'topup' AND payment_status = 'captured';

CREATE UNIQUE INDEX ux_wallet_active_lock
    ON wallet_transactions (gen_id)
    WHERE status = 'locked';

CREATE UNIQUE INDEX ux_wallet_refund_dedup
    ON wallet_transactions (gen_id, type)
    WHERE type = 'refund';

-- ═══════════════════════════════════════════════════════════════════════
-- TABLE: audit_log (Partitioned)
-- ═══════════════════════════════════════════════════════════════════════
CREATE TABLE audit_log (
    id                  BIGSERIAL,
    gen_id              UUID,
    user_id             UUID,
    action              VARCHAR(100) NOT NULL,
    payload             JSONB,
    ip_address          INET,
    user_agent          TEXT,
    declaration_sha256  VARCHAR(64),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- Default initial partition covering some buffer for initial system start.
CREATE TABLE audit_log_y2026m04 PARTITION OF audit_log
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
    
CREATE TABLE audit_log_y2026m05 PARTITION OF audit_log
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');

-- ═══════════════════════════════════════════════════════════════════════
-- TABLE: status_history
-- ═══════════════════════════════════════════════════════════════════════
CREATE TABLE status_history (
    id                  BIGSERIAL PRIMARY KEY,
    gen_id              UUID NOT NULL REFERENCES generations(gen_id),
    from_status         job_status,
    to_status           job_status NOT NULL,
    from_pre_topup_status job_status,
    to_pre_topup_status   job_status,
    changed_by          VARCHAR(50) DEFAULT 'system',
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════════════════
-- TABLE: compliance_log
-- ═══════════════════════════════════════════════════════════════════════
CREATE TABLE compliance_log (
    id                  BIGSERIAL PRIMARY KEY,
    gen_id              UUID NOT NULL REFERENCES generations(gen_id),
    check_type          VARCHAR(50) NOT NULL,
    result              VARCHAR(20) NOT NULL CHECK (result IN ('pass', 'fail', 'warn')),
    details             JSONB,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════════════════
-- TABLE: agent_traces
-- ═══════════════════════════════════════════════════════════════════════
CREATE TABLE agent_traces (
    id                  BIGSERIAL PRIMARY KEY,
    gen_id              UUID NOT NULL REFERENCES generations(gen_id),
    worker              VARCHAR(50) NOT NULL,
    framework           ad_framework NULL,
    input_summary       JSONB,
    output_summary      JSONB,
    model_used          VARCHAR(100),
    tokens_in           INTEGER,
    tokens_out          INTEGER,
    cost_inr            DECIMAL(10, 4),
    latency_ms          INTEGER,
    selection_reason    TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════════════════
-- TABLE: user_signals
-- ═══════════════════════════════════════════════════════════════════════
CREATE TABLE user_signals (
    id                  BIGSERIAL PRIMARY KEY,
    gen_id              UUID NOT NULL REFERENCES generations(gen_id),
    user_id             UUID NOT NULL REFERENCES users(user_id),
    signal_type         VARCHAR(50) NOT NULL,
    polarity            VARCHAR(20) NOT NULL CHECK (polarity IN ('positive', 'negative', 'neutral')),
    stage               VARCHAR(50) NOT NULL,
    signal_data         JSONB,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════════════════
-- TABLE: user_style_profiles (pgvector)
-- ═══════════════════════════════════════════════════════════════════════
CREATE TABLE user_style_profiles (
    id                  BIGSERIAL PRIMARY KEY,
    user_id             UUID NOT NULL REFERENCES users(user_id),
    category            VARCHAR(50) NOT NULL,
    audience            VARCHAR(50),
    benefit             VARCHAR(50),
    emotion             VARCHAR(50),
    language            VARCHAR(20),
    motion_archetype    INTEGER,
    environment_preset  INTEGER,
    preferred_framework ad_framework,
    embedding           vector(1536),
    export_count        INTEGER DEFAULT 0,
    last_used_at        TIMESTAMPTZ DEFAULT NOW(),
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, category)
);

-- ═══════════════════════════════════════════════════════════════════════
-- TABLE: director_tips
-- ═══════════════════════════════════════════════════════════════════════
CREATE TABLE director_tips (
    id                  BIGSERIAL PRIMARY KEY,
    category            VARCHAR(50) NOT NULL,
    tip_text            TEXT NOT NULL,
    tip_type            VARCHAR(20) NOT NULL CHECK (tip_type IN ('lighting', 'environment', 'motion', 'general')),
    confidence_threshold DECIMAL(3,2) DEFAULT 0.85,
    active              BOOLEAN DEFAULT TRUE
);

-- ═══════════════════════════════════════════════════════════════════════
-- TABLE: grievances
-- ═══════════════════════════════════════════════════════════════════════
CREATE TABLE grievances (
    id                  BIGSERIAL PRIMARY KEY,
    user_id             UUID NOT NULL REFERENCES users(user_id),
    gen_id              UUID REFERENCES generations(gen_id),
    type                VARCHAR(50) NOT NULL,
    description         TEXT,
    status              VARCHAR(20) DEFAULT 'open',
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    resolved_at         TIMESTAMPTZ
);

-- ═══════════════════════════════════════════════════════════════════════
-- TABLE: broll_clips
-- ═══════════════════════════════════════════════════════════════════════
CREATE TABLE broll_clips (
    clip_id             VARCHAR(20) PRIMARY KEY,
    archetype           VARCHAR(50) NOT NULL,
    category            green_zone_category NOT NULL,
    duration_ms         INTEGER NOT NULL CHECK (duration_ms BETWEEN 1000 AND 5000),
    r2_url              TEXT NOT NULL,
    excludes_faces      BOOLEAN NOT NULL DEFAULT TRUE,
    excludes_hands      BOOLEAN NOT NULL DEFAULT TRUE,
    excludes_locations  BOOLEAN NOT NULL DEFAULT TRUE,
    license_ref         VARCHAR(100),
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT chk_broll_safety CHECK (
        excludes_faces = TRUE
        AND excludes_hands = TRUE
        AND excludes_locations = TRUE
    )
);
CREATE INDEX idx_broll_archetype_category
    ON broll_clips (archetype, category) WHERE is_active = TRUE;

-- ═══════════════════════════════════════════════════════════════════════
-- TRIGGERS & FUNCTIONS
-- ═══════════════════════════════════════════════════════════════════════

-- State Transition Trigger
CREATE OR REPLACE FUNCTION enforce_state_transition() RETURNS TRIGGER AS $$
DECLARE
    valid_transitions JSONB := '{
        "queued":            ["extracting", "failed_category", "failed_compliance"],
        "extracting":        ["brief_ready", "failed_category", "failed_compliance"],
        "brief_ready":       ["scripting"],
        "scripting":         ["critiquing", "failed_safety"],
        "critiquing":        ["safety_checking"],
        "safety_checking":   ["scripts_ready", "failed_safety"],
        "scripts_ready":     ["strategy_preview", "regenerating", "brief_ready"],
        "regenerating":      ["scripts_ready", "failed_safety"],
        "strategy_preview":  ["funds_locked", "awaiting_funds", "scripts_ready", "brief_ready"],
        "awaiting_funds":    ["strategy_preview", "failed_export"],
        "funds_locked":      ["rendering", "failed_render"],
        "rendering":         ["reflecting", "composing", "failed_render"],
        "reflecting":        ["composing", "rendering", "failed_render"],
        "composing":         ["preview_ready", "failed_render"],
        "preview_ready":     ["export_queued"],
        "export_queued":     ["export_ready", "failed_export"],
        "export_ready":      [],
        "failed_category":   [],
        "failed_compliance": [],
        "failed_safety":     ["scripting"],
        "failed_render":     ["strategy_preview"],
        "failed_export":     ["export_queued", "awaiting_funds"]
    }'::jsonb;
    allowed JSONB;
BEGIN
    -- Allow no-op (idempotent UPDATEs)
    IF OLD.status = NEW.status THEN
        IF OLD.pre_topup_status IS DISTINCT FROM NEW.pre_topup_status THEN
            RAISE EXCEPTION 'pre_topup_status mutated without status transition (% -> %)',
                OLD.pre_topup_status, NEW.pre_topup_status;
        END IF;
        RETURN NEW;
    END IF;

    -- Validate transition
    allowed := valid_transitions -> OLD.status::text;
    IF allowed IS NULL OR NOT allowed ? NEW.status::text THEN
        RAISE EXCEPTION 'Invalid state transition: % -> %', OLD.status, NEW.status;
    END IF;

    -- pre_topup_status paired-write invariants
    -- Rule 1: any transition INTO awaiting_funds requires NEW.pre_topup_status set correctly.
    IF NEW.status = 'awaiting_funds' THEN
        IF OLD.status = 'strategy_preview' AND NEW.pre_topup_status IS DISTINCT FROM 'strategy_preview' THEN
            RAISE EXCEPTION 'strategy_preview -> awaiting_funds requires pre_topup_status=strategy_preview (got %)',
                NEW.pre_topup_status;
        END IF;
        IF OLD.status = 'failed_export' AND NEW.pre_topup_status IS DISTINCT FROM 'failed_export' THEN
            RAISE EXCEPTION 'failed_export -> awaiting_funds requires pre_topup_status=failed_export (got %)',
                NEW.pre_topup_status;
        END IF;
    END IF;

    -- Rule 2: any transition OUT of awaiting_funds must clear pre_topup_status AND restore to snapshot.
    IF OLD.status = 'awaiting_funds' THEN
        IF NEW.pre_topup_status IS NOT NULL THEN
            RAISE EXCEPTION 'Transition out of awaiting_funds must clear pre_topup_status (got %)',
                NEW.pre_topup_status;
        END IF;
        IF OLD.pre_topup_status = 'strategy_preview' AND NEW.status <> 'strategy_preview' THEN
            RAISE EXCEPTION 'awaiting_funds(pre=strategy_preview) must restore to strategy_preview (got %)', NEW.status;
        END IF;
        IF OLD.pre_topup_status = 'failed_export' AND NEW.status <> 'failed_export' THEN
            RAISE EXCEPTION 'awaiting_funds(pre=failed_export) must restore to failed_export (got %)', NEW.status;
        END IF;
    END IF;

    -- Rule 3: any other transition must have NEW.pre_topup_status NULL.
    IF NEW.status <> 'awaiting_funds' AND NEW.pre_topup_status IS NOT NULL THEN
        RAISE EXCEPTION 'pre_topup_status must be NULL when status<>awaiting_funds (got status=%, pre_topup_status=%)',
            NEW.status, NEW.pre_topup_status;
    END IF;

    NEW.updated_at := NOW();

    -- Capture status history with pre_topup_status snapshots for forensics
    INSERT INTO status_history (gen_id, from_status, to_status, from_pre_topup_status, to_pre_topup_status)
    VALUES (NEW.gen_id, OLD.status, NEW.status, OLD.pre_topup_status, NEW.pre_topup_status);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_enforce_state_transition
    BEFORE UPDATE OF status, pre_topup_status ON generations
    FOR EACH ROW EXECUTE FUNCTION enforce_state_transition();

-- Monotonicity guard on export_retry_count
CREATE OR REPLACE FUNCTION enforce_export_retry_monotonic() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.export_retry_count < OLD.export_retry_count THEN
        RAISE EXCEPTION 'export_retry_count cannot decrease (% -> %)',
            OLD.export_retry_count, NEW.export_retry_count;
    END IF;
    IF NEW.export_retry_count > OLD.export_retry_count + 1 THEN
        RAISE EXCEPTION 'export_retry_count must increment by exactly 1 (% -> %)',
            OLD.export_retry_count, NEW.export_retry_count;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_export_retry_monotonic
    BEFORE UPDATE OF export_retry_count ON generations
    FOR EACH ROW EXECUTE FUNCTION enforce_export_retry_monotonic();

COMMIT;
