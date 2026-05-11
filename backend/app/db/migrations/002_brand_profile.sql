-- Migration 002: brand_profile on users
ALTER TABLE users ADD COLUMN IF NOT EXISTS 
  brand_profile JSONB NOT NULL DEFAULT '{}';

COMMENT ON COLUMN users.brand_profile IS 
  'Brand identity tokens: brand_name, primary_color, secondary_color, font_style, tone_of_voice';
