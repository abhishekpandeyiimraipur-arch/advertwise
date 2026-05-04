-- Nuclear reset — DEV ONLY. Drops all AdvertWise app objects.
BEGIN;

-- Drop triggers first
DROP TRIGGER IF EXISTS trg_status_history ON generations;
DROP TRIGGER IF EXISTS trg_enforce_state_transition ON generations;
DROP TRIGGER IF EXISTS trg_export_retry_monotonic ON generations;

-- Drop functions
DROP FUNCTION IF EXISTS record_status_history() CASCADE;
DROP FUNCTION IF EXISTS enforce_state_transition() CASCADE;
DROP FUNCTION IF EXISTS enforce_export_retry_monotonic() CASCADE;

-- Drop tables in reverse FK order
DROP TABLE IF EXISTS broll_clips CASCADE;
DROP TABLE IF EXISTS grievances CASCADE;
DROP TABLE IF EXISTS user_style_profiles CASCADE;
DROP TABLE IF EXISTS director_tips CASCADE;
DROP TABLE IF EXISTS user_signals CASCADE;
DROP TABLE IF EXISTS agent_traces CASCADE;
DROP TABLE IF EXISTS compliance_log CASCADE;
DROP TABLE IF EXISTS status_history CASCADE;
DROP TABLE IF EXISTS audit_log CASCADE;
DROP TABLE IF EXISTS wallet_transactions CASCADE;
DROP TABLE IF EXISTS generations CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS schema_migrations CASCADE;

-- Drop custom ENUMs
DROP TYPE IF EXISTS ad_framework CASCADE;
DROP TYPE IF EXISTS green_zone_category CASCADE;
DROP TYPE IF EXISTS wallet_status CASCADE;
DROP TYPE IF EXISTS payment_status CASCADE;
DROP TYPE IF EXISTS plan_tier CASCADE;
DROP TYPE IF EXISTS job_status CASCADE;

COMMIT;
