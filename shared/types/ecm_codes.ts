/**
 * [TDD-TYPES]-A · ECM Error Codes — Error Copy Matrix
 * Fulfills: [PRD-ERROR-MATRIX], [PRD-ERROR-COPY], [PRD-ERROR-MAP]
 *
 * Canonical error codes extracted from [PRD-ERROR-COPY].
 * 20 codes — each maps to a specific HTTP status, screen, and recovery path.
 */

// ── ECM Error Code Union ──
export type ECMCode =
  | "ECM-001"   // failed_category — Product Not Supported
  | "ECM-002"   // failed_compliance — Content Flagged
  | "ECM-003"   // failed_safety — Scripts Need Adjustment
  | "ECM-004"   // failed_render — Rendering Failed
  | "ECM-005"   // failed_export — Export Failed — Retry Available
  | "ECM-006"   // STARTER_RENDER_BLOCKED — Upgrade to Render
  | "ECM-007"   // INSUFFICIENT_FUNDS — Add Credits to Render
  | "ECM-008"   // CHAT_LIMIT_REACHED — Chat Limit Reached
  | "ECM-009"   // CHAT_CEILING_HIT — Budget Limit
  | "ECM-010"   // CHAT_SAFETY_REJECT — Refinement Flagged
  | "ECM-011"   // CHAT_COMPLIANCE_REJECT — Invalid Input
  | "ECM-012"   // CROSS_TAB_CONFLICT — Action In Progress
  | "ECM-013"   // HYDRATION_FAILED — Connection Lost
  | "ECM-014"   // UPLOAD_TOO_LARGE — File Too Large
  | "ECM-015"   // FIRECRAWL_TIMEOUT — Scraping Timeout
  | "ECM-016"   // C2PA_SIGN_FAILED — Signing Failed
  | "ECM-017"   // DECLARATION_INVALID — Declaration Required
  | "ECM-018"   // EXPORT_ASSETS_EXPIRED — Preview Assets Expired
  | "ECM-019"   // EXPORT_RETRY_EXHAUSTED — Export Retry Limit Reached
  | "ECM-020";  // DECLARATION_REFRESH_REQUIRED — Declaration Refresh Required

// ── Error Metadata ──
export interface ECMErrorMeta {
  code: ECMCode;
  httpStatus: number | null;  // null for SSE/DLQ-delivered errors
  title: string;
  body: string;
  recovery: string;
  landingScreen: string;
}

/**
 * Canonical ECM Error Map — per [PRD-ERROR-COPY].
 * Immutable reference for frontend error rendering.
 */
export const ECM_ERROR_MAP: Record<ECMCode, ECMErrorMeta> = {
  "ECM-001": {
    code: "ECM-001",
    httpStatus: null,
    title: "Product Not Supported",
    body: "We don't support this product category yet. We work best with beauty, food, accessories, electronics, and home products.",
    recovery: "[Start Over]",
    landingScreen: "HD-1",
  },
  "ECM-002": {
    code: "ECM-002",
    httpStatus: null,
    title: "Content Flagged",
    body: "This content didn't pass our safety check required by IT Rules 2026. Please try a different product.",
    recovery: "[Start Over]",
    landingScreen: "HD-1",
  },
  "ECM-003": {
    code: "ECM-003",
    httpStatus: null,
    title: "Scripts Need Adjustment",
    body: "Our brand safety check flagged all scripts. We're regenerating with adjusted parameters…",
    recovery: "Auto-retry 1×; else [Back to Scripts]",
    landingScreen: "HD-3",
  },
  "ECM-004": {
    code: "ECM-004",
    httpStatus: null,
    title: "Rendering Failed",
    body: "Video rendering failed after retries. Your credit has been refunded to your wallet.",
    recovery: "[↻ Try Again] · [← Back to Strategy]",
    landingScreen: "HD-5",
  },
  "ECM-005": {
    code: "ECM-005",
    httpStatus: null,
    title: "Export Failed — Retry Available",
    body: "Export processing failed. Your credit has been refunded. Your preview is intact — we just need to retry the final signing step. This uses 1 credit (no re-rendering needed).",
    recovery: "[↻ Retry Export · Use 1 Credit]",
    landingScreen: "HD-6",
  },
  "ECM-006": {
    code: "ECM-006",
    httpStatus: 403,
    title: "Upgrade to Render",
    body: "The free plan lets you preview your strategy. Upgrade to Essential or Pro to render your video.",
    recovery: "[View Plans]",
    landingScreen: "HD-4",
  },
  "ECM-007": {
    code: "ECM-007",
    httpStatus: 402,
    title: "Add Credits to Render",
    body: "You need at least 1 credit to render. Top up your wallet — your strategy is saved.",
    recovery: "[Add Credits]",
    landingScreen: "HD-4 or HD-6",
  },
  "ECM-008": {
    code: "ECM-008",
    httpStatus: 429,
    title: "Chat Limit Reached",
    body: "You've used all 3 refinement turns for this video. Review your script and continue.",
    recovery: "(Disabled)",
    landingScreen: "HD-3",
  },
  "ECM-009": {
    code: "ECM-009",
    httpStatus: 429,
    title: "Budget Limit",
    body: "Another chat turn would exceed this generation's cost ceiling. Continue with your current script.",
    recovery: "(Disabled)",
    landingScreen: "HD-3",
  },
  "ECM-010": {
    code: "ECM-010",
    httpStatus: 422,
    title: "Refinement Flagged",
    body: "That refinement didn't pass our brand safety filter. Try a different instruction. (This turn was not counted.)",
    recovery: "(Re-enabled)",
    landingScreen: "HD-3",
  },
  "ECM-011": {
    code: "ECM-011",
    httpStatus: 400,
    title: "Invalid Input",
    body: "Your message contained content we can't process. Please rephrase your instruction.",
    recovery: "(Cleared, re-enabled)",
    landingScreen: "HD-3",
  },
  "ECM-012": {
    code: "ECM-012",
    httpStatus: 409,
    title: "Action In Progress",
    body: "This action is being processed in another tab. Please wait a moment and try again.",
    recovery: "[Refresh]",
    landingScreen: "Current",
  },
  "ECM-013": {
    code: "ECM-013",
    httpStatus: null,
    title: "Connection Lost",
    body: "We couldn't load your generation. Please refresh the page.",
    recovery: "[Refresh Page]",
    landingScreen: "Current",
  },
  "ECM-014": {
    code: "ECM-014",
    httpStatus: 413,
    title: "File Too Large",
    body: "Images must be under 10MB. Please resize or compress your image.",
    recovery: "[Try Again]",
    landingScreen: "HD-1",
  },
  "ECM-015": {
    code: "ECM-015",
    httpStatus: null,
    title: "Scraping Timeout",
    body: "We couldn't fetch your product page in time. Try uploading a product image directly.",
    recovery: "[Upload Image] · [Try URL Again]",
    landingScreen: "HD-1",
  },
  "ECM-016": {
    code: "ECM-016",
    httpStatus: null,
    title: "Signing Failed",
    body: "We couldn't sign your video for compliance. Your credit has been refunded. Our team is investigating.",
    recovery: "Treated as failed_export → [↻ Retry Export]",
    landingScreen: "HD-6",
  },
  "ECM-017": {
    code: "ECM-017",
    httpStatus: 400,
    title: "Declaration Required",
    body: "Please accept all 3 declarations before exporting.",
    recovery: "(Checkbox highlight)",
    landingScreen: "HD-6",
  },
  "ECM-018": {
    code: "ECM-018",
    httpStatus: 410,
    title: "Preview Assets Expired",
    body: "Your render is more than 30 days old, so we've cleaned up the preview files. You'll need to start a new generation — we're sorry for the inconvenience.",
    recovery: "[Start New Generation]",
    landingScreen: "HD-6",
  },
  "ECM-019": {
    code: "ECM-019",
    httpStatus: 410,
    title: "Export Retry Limit Reached",
    body: "Export failed 3 times. All credits have been refunded. Please contact support so we can investigate this generation.",
    recovery: "[Contact Support] · [Start New Generation]",
    landingScreen: "HD-6",
  },
  "ECM-020": {
    code: "ECM-020",
    httpStatus: 428,
    title: "Declaration Refresh Required",
    body: "Your last declaration is more than 24 hours old. Please re-confirm the 3 declarations above to retry the export. No credit will be charged until you re-sign.",
    recovery: "3 checkboxes inline above retry",
    landingScreen: "HD-6",
  },
};
