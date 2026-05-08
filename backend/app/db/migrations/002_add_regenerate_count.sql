-- Migration 002: Add regenerate_count to generations
-- Tracks how many times a user has regenerated scripts for a generation.
-- Max 2 regenerations enforced at API layer (ECM-008 on violation).
-- Append-only migration — no DROP, no RENAME, no ALTER TYPE.

ALTER TABLE generations
    ADD COLUMN IF NOT EXISTS regenerate_count INTEGER NOT NULL DEFAULT 0;

-- Enforce max at DB level as a secondary safety net
ALTER TABLE generations
    ADD CONSTRAINT chk_regenerate_count_max
    CHECK (regenerate_count <= 2);

COMMENT ON COLUMN generations.regenerate_count IS
    'Number of times phase2_chain has been re-enqueued via /regenerate. Max 2. Enforced at API + DB layer.';
