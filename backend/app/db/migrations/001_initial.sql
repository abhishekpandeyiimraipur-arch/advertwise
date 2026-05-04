BEGIN;

-- ═══════════════════════════════════════════
-- schema_migrations tracker
-- ═══════════════════════════════════════════
CREATE TABLE schema_migrations (
    filename    TEXT PRIMARY KEY,
    applied_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ═══════════════════════════════════════════
-- ENUMs
-- ═══════════════════════════════════════════
CREATE TYPE job_status AS ENUM (
    'queued', 'extracting', 'brief_ready',
    'scripting', 'critiquing', 'safety_checking',
    'scripts_ready', 'regenerating',
    'strategy_preview',
    'awaiting_funds',
    'funds_locked',
    'rendering', 'reflecting', 'composing', 'preview_ready',
    'export_queued', 'export_ready',
    'failed_category', 'failed_compliance', 'failed_safety',
    'failed_render', 'failed_export'
);

CREATE TYPE plan_tier AS ENUM ('starter', 'essential', 'pro');
CREATE TYPE payment_status AS ENUM ('pending', 'captured', 'failed', 'refunded');
CREATE TYPE wallet_status AS ENUM ('locked', 'consumed', 'refunded');

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

-- ═══════════════════════════════════════════
-- users
-- ═══════════════════════════════════════════
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
    beta_invited        BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_users_beta_invited ON users (beta_invited) WHERE beta_invited = TRUE;

-- ═══════════════════════════════════════════
-- generations
-- ═══════════════════════════════════════════
CREATE TABLE generations (
    gen_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(user_id),
    status              job_status DEFAULT 'queued',
    pre_topup_status    job_status NULL,
    plan_tier           plan_tier NOT NULL,

    -- Phase 1
    source_url          VARCHAR(2048),
    source_image_url    TEXT,
    isolated_png_url    TEXT,
    confidence_score    DECIMAL(3,2),
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

    -- Co-Pilot
    chat_history        JSONB DEFAULT '[]',
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
    cogs_total          DECIMAL(10,4) DEFAULT 0,

    -- Compliance
    declaration_accepted    BOOLEAN DEFAULT FALSE,
    declaration_accepted_at TIMESTAMPTZ,
    declaration_ip          INET,
    declaration_ua          TEXT,
    declaration_hash        VARCHAR(64),
    c2pa_manifest_hash      VARCHAR(64),

    -- Errors
    error_code          VARCHAR(50),
    error_message       TEXT,
    retry_count         INTEGER DEFAULT 0,

    -- DLQ
    dlq_dead_at         TIMESTAMPTZ,
    dlq_original_task   VARCHAR(50),

    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT chk_pre_topup_coupling CHECK (
        (status = 'awaiting_funds'
         AND pre_topup_status IN ('strategy_preview','failed_export'))
        OR (status <> 'awaiting_funds' AND pre_topup_status IS NULL)
    ),
    CONSTRAINT chk_routed_frameworks_cardinality CHECK (
        routed_frameworks IS NULL OR
        array_length(routed_frameworks, 1) = 3
    ),
    CONSTRAINT chk_product_brief_shape CHECK (
        product_brief IS NULL OR (
            jsonb_typeof(product_brief) = 'object'
            AND product_brief ? 'product_name'
            AND product_brief ? 'category'
            AND product_brief ? 'key_features'
        )
    )
);

-- ═══════════════════════════════════════════
-- wallet_transactions
-- ═══════════════════════════════════════════
CREATE TABLE wallet_transactions (
    txn_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(user_id),
    type                VARCHAR(20) NOT NULL
                        CHECK (type IN ('topup','lock','consume','refund','expire')),
    credits             INTEGER NOT NULL,
    razorpay_payment_id VARCHAR(100),
    payment_status      payment_status,
    status              wallet_status,
    gen_id              UUID REFERENCES generations(gen_id),
    created_at          TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT chk_wallet_status_coupling CHECK (
        (type = 'topup' AND status IS NULL AND payment_status IS NOT NULL)
        OR (type IN ('lock','consume','refund')
            AND payment_status IS NULL AND status IS NOT NULL)
        OR (type = 'expire' AND payment_status IS NULL AND status IS NULL)
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

-- ═══════════════════════════════════════════
-- audit_log (partitioned)
-- ═══════════════════════════════════════════
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

CREATE TABLE audit_log_2026
    PARTITION OF audit_log
    FOR VALUES FROM ('2026-01-01') TO ('2027-01-01');

-- ═══════════════════════════════════════════
-- status_history
-- ═══════════════════════════════════════════
CREATE TABLE status_history (
    id                      BIGSERIAL PRIMARY KEY,
    gen_id                  UUID NOT NULL REFERENCES generations(gen_id),
    from_status             job_status,
    to_status               job_status NOT NULL,
    from_pre_topup_status   job_status,
    to_pre_topup_status     job_status,
    changed_by              VARCHAR(50) DEFAULT 'system',
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

-- ═══════════════════════════════════════════
-- compliance_log
-- ═══════════════════════════════════════════
CREATE TABLE compliance_log (
    id          BIGSERIAL PRIMARY KEY,
    gen_id      UUID NOT NULL REFERENCES generations(gen_id),
    check_type  VARCHAR(50) NOT NULL,
    result      VARCHAR(20) NOT NULL CHECK (result IN ('pass','fail','warn')),
    details     JSONB,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ═══════════════════════════════════════════
-- agent_traces
-- ═══════════════════════════════════════════
CREATE TABLE agent_traces (
    id              BIGSERIAL PRIMARY KEY,
    gen_id          UUID NOT NULL REFERENCES generations(gen_id),
    worker          VARCHAR(50) NOT NULL,
    framework       ad_framework NULL,
    input_summary   JSONB,
    output_summary  JSONB,
    model_used      VARCHAR(100),
    tokens_in       INTEGER,
    tokens_out      INTEGER,
    cost_inr        DECIMAL(10,4),
    latency_ms      INTEGER,
    selection_reason TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ═══════════════════════════════════════════
-- user_signals
-- ═══════════════════════════════════════════
CREATE TABLE user_signals (
    id          BIGSERIAL PRIMARY KEY,
    gen_id      UUID NOT NULL REFERENCES generations(gen_id),
    user_id     UUID NOT NULL REFERENCES users(user_id),
    signal_type VARCHAR(50) NOT NULL,
    polarity    VARCHAR(20) NOT NULL CHECK (polarity IN ('positive','negative','neutral')),
    stage       VARCHAR(50) NOT NULL,
    signal_data JSONB,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ═══════════════════════════════════════════
-- user_style_profiles
-- ═══════════════════════════════════════════
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
    export_count        INTEGER DEFAULT 0,
    last_used_at        TIMESTAMPTZ DEFAULT NOW(),
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, category)
);

-- ═══════════════════════════════════════════
-- director_tips
-- ═══════════════════════════════════════════
CREATE TABLE director_tips (
    id                   BIGSERIAL PRIMARY KEY,
    category             VARCHAR(50) NOT NULL,
    tip_text             TEXT NOT NULL,
    tip_type             VARCHAR(20) NOT NULL
                         CHECK (tip_type IN ('lighting','environment','motion','general')),
    confidence_threshold DECIMAL(3,2) DEFAULT 0.85,
    active               BOOLEAN DEFAULT TRUE
);

-- ═══════════════════════════════════════════
-- grievances
-- ═══════════════════════════════════════════
CREATE TABLE grievances (
    id          BIGSERIAL PRIMARY KEY,
    user_id     UUID NOT NULL REFERENCES users(user_id),
    gen_id      UUID REFERENCES generations(gen_id),
    type        VARCHAR(50) NOT NULL,
    description TEXT,
    status      VARCHAR(20) DEFAULT 'open',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

-- ═══════════════════════════════════════════
-- broll_clips
-- ═══════════════════════════════════════════
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
        excludes_faces = TRUE AND excludes_hands = TRUE AND excludes_locations = TRUE
    )
);

-- ═══════════════════════════════════════════
-- FSM trigger — status_history auto-record
-- ═══════════════════════════════════════════
CREATE OR REPLACE FUNCTION record_status_history() RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status IS DISTINCT FROM NEW.status
       OR OLD.pre_topup_status IS DISTINCT FROM NEW.pre_topup_status THEN
        INSERT INTO status_history
            (gen_id, from_status, to_status,
             from_pre_topup_status, to_pre_topup_status)
        VALUES
            (NEW.gen_id, OLD.status, NEW.status,
             OLD.pre_topup_status, NEW.pre_topup_status);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_status_history
    AFTER UPDATE OF status, pre_topup_status ON generations
    FOR EACH ROW EXECUTE FUNCTION record_status_history();

-- ═══════════════════════════════════════════
-- Key indices
-- ═══════════════════════════════════════════
CREATE INDEX idx_generations_user_status
    ON generations (user_id, status, created_at DESC);

CREATE INDEX idx_generations_awaiting_funds
    ON generations (user_id)
    WHERE status = 'awaiting_funds';

CREATE INDEX idx_generations_dlq
    ON generations (dlq_dead_at DESC)
    WHERE dlq_dead_at IS NOT NULL;

CREATE INDEX idx_status_history_gen_created
    ON status_history (gen_id, created_at DESC);

CREATE INDEX idx_compliance_log_gen_check
    ON compliance_log (gen_id, check_type, created_at DESC);

CREATE INDEX idx_agent_traces_gen_framework
    ON agent_traces (gen_id, framework, created_at DESC);

INSERT INTO schema_migrations (filename) VALUES ('001_initial.sql');

COMMIT;
