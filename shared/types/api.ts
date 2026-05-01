/**
 * [TDD-TYPES]-A · API Contract Interfaces
 * Fulfills: [PRD-IDEMPOTENCY], [PRD-HD1]–[PRD-HD6], [TDD-API]-A
 *
 * HTTP request/response shapes for the L2 FastAPI surface.
 * Mirrors the Pydantic models in backend/app/models/ exactly.
 */

import type { AdFramework } from "./ad_framework";
import type { Script, ExportArtifacts } from "./generation";
import type { JobStatus } from "./job_status";
import type { ECMCode } from "./ecm_codes";

// ── POST /api/generations — Create generation ──
export interface CreateGenerationRequest {
  url?: string;
  // Image upload handled via multipart — not modeled here
}

export interface CreateGenerationResponse {
  gen_id: string;
  status: JobStatus;
}

// ── GET /api/generations/{gen_id} — Hydration ──
export interface StatusResponse {
  status: JobStatus;
  error_code: string | null;
  confidence_score: number | null;
}

// ── POST /api/generations/{gen_id}/advance ──
export interface AdvanceResponse {
  status: JobStatus;
}

// ── POST /api/generations/{gen_id}/selections ──
export interface SelectionsRequest {
  audience: string;
  benefit: string;
  emotion: string;
  language: string;
}

// ── POST /api/generations/{gen_id}/chat ──
export interface ChatRequestPayload {
  message: string;  // max 500 chars, max 20 words
}

export interface ChatResponsePayload {
  refined_script: Script;
  turns_used: number;
  turns_remaining: number;
  cost_inr: number;
}

// ── POST /api/generations/{gen_id}/edit-back ──
export interface EditBackRequest {
  target_state: "brief_ready" | "scripts_ready";
  target_field: "product" | "targeting" | "script" | "style";
}

export interface EditBackResponse {
  status: string;
  target_field: string;
}

// ── POST /api/generations/{gen_id}/approve-strategy ──
export interface ApproveStrategyRequest {
  approved: boolean;
}

export interface ApproveStrategyResponse {
  status: "funds_locked";
}

// ── POST /api/generations/{gen_id}/declaration ──
export interface DeclarationRequest {
  declaration_accepted: boolean;
  confirms_commercial_use: boolean;
  confirms_image_rights: boolean;
  confirms_ai_disclosure: boolean;
}

export interface DeclarationResponse {
  status: "export_queued";
}

// ── POST /api/generations/{gen_id}/retry-export ──
export interface RetryExportRequestPayload {
  declarations?: [boolean, boolean, boolean];
}

export interface RetryExportResponse {
  status: "export_queued";
  export_retry_count: number;
}

// ── POST /api/wallet/topup ──
export interface TopupRequest {
  plan: "essential" | "pro";
}

export interface TopupResponse {
  razorpay_order_id: string;
  amount_paise: number;
}

// ── POST /api/webhook/razorpay ──
export interface RazorpayWebhookResponse {
  ok: boolean;
  credits_applied?: number;
  restored_count?: number;
  dedup?: boolean;
  ignored?: boolean;
}

// ── POST /api/grievance ──
export interface GrievanceRequest {
  type: "content_violation" | "privacy" | "ip_infringement" | "other";
  gen_id?: string;
  description: string;
  contact_email: string;
}

export interface GrievanceResponse {
  ticket_id: number;
  slo_deadline_ts: string;
}

// ── SSE Event Payloads ──
export interface SSEStateChangeEvent {
  type: "state_change";
  state: JobStatus;
  preview_url?: string;
  exports?: ExportArtifacts;
  restore_screen?: string;
  pre_topup_status?: string | null;
  source?: string;
}

export interface SSEChatTurnEvent {
  type: "chat_turn";
  turns_used: number;
  turns_remaining: number;
}

export interface SSEEditBackEvent {
  type: "edit_back_complete";
  target_field: string;
  target_state: string;
}

export interface SSEErrorEvent {
  type: "render_failed" | "export_failed";
  state: JobStatus;
  error_code: ECMCode;
  failure_stage: string;
}

export type SSEEvent =
  | SSEStateChangeEvent
  | SSEChatTurnEvent
  | SSEEditBackEvent
  | SSEErrorEvent;

// ── Error Response Shape ──
export interface APIErrorResponse {
  error_code: ECMCode;
  message?: string;
  requires_declarations?: boolean;
}

// ── Idempotency Meta (server-side cache) ──
export interface IdempotencyMeta {
  status_code: number;
  body: Record<string, unknown>;
  created_at: string;
}
