-- 002_broll_seed.sql
-- Seeds broll_clips with real R2 assets.
-- Safe to re-run: ON CONFLICT DO NOTHING.
-- Run after 001_initial.sql.

BEGIN;

INSERT INTO broll_clips (clip_id, r2_url, duration_ms, archetype, category, excludes_faces, excludes_hands, excludes_locations, license_ref, is_active)
VALUES
  ('broll_11', 'Broll/abstract/Broll 11_std(abstract lights).mp4', 3000, 'abstract', 'd2c_beauty', true, true, true, 'advertwise-internal-v1', true),
  ('broll_12', 'Broll/abstract/Broll 12_std(abstarct ligh gradient).mp4', 3000, 'abstract', 'd2c_beauty', true, true, true, 'advertwise-internal-v1', true),
  ('broll_18', 'Broll/abstract/Broll 18_std(abstarct motion).mp4', 3000, 'abstract', 'd2c_beauty', true, true, true, 'advertwise-internal-v1', true),
  ('broll_09', 'Broll/abstract/Broll 9_std(abstract).mp4', 3000, 'abstract', 'd2c_beauty', true, true, true, 'advertwise-internal-v1', true),
  
  ('broll_10', 'Broll/motion/Broll 10_std(motion particles).mp4', 3000, 'motion', 'electronics', true, true, true, 'advertwise-internal-v1', true),
  ('broll_13', 'Broll/motion/Broll 13_std(motion).mp4', 3000, 'motion', 'electronics', true, true, true, 'advertwise-internal-v1', true),
  ('broll_16', 'Broll/motion/Broll 16_std(abstarct motion).mp4', 3000, 'motion', 'electronics', true, true, true, 'advertwise-internal-v1', true),

  ('broll_01', 'Broll/texture/Broll 1_std(motion  texture).mp4', 3000, 'texture', 'packaged_food', true, true, true, 'advertwise-internal-v1', true),
  ('broll_03', 'Broll/texture/Broll 3_std( water droplet).mp4', 3000, 'texture', 'packaged_food', true, true, true, 'advertwise-internal-v1', true),
  ('broll_05', 'Broll/texture/Broll 5_std(paper texture).mp4', 3000, 'texture', 'packaged_food', true, true, true, 'advertwise-internal-v1', true),
  ('broll_08', 'Broll/texture/Broll 8_std(water droplet).mp4', 3000, 'texture', 'packaged_food', true, true, true, 'advertwise-internal-v1', true),

  ('broll_02', 'Broll/packaging/Broll 2_std(packaging  logistics).mp4', 3000, 'packaging', 'packaged_food', true, true, true, 'advertwise-internal-v1', true),
  ('broll_06', 'Broll/packaging/Broll 6_std(packaging  logistics).mp4', 3000, 'packaging', 'packaged_food', true, true, true, 'advertwise-internal-v1', true),

  ('broll_17', 'Broll/warehouse/Broll 17_std(warehouse).mp4', 3000, 'warehouse', 'home_kitchen', true, true, true, 'advertwise-internal-v1', true),
  ('broll_04', 'Broll/warehouse/Broll 4_std(warehouse).mp4', 3000, 'warehouse', 'home_kitchen', true, true, true, 'advertwise-internal-v1', true),
  ('broll_07', 'Broll/warehouse/Broll 7_std(warehouse).mp4', 3000, 'warehouse', 'home_kitchen', true, true, true, 'advertwise-internal-v1', true)
ON CONFLICT (clip_id) DO NOTHING;

INSERT INTO schema_migrations (filename) VALUES ('002_broll_seed.sql')
ON CONFLICT (filename) DO NOTHING;

COMMIT;
