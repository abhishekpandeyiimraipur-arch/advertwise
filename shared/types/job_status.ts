/**
 * [TDD-TYPES]-A · JobStatus — 22-State FSM ENUM
 * Fulfills: [PRD-FSM], [PRD-PRETOPUP], [PRD-STATE-MATRIX]
 *
 * Mirrors Postgres `job_status` ENUM exactly.
 * UI is a reactive projection of this value via GET /api/generations/{gen_id}.
 */

// ── 22-State Machine ──
export type JobStatus =
  // Phase 1: Ingestion
  | "queued"              // HD-1 | POST /generate accepted
  | "extracting"          // HD-1 | Worker-EXTRACT running
  | "brief_ready"         // HD-2 | Phase 1 complete

  // Phase 2: Strategy
  | "scripting"           // HD-3 | Worker-COPY drafting
  | "critiquing"          // HD-3 | Worker-CRITIC scoring
  | "safety_checking"     // HD-3 | Worker-SAFETY batch
  | "scripts_ready"       // HD-3 | Phase 2 complete
  | "regenerating"        // HD-3 | chip-change re-run

  // Phase 3: Intent Gate
  | "strategy_preview"    // HD-4 | Worker-STRATEGIST complete
  | "awaiting_funds"      // HD-4 OR HD-6 | Lua lock failed → Top-Up Drawer overlay
  | "funds_locked"        // HD-5 | Lua lock succeeded (<1s transient)

  // Phase 4: Production
  | "rendering"           // HD-5 | TTS + I2V (asyncio.gather)
  | "reflecting"          // HD-5 | Worker-REFLECT SSIM
  | "composing"           // HD-5 | Worker-COMPOSE FFmpeg
  | "preview_ready"       // HD-6 | Preview live, declarations unsigned
  | "export_queued"       // HD-6 | Declaration signed, Worker-EXPORT running
  | "export_ready"        // HD-6 | C2PA signed, downloads active

  // Terminal Failures
  | "failed_category"     // HD-1 re-entry
  | "failed_compliance"   // HD-1 re-entry
  | "failed_safety"       // HD-3 inline
  | "failed_render"       // HD-5 inline recovery → HD-4 re-lock
  | "failed_export";      // HD-6 inline recovery → /retry-export

/**
 * pre_topup_status — origin-screen preservation column.
 * Non-NULL IFF status='awaiting_funds'.
 * 'strategy_preview' → HD-4 origin; 'failed_export' → HD-6 origin.
 */
export type PreTopupStatus = "strategy_preview" | "failed_export" | null;

/**
 * State → Screen mapping helper.
 * Deterministic projection from FSM state to resident screen.
 */
export type ScreenId = "HD-1" | "HD-2" | "HD-3" | "HD-4" | "HD-5" | "HD-6";

export function getScreenForStatus(
  status: JobStatus,
  preTopupStatus: PreTopupStatus
): ScreenId {
  switch (status) {
    case "queued":
    case "extracting":
    case "failed_category":
    case "failed_compliance":
      return "HD-1";

    case "brief_ready":
      return "HD-2";

    case "scripting":
    case "critiquing":
    case "safety_checking":
    case "scripts_ready":
    case "regenerating":
    case "failed_safety":
      return "HD-3";

    case "strategy_preview":
      return "HD-4";

    case "awaiting_funds":
      // Origin-preserving projection via pre_topup_status
      return preTopupStatus === "failed_export" ? "HD-6" : "HD-4";

    case "funds_locked":
    case "rendering":
    case "reflecting":
    case "composing":
    case "failed_render":
      return "HD-5";

    case "preview_ready":
    case "export_queued":
    case "export_ready":
    case "failed_export":
      return "HD-6";
  }
}
