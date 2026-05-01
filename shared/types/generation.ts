/**
 * [TDD-TYPES]-A · Generation Interfaces — Core Business Objects
 * Fulfills: [PRD-FSM], [PRD-PRETOPUP], [PRD-FEATURES-CREATIVE],
 *           [PRD-FEATURES-INTENT], [PRD-FEATURES-PRODUCTION],
 *           [PRD-COPILOT], [PRD-AGENTIC-DRAFT]
 *
 * Canonical TypeScript interfaces matching the hydration payload
 * returned by GET /api/generations/{gen_id} per [TDD-API]-B.
 */

import type { AdFramework, FrameworkAngle } from "./ad_framework";
import type { JobStatus, PreTopupStatus } from "./job_status";

// ── Confidence Level (HD-2 visual signal) ──
export type ConfidenceLevel = "high" | "medium" | "low";

export function getConfidenceLevel(score: number): ConfidenceLevel {
  if (score >= 0.90) return "high";
  if (score >= 0.85) return "medium";
  return "low";
}

// ── Script (Phase 2 output — framework-tagged) ──
export interface Script {
  hook: string;
  body: string;
  cta: string;
  full_text: string;
  word_count: number;
  language_mix: "pure_hindi" | "hinglish" | "pure_english";
  framework: AdFramework;
  framework_angle: FrameworkAngle;
  framework_rationale: string;
  evidence_note: string;
  suggested_tone: string;
  critic_score?: number;
  critic_rationale?: string;
}

// ── Framework Routing Result (Worker-COPY output) ──
export interface FrameworkRoutingResult {
  selected: [AdFramework, AdFramework, AdFramework];
  default_trio_satisfied: boolean;
  fallback_triggered: boolean;
  routing_rationale: Record<AdFramework, string>;
}

// ── Chat Message (Copilot conversation history) ──
export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

// ── Chat Request (client → server) ──
export interface ChatRequest {
  message: string;
}

// ── Chat Response (server → client) ──
export interface ChatResponse {
  refined_script: Script;
  turns_used: number;
  turns_remaining: number;
  cost_inr: number;
}

// ── B-Roll Clip (deterministic planner output per [TDD-WORKERS]-C2) ──
export interface BRollClip {
  clip_id: string;
  archetype: string;
  duration_ms: number;
  r2_url: string;
}

// ── Strategy Card V3 (HD-4 projection per [TDD-WORKERS]-G) ──
export interface StrategyCardV3 {
  product_summary: any;
  script_summary: any;
  voice: any;
  motion: any;
  environment: any;
  provider: any;
  cost_estimate: any;
  compliance: any;
  chat_turns_used: number;
  chat_cost_inr: number;
  b_roll_plan: BRollClip[];
}

// ── DLQ Event (Dead Letter Queue per [TDD-DLQ]) ──
export interface DLQEvent {
  gen_id: string;
  failed_task: string;
  failed_at: string;
  recovery_action: "retry_full" | "retry_export" | "refund_only" | "abandon";
}

// ── Retry Export Request (client → server) ──
export interface RetryExportRequest {
  declarations?: [boolean, boolean, boolean];
}

// ── Export Artifacts ──
export interface ExportArtifacts {
  square_url?: string;
  vertical_url?: string;
  c2pa_manifest_hash?: string;
  finalized_at?: string;
}

// ── GenerationState — Canonical hydration interface per [TDD-API]-B ──
export interface GenerationState {
  gen_id: string;
  status: JobStatus;
  pre_topup_status: PreTopupStatus;
  routed_frameworks?: AdFramework[];
  raw_scripts?: Script[];
  selected_script_id?: number;
  refined_script?: Script;
  chat_turns_used: number;
  export_retry_count: number;
  preview_url?: string;
  exports?: ExportArtifacts;
}
