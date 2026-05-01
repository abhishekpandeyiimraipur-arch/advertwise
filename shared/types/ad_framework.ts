/**
 * [TDD-TYPES]-A · AdFramework & FrameworkAngle — Dynamic Playbook ENUMs
 * Fulfills: [PRD-PLAYBOOK], [PRD-AGENTIC-DRAFT], [PRD-FEATURES-CREATIVE]
 *
 * Mirrors Postgres `ad_framework` ENUM and derived `framework_angle` exactly.
 * 12 framework families → 3 angles (logic, emotion, conversion).
 */

// ── 12-Framework ENUM (Postgres ad_framework) ──
export type AdFramework =
  // Problem/Efficacy — logic angle
  | "pas_micro"
  | "clinical_flex"
  | "myth_buster"
  // Sensory/Desire — emotion angle
  | "asmr_trigger"
  | "usage_ritual"
  | "hyper_local_comfort"
  // Status/Value — logic or emotion angle
  | "spec_drop_flex"
  | "premium_upgrade"
  | "roi_durability_flex"
  // Urgency/Conversion — conversion angle
  | "festival_occasion_hook"
  | "scarcity_drop"
  | "social_proof";

// ── Framework Angle (derived from framework family) ──
export type FrameworkAngle = "logic" | "emotion" | "conversion";

/**
 * Canonical framework → angle mapping.
 * Source of truth: [PRD-PLAYBOOK] table.
 */
export const FRAMEWORK_ANGLE_MAP: Record<AdFramework, FrameworkAngle> = {
  pas_micro: "logic",
  clinical_flex: "logic",
  myth_buster: "logic",
  asmr_trigger: "emotion",
  usage_ritual: "emotion",
  hyper_local_comfort: "emotion",
  spec_drop_flex: "logic",
  premium_upgrade: "emotion",
  roi_durability_flex: "logic",
  festival_occasion_hook: "conversion",
  scarcity_drop: "conversion",
  social_proof: "conversion",
};

/**
 * SAFE_TRIO — default fallback when evidence is weak.
 * Source: [PRD-PLAYBOOK] routing rule.
 */
export const SAFE_TRIO: [AdFramework, AdFramework, AdFramework] = [
  "pas_micro",
  "usage_ritual",
  "social_proof",
];

/**
 * All 12 AdFramework values as a const array for runtime validation.
 */
export const AD_FRAMEWORK_VALUES: AdFramework[] = [
  "pas_micro",
  "clinical_flex",
  "myth_buster",
  "asmr_trigger",
  "usage_ritual",
  "hyper_local_comfort",
  "spec_drop_flex",
  "premium_upgrade",
  "roi_durability_flex",
  "festival_occasion_hook",
  "scarcity_drop",
  "social_proof",
];

// ── Plan Tier (Postgres plan_tier) ──
export type PlanTier = "starter" | "essential" | "pro";

// ── Green Zone Category (Postgres green_zone_category) ──
export type GreenZoneCategory =
  | "d2c_beauty"
  | "packaged_food"
  | "hard_accessories"
  | "electronics"
  | "home_kitchen";

// ── Red Zone Category ──
export type RedZoneCategory =
  | "apparel"
  | "footwear"
  | "fabric_home"
  | "organic_produce";

// ── Payment Status (Postgres payment_status — Razorpay FSM) ──
export type PaymentStatus = "pending" | "captured" | "failed" | "refunded";

// ── Wallet Status (Postgres wallet_status — lock lifecycle) ──
export type WalletStatus = "locked" | "consumed" | "refunded";

// ── Supported TTS Languages ──
export type SupportedTTSLanguage =
  | "hindi"
  | "hinglish"
  | "marathi"
  | "punjabi"
  | "bengali"
  | "tamil"
  | "telugu"
  | "english";

/**
 * TTS language → provider mapping.
 * Source: [TDD-WORKERS]-H Worker-TTS.
 */
export const TTS_PROVIDER_MAP: Record<SupportedTTSLanguage, "sarvam" | "elevenlabs"> = {
  hindi: "sarvam",
  hinglish: "sarvam",
  marathi: "sarvam",
  punjabi: "sarvam",
  bengali: "sarvam",
  tamil: "sarvam",
  telugu: "sarvam",
  english: "elevenlabs",
};
