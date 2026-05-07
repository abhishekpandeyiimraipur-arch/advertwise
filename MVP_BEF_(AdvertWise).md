#

> **Classification:** CONFIDENTIAL · GOLDEN RC · Execution-Grade Blueprint
> **Status:** MVP Locked · Aligned to PRD v3 (28 Apr 2026) + TDD v3 (28 Apr 2026)
> **Audience:** Google Antigravity Agentic IDE (executor) + Founder (orchestrator)
> **Sprint Window:** Apr 26 → May 10 (15-day build), May 10 → May 20 (10-day closed beta), May 20 (production launch)
> **Invariants:** 6-Screen Linear Flow · 4-Phase Pipeline · Mandatory Intent Gate · Bounded Co-Pilot Chat · Credit Lock Before Compute · State-Driven UI · 2xx-Only Idempotency Cache · Origin-Preserving Webhook Restore

---

## 1. Define BEF Reading Rules and Authority Stack

This section tells the Agentic IDE how to read this document, how to resolve disagreements between PRD, TDD, and BEF, and what minimum context to load before authoring any file.

### 1.1 Purpose

The Blueprint Execution File (BEF) is the third-tier authority document in the AdvertWise specification stack. PRD v3 defines **WHAT** must exist; TDD v3 defines **HOW** it is implemented; this BEF defines **HOW TO EXECUTE THE BUILDING OF IT** — the order, the seams, the human-vs-agent boundary, and the validation gates between PRD requirements and TDD code.

The BEF is not a derivative summary. It is the operating contract under which the Agentic IDE writes code and the Founder reviews it. Every section closes a specific decision the agent would otherwise have to make on its own — sequencing, halts, approval gates, and explicit gap callouts where PRD or TDD leave ambiguity.

### 1.2 What this section defines

- The 16-section MECE structure that scopes every executable decision in the build.
- The Founder vs Agentic IDE responsibility framing referenced in §3.
- The mapping between every PRD `[PRD-*]` semantic anchor, every TDD `[TDD-*]` implementation anchor, and the BEF section that sequences it.
- The build order (foundations → execution) with explicit halt points referenced in §16.
- Identified gaps where PRD and TDD disagree, are silent, or where the BEF must legislate a tie-breaker.

### 1.3 What this section does NOT define

- It does not re-state the full PRD or TDD verbatim. The PRD is the contract; the TDD is the implementation; the BEF is the **execution sequencer**.
- It does not contain code blocks, SQL DDL, Python implementations, FFmpeg commands, or Lua scripts. Those live in the TDD by design.
- It does not invent features, screens, FSM states, ENUM values, error codes, or endpoints. Anything not present in PRD v3 or TDD v3 is out of scope.
- It does not define visual design beyond what the design-token dictionary in PRD already freezes.
- It does not define marketing copy, landing-page content, or any surface that lives outside HD-1..HD-6.

### 1.4 The Authority Stack (Three-Axis Decision Table)

When two documents conflict, apply this decision table mechanically. The hierarchy is **immutable**.

| Axis | Dimension | Authority Order | Rationale |
|---|---|---|---|
| **A1** | Product features and behaviors (screens, states, error codes, copy, user-visible flow) | **PRD → TDD → BEF** | PRD is the contract with the user. |
| **A2** | Technical implementation choices (SQL, Python, library choices, infrastructure, model selection, CI scripts) | **TDD → PRD → BEF** | TDD is the engineering contract; PRD only specifies WHAT. |
| **A3** | Execution order and agent rules (halts, approval gates, single-file scope, build sequencing) | **BEF → TDD → PRD** | BEF is the execution sequencer; PRD/TDD contain content but not order. |

**Application protocol — no silent picks.** When the agent encounters a divergence:

- **IF** the divergence is on Axis A1 → **THEN** the PRD position is canonical; the TDD position is reconciled to PRD.
- **IF** the divergence is on Axis A2 → **THEN** the TDD position is canonical, **provided** TDD's implementation still satisfies PRD acceptance criteria; **ELSE** PRD wins.
- **IF** the divergence is on Axis A3 → **THEN** this BEF is canonical.
- **IF** the divergence is on a dimension not covered by A1/A2/A3 → **THEN** halt and surface to Founder per §3.7. Do not silently default.

Every applied resolution is logged in `bef-decisions.md` so future agent sessions inherit the precedent.

### 1.5 Reading Rules for the Agentic IDE (Numbered)

1. **Anchor first, content second.** Always grep for `[PRD-*]` or `[TDD-*]` anchors before reading prose. Anchors are stable IDs; prose is mutable explanation.
2. **PRD wins on contract conflicts (Axis A1).** If PRD and TDD disagree on a feature, the PRD is authoritative; file a reconciliation ticket per §2.7 rather than silently diverging.
3. **TDD wins on implementation conflicts (Axis A2).** Library choice, SQL DDL, worker permission matrix, CI script names — TDD is authoritative provided PRD acceptance criteria still hold.
4. **BEF wins on execution sequencing (Axis A3).** Build order, halt points, single-file scope, gate structure — BEF is authoritative.
5. **Pin context narrowly.** Per-task context = the BEF section that names the task + the PRD anchor(s) that section references + the TDD section(s) that section references + the immediate file being authored. Do not load whole documents.
6. **Single-file scope per task.** No multi-file refactors in one execution. The build order in §16 enumerates one file per step.
7. **Halt at named checkpoints.** §3 lists the five mandatory Founder approval gates. The agent must stop and await explicit approval before continuing past each gate.
8. **CI is the truth.** If a CI job is red, no new file may be authored. The list of CI jobs and their pass criteria is in §15.
9. **Missing anchor = halt.** If this BEF references a `[PRD-*]` or `[TDD-*]` anchor that is not present in the latest PRD/TDD revision, treat that as an immediate halt-and-surface event per §3.7. Do not synthesize.
10. Zero-Shadowing policy: do not create folders/files that collide with stdlib modules, sibling packages, or legacy names; use collision-proof names only.

### 1.6 Dependencies with other sections

This section is the entry point. Every subsequent section assumes these reading rules are honored. §2 (Anchor Authority) extends the authority stack into the cross-document anchor DAG. §3 sequences the halts that operationalize Rule 7. §16 sequences the build order that operationalizes Rules 5 and 6.

---

## 2. Map PRD↔TDD↔BEF Anchor Authority

This section establishes the unambiguous Directed Acyclic Graph (DAG) of authority across the three-document stack, so that for any execution decision the agent must make, there is exactly one unambiguous source of normative content.

### 2.1 Purpose

To make traceability mechanical. Bi-directional traceability is enforced by `[TDD-TRACE]` in TDD v3 and is reproduced here as the BEF execution map. Every PRD anchor that the Agentic IDE will encounter at execution time has a TDD implementation anchor and a BEF section that sequences it.

### 2.2 What this section defines

- The application of §1.4 (the three-axis Authority Stack) to specific recurring conflict types.
- The cross-reference table mapping every PRD anchor to its TDD implementation anchor to the BEF section that sequences it.
- The conflict-resolution protocol for cases where PRD and TDD diverge.
- The list of conflicts already resolved against the v3 documents.

### 2.3 What this section does NOT define

- The actual content of PRD or TDD anchors (those live in their source documents).
- The 22-state FSM diagram (lives in §7).
- The component hierarchy (lives in §10).
- The build order (lives in §16).

### 2.4 The Authority Stack Applied to Recurring Conflict Types

| Concern | Authority Order | Worked Example |
|---|---|---|
| Product features, user-visible behavior, copy, screens, states, error codes | PRD > TDD > BEF (Axis A1) | If TDD shipped 21 states but PRD specifies 22, PRD wins. |
| Technical implementation details (SQL, Python signatures, library choices, infrastructure) | TDD > PRD > BEF (Axis A2) | If PRD says "Next.js 14" but TDD says "Next.js 15", TDD wins. |
| Build sequence, human approval gates, agent halts, MECE section split | BEF > TDD > PRD (Axis A3) | If TDD lists 45 init steps in a flat sequence but BEF micro-phases them, BEF's micro-phasing is authoritative for execution order. |
| CI test pass/fail criteria | TDD > BEF | TDD specifies the actual CI jobs; BEF references them. |
| Acceptance criteria for release readiness | PRD > BEF | PRD §RELEASE-MVP and §RELEASE-BETA are the gate definitions. |

### 2.5 The Anchor-to-Section Map

The map is grouped by phase of work to match the build order in §16.

#### 2.5.1 Foundations (Schema, Types, Enums)

| PRD Anchor | TDD Anchor | BEF Section |
|---|---|---|
| `[PRD-FSM]`, `[PRD-PRETOPUP]`, `[PRD-STATE-MATRIX]` | `[TDD-FSM]`, `[TDD-SCHEMA]`, `[TDD-MIGRATIONS]` | §7, §11 |
| `[PRD-GREENZONE]` | `[TDD-ENUMS]`, `[TDD-WORKERS]-B` | §5, §11 |
| `[PRD-PLAYBOOK]` (12 frameworks ENUM) | `[TDD-PROMPTS]-E`, `[TDD-WORKERS]-C` | §9 |
| `[PRD-DESIGN-TOKENS]`, `[PRD-UI-TREE]`, `[PRD-UI-MOCKS]` | `[TDD-SCAFFOLD]`, `[TDD-TYPES]-A` | §10 |

#### 2.5.1.1 Infrastructure Modules (Gateway + Redis)

The backend infrastructure layer uses collision-proof module naming under the `infra_*` convention.

- `app/infra_gateway.py` is the canonical ModelGateway interface used by all workers and orchestrators.
- `app/infra_redis.py` is the canonical Redis bootstrap and manager module.


`infra_redis.py` is responsible for:
- Initializing Redis connections during FastAPI lifespan startup.
- Managing logical Redis DB separation (DB0–DB5 as defined in TDD).
- Exposing a single access point (`app.state.redis_mgr`) for all guards, routes, and workers.

**Dependency Injection Contract:**
- Redis is initialized in `main.py` during application startup.
- The instance is attached to `app.state.redis_mgr`.
- All downstream consumers MUST access Redis via `request.app.state.redis_mgr` (never create new connections).

**Policy (Zero-Shadowing Extension):**
- No module may be named `redis.py`, `types.py`, or any stdlib-conflicting name.
- All infrastructure utilities MUST use the `infra_*` prefix to avoid namespace collisions.





#### 2.5.2 User Journey Surfaces (Screens HD-1..HD-6)

| PRD Anchor | TDD Anchor | BEF Section |
|---|---|---|
| `[PRD-HD1]` | `[TDD-WORKERS]-B` (Worker-EXTRACT), `[TDD-API]-A` POST `/api/generations` | §6, §8, §12 |
| `[PRD-HD2]` | `[TDD-DIRECTOR]-A/B/C`, `[TDD-WORKERS]-B` confidence outputs | §6, §10 |
| `[PRD-HD3]`, `[PRD-COPILOT]` | `[TDD-WORKERS]-D` (phase2_chain), `[TDD-CHAT-CHAIN]`, `[TDD-API]-C` | §6, §9, §12 |
| `[PRD-HD4]` | `[TDD-WORKERS]-G` (STRATEGIST), `[TDD-API]-D`, `[TDD-API]-E`, `[TDD-STRATEGY]-A` | §6, §8, §12 |
| `[PRD-HD5]` | `[TDD-WORKERS]-J` (phase4_coordinator), `[TDD-VIDEO]-A/B`, `[TDD-WORKERS]-H` | §6, §8, §12 |
| `[PRD-HD6]` | `[TDD-WORKERS]-I` (Worker-EXPORT), `[TDD-API]-F`, `[TDD-API]-G` | §6, §8, §12, §13 |

#### 2.5.3 Cross-Cutting Subsystems

| PRD Anchor                                                          | TDD Anchor                                                                                 | BEF Section   |
| ------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ | ------------- |
| `[PRD-FEATURES-PAYMENT]` (F-301, F-302, F-303), `[PRD-PAYMENT-FSM]` | `[TDD-API]-D`, `[TDD-API]-G`, `[TDD-API]-H`, `[TDD-REDIS]-B/C/D`, `[TDD-CONCURRENCY]-A..E` | §11, §12, §13 |
| `[PRD-FEATURES-COMPLIANCE]` (F-501, F-503, F-505, F-506)            | `[TDD-VIDEO]-B/C`, `[TDD-WORKERS]-I` (C2PA), `[TDD-TAKEDOWN]-A/B/C/D`, `[TDD-GUARDS]-A/B`  | §14           |
| `[PRD-FEATURES-RETENTION]`                                          | `[TDD-R2-RETENTION]`, `[TDD-MIGRATIONS]` partition rotator                                 | §11, §14      |
| `[PRD-IDEMPOTENCY]`                                                 | `[TDD-CONCURRENCY]-A`, `[TDD-REDIS]-A` (DB5)                                               | §12           |
| `[PRD-ERROR-MATRIX]`, `[PRD-ERROR-COPY]`, `[PRD-ERROR-MAP]`         | `[TDD-DLQ]-A/B`, `[TDD-API]-G`                                                             | §13           |
| `[PRD-MOATS]` (Style Memory)                                        | `[TDD-FLYWHEEL]-A/B`, `[TDD-SCHEMA]` `user_style_profiles`                                 | §11           |
| `[PRD-FEATURES-INFRA]` (F-601..F-607)                               | `[TDD-PROMPTS]`, `[TDD-GATEWAY]`, `[TDD-REDIS]-E`, `[TDD-OBSERVABILITY]`                   | §9, §15       |
| `[PRD-AC-1..6]`, `[PRD-AC-GLOBAL]` G1..G5                           | `[TDD-CICD]-A..E`, `[TDD-API-STUBS]-*`                                                     | §15           |

#### 2.5.4 Release Gates

| PRD Anchor | TDD Anchor | BEF Section |
|---|---|---|
| `[PRD-RELEASE-BETA]` B1..B5, E1..E6 | `[TDD-CICD]`, `[TDD-ROLLBACK]-F` (Rollback Drill) | §15, §16 |
| `[PRD-RELEASE-MVP]` M1..M10 | `[TDD-OBSERVABILITY]`, `[TDD-CICD]` | §15, §16 |
| `[PRD-UX-FREEZE]` | `[TDD-MIGRATION-SAFETY]-E` (no destructive migrations) | §5, §16 |

### 2.6 Conflict-Resolution Protocol (Per §1.4 Application)

When the agent encounters a divergence between PRD and TDD:

1. **Stop.** Do not pick one and proceed silently.
2. **Identify the divergence class:**
   - **Class A — Contract divergence** (feature semantics, error code, screen flow, FSM state count, declaration count, copy text). Axis A1 applies. PRD wins. File a reconciliation ticket; TDD is updated to match PRD.
   - **Class B — Implementation divergence** (column type narrower in TDD than PRD requires; library choice; CI script name; concurrency primitive; provider). Axis A2 applies. TDD wins **only if** TDD's implementation still satisfies the PRD acceptance criteria; otherwise PRD wins.
   - **Class C — Silence on both sides.** The §16.7 Open Gaps subsection legislates a tie-breaker; if the gap is not yet enumerated there, halt and surface to Founder.
3. **Document the resolution** in `status_history` audit trail or Founder log; do not let the divergence vanish.

### 2.7 Identified Conflicts (Resolved Here)

| # | Conflict | PRD Position | TDD Position | Resolution |
|---|---|---|---|---|
| C1 | Canonical video duration | `[PRD-VISION]`: "5–10 second" video; HD-3 mock shows 15s as a duration chip option, implying 5/10/15s selectable. | `[TDD-VIDEO]-A`: hard-canonical 15s smart-stitch (3s hook + 9s I2V + 3s CTA), `WorkerCompose.CANONICAL_DURATION_S = 15.0`. | **PRD wins on customer-facing claim ("user-selected duration")** but TDD's 15s smart-stitch is the only implementation. **BEF directive:** treat 15s as the only buildable duration in MVP; surface duration as a non-editable fixed display in the HD-3 chip bar; defer 5s/10s variants post-MVP. Update PRD copy to "around 15-second" in next PRD revision. |
| C2 | pgvector embedding dimensionality | Standardize on **1536-dim** using `text-embedding-3-small` across all vector operations. | Discrepancy in some TDD constants. | **BEF directive (Axis A2):** Implement 1536-dim via OpenAI `text-embedding-3-small` for all `pgvector` columns. Hard-fail any attempt to use 768-dim models or non-OpenAI standard embeddings. |
| C3 | LLM provider for chat refinement | PRD does not name a specific model. | `[TDD-CHAT-CHAIN]` Stage 3: "Model: deepseek-v3.2"; `[TDD-OVERVIEW]` lists DeepSeek V3.2, Groq, Gemini, Together AI, SiliconFlow as the LLM pool. | **BEF directive (Axis A2):** the gateway's `route(capability='llm')` chooses among the pool; DeepSeek V3.2 is the prompt-pinned target but the gateway is authoritative for fallback selection. |
| C4 | Frontend framework version | `[PRD-UI-TREE]`: "Next.js 14 App Router". | `[TDD-OVERVIEW]`: "Next.js 15 (App Router)". | **TDD wins (Axis A2).** Build on Next.js 15. PRD copy is updated in the next revision. |
| C5 | C2PA verification target | `[PRD-FEATURES-COMPLIANCE]`: External verification (Adobe VerifyContentCredentials) is **forbidden** in CI and worker loops. | `[TDD-WORKERS]-I`: c2patool returncode-checked; local `c2patool --verify` for verification. | **PRD wins (Axis A1) and TDD agrees.** All C2PA verification is local via `c2patool --verify`. External tools are end-user optional only. See GAP-07 in §16.7 for the historical patch. |
| C6 | Migration runner | PRD silent. | `[TDD-IDE]-A` step 2a: raw SQL via `ci/run_migrations.py --dry-run` / `--apply`, lexicographic order, recorded in `schema_migrations`. | **TDD wins (Axis A2).** No Alembic. See GAP-09 in §16.7 for the canonical resolution. |
| C7 | Alerting platform | PRD silent on alerting backend. | `[TDD-OBSERVABILITY]`: PostHog + Grafana Cloud; PagerDuty not used in MVP. | **TDD wins (Axis A2).** Alert tiers (`GA-Warn`, `GA-Critical`) are abstract severities; delivery is via Grafana per `[PRD-FEATURES-INFRA]` F-606. References to "PagerDuty P0" in earlier drafts are normalized to "Grafana alert" in §14 and §15. |

### 2.8 Dependencies with other sections

§2 is read by every subsequent section as the lookup index. §16 (Build Order + Open Gaps) extends this with the build sequence and the unresolved gap log.

---

## 3. Define Founder/Agent Halt Gates G1–G5

This section assigns every category of decision and action to either the Founder or the Agentic IDE, names the five mandatory halt points where the agent must stop and wait, and lists the actions the agent may never perform.

### 3.1 Purpose

To define unambiguously, for every category of decision and execution, whether the **Founder** (Abhishek, the human Orchestrator/Director) or the **Agentic IDE** (Antigravity, the autonomous executor) holds authority. The MVP is built under a strict human-in-the-loop model: the agent writes code; the Founder reviews, approves, and authorizes irreversible operations. No agent autonomy exists for financial, legal, or destructive operations.

### 3.2 What this section defines

- The decision-rights matrix between Founder and Agent.
- The five mandatory Founder approval gates (G1..G5), defined here and sequenced in §16.5.
- The forbidden-actions list for the agent.
- The escalation protocol when the agent encounters ambiguity.

### 3.3 What this section does NOT define

- The actual sequence of files to be built (lives in §16).
- The state-machine transitions (lives in §7).
- The technical implementation of permissions (e.g., DB role grants live in §11).

### 3.4 Decision-Rights Matrix

| Decision Class | Founder | Agentic IDE | Rationale |
|---|---|---|---|
| Define product features (what exists) | ✅ exclusive | ❌ | PRD is human-authored. |
| Approve PRD changes (new screen, new state, new error code) | ✅ exclusive | ❌ | UX-Freeze enforced by `[PRD-UX-FREEZE]`. |
| Author TDD additive sections | ✅ primary | ✅ proposes | Agent may draft; Founder approves. |
| Author code matching a TDD anchor | 🔍 reviews | ✅ executes | Single-file-scope autonomous. |
| Add an additive DB migration (`ADD COLUMN ... NULL`) | 🔍 reviews | ✅ executes | Append-only is safe per `[TDD-MIGRATION-SAFETY]-A`. |
| Author a destructive DB migration (DROP, RENAME, ALTER TYPE narrow) | ✅ exclusive | ❌ HALT | Per `[TDD-MIGRATION-SAFETY]-E` agent is physically forbidden. |
| Run `ci/run_migrations.py --apply` against staging | 🔍 approves | ✅ executes | After dry-run is green. |
| Run `ci/run_migrations.py --apply` against production | ✅ exclusive | ❌ | Two-reviewer + Founder sign-off. |
| Add or modify an LLM prompt template | 🔍 reviews | ✅ proposes | YAML schema + Pydantic output enforced by `[TDD-PROMPTS]`. |
| Tune CostGuard ceilings (₹2 / ₹10 / ₹14) | ✅ exclusive | ❌ | Direct unit-economics impact. |
| Add a new external API provider to gateway pool | ✅ exclusive | ❌ | New COGS source. |
| Toggle feature flags (Tier 1–4 degradation, beta gate) | ✅ exclusive | ❌ | Production behavior change. |
| Acknowledge a P0/P1 Grafana alert | ✅ exclusive | ❌ | Human accountability. |
| Roll back the application Docker image | ✅ executes | ❌ | Per `[TDD-ROLLBACK]-G`. |
| Force-set FSM state via psql (corruption recovery) | ✅ exclusive | ❌ | Per `[TDD-ROLLBACK]-C`. |
| Issue a manual refund | ✅ exclusive | ❌ | Per `[TDD-ROLLBACK]-D` no auto-refund during reconciliation. |
| Write to `pre_topup_status` column | ❌ | ✅ via L2 routes only | Workers DENIED; only `/approve-strategy`, `/retry-export`, webhook handler. |
| Write to `wallet_transactions` table | ❌ | ✅ via L2 routes + DLQ | Workers DENIED except `Worker-EXPORT` which only flips `locked → consumed`. |
| Write to `audit_log` table (after migration) | ❌ | ✅ via L2 routes only | DB role REVOKE UPDATE/DELETE on partitions; INSERT-only. |
| Beta cohort user invitation | ✅ exclusive | ❌ | Per `users.beta_invited` column. |

### 3.5 Mandatory Founder Approval Gates G1–G5 (Checkpoints)

These are the five hard halts named in `[TDD-IDE]-C`. The agent MUST stop building and emit an `AWAITING_APPROVAL` status; the Founder responds in writing before the next file is authored. Sequenced in time in §16.5; verified via §15.7.

| #      | Halt After                                                                                          | Founder Verifies                                                                                                                                                                                                           | Pass Criterion                                                                                                                                                                                                                                         |
| ------ | --------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **G1** | Step 10 of build order — Guards complete (`compliance_gate.py`, `output_guard.py`, `cost_guard.py`) | Pre-/post-LLM guard logs are appearing in Postgres `agent_traces` and `compliance_log`.                                                                                                                                    | Two manual `/chat` invocations in dev: one valid → COGS recorded; one with prompt-injection → blocked at Stage 1, no LLM call, no COGS.                                                                                                                |
| **G2** | Step 16 — Phase 2 chain (`phase2_chain.py`) functional                                              | Framework router LLM JSON parses cleanly into `FrameworkRoutingOutput`; default-trio constraint satisfied or fallback flagged.                                                                                             | Run a real product URL through HD-1→HD-3; verify 3 framework-tagged scripts render with `framework_angle` mix of logic + emotion + conversion.                                                                                                         |
| **G3** | Step 20 — B-Roll Planner (`broll/planner.py`)                                                       | Determinism: same `(framework_angle, category)` input always returns the same `clip_id` list.                                                                                                                              | Run 5 identical inputs; assert byte-identical output; verify `d2c_beauty + emotion` returns archetypes biased toward sensory clips.                                                                                                                    |
| **G4** | Step 26 — Worker-EXPORT functional end-to-end                                                       | Full HD-1→HD-6 flow: 15s render completes, declarations capture, `c2patool --version` runs, both 1080×1080 + 1080×1920 sign with returncode 0.                                                                             | C2PA manifest validates using local `c2patool --verify`. (External verification APIs such as Adobe VerifyContentCredentials are strictly forbidden in both CI and runtime per `[PRD-FEATURES-COMPLIANCE]`.) SGI watermark visible at both resolutions. |
| **G5** | Step 36 — Razorpay Webhook (`webhook.py`)                                                           | Origin-preserving multi-row restore: a user pinned simultaneously on HD-4 (`pre_topup_status='strategy_preview'`) AND HD-6 (`pre_topup_status='failed_export'`) restores to **both correct screens** in one webhook event. | Manual ₹1 sandbox top-up; check `restored_count == 2`; verify HD-4 user lands on HD-4 strategy view and HD-6 user lands on HD-6 failed-export view.                                                                                                    |

The Founder may add ad-hoc halts at any step; the agent must honor any "HALT" instruction received via the conversation.

### 3.6 Forbidden Actions for the Agent (Hard Halts)

The agent must refuse and surface to Founder if any task implies one of these:

- Writing `httpx`, `requests`, or `aiohttp` imports inside `app/workers/strategist.py`, `compose.py`, `export.py`, `copy.py`, `critic.py`, `tts.py`, `i2v.py`, `reflect.py` (per `[TDD-IMPORT-GRAPH]`).
- Writing `arq.enqueue.*worker_export` inside `phase4_coordinator` (per `[TDD-WORKERS]-J` disambiguation block).
- Writing `pre_topup_status` mutations inside any `app/workers/*.py` file (per `[TDD-WORKERS]-A` invariant).
- Writing `-shortest` flag in any FFmpeg command (per `[TDD-WORKERS]-H`).
- Writing `localStorage` or `sessionStorage` reads/writes that would persist across browsers (only allowed: idempotency keys with the documented schema).
- Hardcoding `status='strategy_preview'` as the webhook restoration target (per the v28 regression that `[PRD-PRETOPUP]` exists to prevent).
- Using presigned R2 URLs inside any worker. **Storage Security Invariant:** B-roll and source assets are stored in Cloudflare R2 with structured folders (e.g., `/broll/<category>/<archetype>/`). Workers must use credentialed `boto3` access only; presigned URLs are strictly forbidden for internal worker-to-worker transfers.
- Using static JSON service account keys for authentication. **Auth Security Invariant:** The system relies strictly on Google Application Default Credentials (ADC) via `gcloud auth` for TTS, OAuth, and embeddings. JSON key files are forbidden.
- Adding any new route under `/app/*` that does not map to HD-1..HD-6 (per `[PRD-UX-FREEZE-SCREEN]`). The peripheral `/grievance` route is the only allowed exception (defined in §10).
- Adding a new `JobStatus` ENUM member (per `[PRD-UX-FREEZE-FLOW]` and `fsm_freeze_guard.py`).
- Modifying `app/ui/copy/errors.ts` without two-reviewer approval (per `[PRD-UX-FREEZE-COPY]`).
- Removing `AW_API_MODE=stub` from any CI workflow (per `[TDD-API-STUBS]-P`).

**Missing-anchor rule (per §1.5 #9):** if the agent encounters a forbidden-action reference whose `[TDD-*]` or `[PRD-*]` anchor cannot be located in the latest PRD/TDD revision, the agent must halt and surface per §3.7 — never synthesize the missing target.

### 3.7 Escalation Protocol

When the agent encounters ambiguity not covered by PRD/TDD/BEF:

1. **Halt the current task.** Do not proceed with a guess.
2. **Emit a structured surface report** containing: the file being authored, the specific decision required, the PRD/TDD anchors consulted, the candidate options, and the agent's recommended choice with reasoning.
3. **Wait for Founder reply.** Do not author parallel work in the meantime — context window discipline matters more than throughput.
4. **Persist the resolution** in `bef-decisions.md` (a Founder-maintained log) so future agent sessions inherit the precedent.

### 3.8 Dependencies with other sections

§3 governs every subsequent execution decision. §16 references the Founder approval gates by their G1..G5 IDs. §11 references the worker permission matrix. §12 references the L2-only mutation privileges.

---

## 4. Restate PRD Product Contract Boundaries

This section states in one bounded definition exactly what AdvertWise MVP is — and by negation, what it is not — so that no agent task may invent a feature outside this envelope.

### 4.1 Purpose

To make the product perimeter unambiguous. Every other section sequences work strictly inside it.

### 4.2 What this section defines

- The product-class definition (what kind of system this is).
- The user-visible deliverable (what a user receives at the end).
- The bounded scope of inputs, outputs, and surfaces.
- The competitive positioning (positioned-against axis from PRD `[PRD-COMPETITION]` and `[PRD-DIFFS]`).

### 4.3 What this section does NOT define

- Implementation details of the pipeline (lives in §8).
- The component tree or design tokens (lives in §10).
- Plan pricing or COGS ceilings as enforcement (those are constraints — they live in §5).
- The state machine that governs the journey (lives in §7).

### 4.4 Product-Class Definition

AdvertWise is a **verticalized AI co-pilot for India-first short-form product advertising**, delivered as a **cross-device responsive web application only**. It converts a single product URL or product image into a marketing-ready, IT-Rules-2026-compliant 15-second video advertisement, with multi-regional Indic voiceover, in under 3 minutes, for a single pre-paid credit. It is strictly bounded: it is **not** a general-purpose video editor, **not** an open-ended text-to-video prompter, **not** a template marketplace, **not** an avatar/lip-sync platform, and **not** a content marketplace.

### 4.5 What the User Receives at the End of a Successful Generation

Per `[PRD-HD6]` State 3 (`export_ready`), a successful end-to-end run produces:

1. A **480p preview MP4** (R2-hosted, presigned, used in HD-6 player), with 30-day retention for Paid users.
2. **Two HD final exports**: 1080×1080 (1:1 square) and 1080×1920 (9:16 vertical), both H.264 + AAC, both **C2PA-signed**, both bearing a burned-in **SGI watermark** ("AI Generated Content"), with 5-year retention.
3. A **C2PA manifest hash** stored in `generations.exports.c2pa_manifest_hash`.
4. An **immutable audit_log row** recording the user's three legal declarations (commercial purpose, image rights, AI disclosure), captured with IP, User-Agent, server timestamp, and a SHA-256 hash of the declaration payload.
5. **One credit consumed** from the user's wallet (`wallet_transactions.status='consumed'`).
6. An **opt-in Style Memory upsert** in `user_style_profiles` (pgvector embedding of the winning script + framework + motion + environment), reusable for the user's next generation in the same category.

### 4.6 What the User Provides at the Start

Per `[PRD-HD1]`:

1. A product URL (preferred — Meesho, Flipkart, Amazon.in muscle memory) **or** a product image upload (≤10MB, JPEG/PNG).
2. After initial isolation: bounded enum selections only — audience, benefit, emotion, language. No free-text primary inputs. No prompt typing.
3. Optionally: up to three Co-Pilot Chat refinement turns on HD-3, each ≤500 chars and ≤20 words, classified into structured refinement intents.
4. Three legal declaration checkboxes on HD-6 before download.
5. UPI payment (Razorpay) for credits when the wallet is empty.

### 4.7 Bounded Scope — Input Surface

| Input class | Allowed | Forbidden |
|---|---|---|
| Primary inputs | URL · image upload · enum chips · 3-turn bounded chat · 3 declaration checkboxes | Open-ended prompts · timeline scrubbing · custom framework authoring · keyframe edits · brush/mask/erase tools · multi-product batch input |
| Product categories | 5 Green Zone: `d2c_beauty`, `packaged_food`, `hard_accessories`, `electronics`, `home_kitchen` | 4 Red Zone: `apparel`, `footwear`, `fabric_home`, `organic_produce` (rejected at Phase 1 with `failed_category`) |
| Languages | 7 Indic TTS voices: Hindi, Hinglish, Marathi, Punjabi, Bengali, Tamil, Telugu | All other languages |
| Payment | INR via Razorpay UPI only | Stripe, PayU, Cashfree, PayPal, crypto, international currencies |
| Surfaces | 6 screens HD-1..HD-6, plus Top-Up Drawer overlay and Plan Modal overlay, plus the peripheral `/grievance` route | Native mobile apps · Electron · browser extension · public API · customer webhooks |

### 4.8 Bounded Scope — Output Surface

| Output class | Allowed                                                                                                                                     | Forbidden |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| Render duration | Canonical 15 seconds (3s hook B-roll + 9s I2V + 3s CTA B-roll, per `[TDD-VIDEO]-A`)                                                         | Any other duration in MVP |
| Hero asset | The user's actual product (isolated PNG via BiRefNet (Apache 2.0) plus optional curated atmospheric B-roll (faces/hands/locations excluded) | Generic stock product footage · talking-head avatars · human spokespersons · lip-sync · video-to-video stylization |
| Export formats | Exactly 2 per credit: 1080×1080 (1:1) + 1080×1920 (9:16)                                                                                    | Any other resolution · CSV bulk export · batch render · audio-only export |
| Compliance burn-in | SGI watermark ("AI Generated Content") FFmpeg drawtext at all resolutions; C2PA manifest cryptographically signed via `c2patool`            | Unsigned exports · removable watermarks · avatar disclosure variants |

### 4.9 Competitive Positioning (Frozen)

Per `[PRD-COMPETITION]` and `[PRD-DIFFS]`, AdvertWise occupies the **uncontested upper-right quadrant**: HIGH India localization × HIGH I2V × IT Rules 2026 compliance baked-in. The three strategic moats are:

1. **Regulatory defensibility:** SGI burn-in + C2PA signing + 5-year partitioned audit + <60-min auto-takedown.
2. **Hyper-localization:** Sarvam Bulbul V3 routing for 7 Indic TTS languages.
3. **UPI-native financials:** Razorpay UPI only, no USD-card friction, sachet-pricing (₹399 / ₹1,499) with `payment_status` and `wallet_status` cleanly split FSMs.

### 4.10 Plan Tier Contract

Per `[PRD-PRICING]`:

| Plan | Price | Validity | Credits | COGS Ceiling | Render Capability |
|---|---|---|---|---|---|
| Starter (Free) | ₹0 | No expiry | Phase 1–3 access only · max 3 gens lifetime | ₹2.00 / gen | **Cannot render.** HD-4 button → 403 ECM-006 → Plan Modal |
| Essential | ₹399 | 30 days | 4 credits (1 credit = 1 HD export, 2 formats) | ₹10 / gen (CostGuard) | Full pipeline including export |
| Pro | ₹1,499 | 45 days | 25 credits (same semantics) | ₹14 / gen (CostGuard) | Full pipeline including export |

### 4.11 Dependencies with other sections

§4 is the perimeter. §5 enumerates the invariants that defend this perimeter. §6 details the user journey within it. §8, §11, §12 implement the technical realization.

---

## 5. Lock Hard Invariants and Banned Patterns

This section enumerates every constraint that must remain true at every transition, every API call, every database write, and every UI render across the lifetime of a generation. Violations are P0/P1 incidents, not bugs.

### 5.1 Purpose

To enumerate the system's **safety invariants**: financial, legal, UX, system-predictability, and freeze rules.

### 5.2 What this section defines

- The financial invariants protecting unit economics.
- The legal invariants required for IT Rules 2026 + DPDP Act 2023 compliance.
- The UX invariants protecting the bounded product identity.
- The system-predictability invariants protecting against silent state drift.
- The freeze rules locked by `[PRD-UX-FREEZE]`.
- The banned-pattern catalog enforced by CI.

### 5.3 What this section does NOT define

- The recovery flows for invariant violations (lives in §13).
- The CI jobs that detect violations (lives in §15).
- Specific implementation code for invariant enforcement (lives in TDD).

### 5.4 Financial & Economic Invariants

| ID | Invariant | Enforcement |
|---|---|---|
| **F1** | **Credit Lock Before Compute.** No Phase-4 worker may begin running until a Lua `wallet_lock` has succeeded for the exact compute it authorizes. HD-4 lock authorizes full Phase-4 render; HD-6 retry lock authorizes Worker-EXPORT only. | Lua + DB ledger row inserted in same transaction; ARQ enqueue happens after COMMIT. |
| **F2** | **Zero-Risk Generation.** Users are never charged for system failures. Every Phase-4 DLQ event triggers an automatic refund. | DLQ dual-branch handler `on_job_dead` invokes `wallet_refund.lua` plus DB ledger refund row. |
| **F3** | **No Double-Compute.** Once Phase-4 render assets persist to R2, no recovery path re-runs render. Retry from HD-6 targets Worker-EXPORT only — preserving ~₹10 of Phase-4 compute per retry. | `phase4_coordinator` STOPS at `preview_ready` and never enqueues `worker_export`. |
| **F4** | **Algorithmic Model Selection.** Users cannot select underlying AI models. The ModelGateway with circuit-breaker FSM (CLOSED/OPEN/HALF_OPEN) is the sole authority. | `ModelGateway._rank_providers` and `circuit_breaker.lua`. |
| **F5** | **Single Active Lock per Generation.** Partial UNIQUE INDEX `ux_wallet_active_lock ON wallet_transactions (gen_id) WHERE status='locked'` makes double-active-lock physically impossible. | DB-level constraint. |
| **F6** | **Single Refund per Generation.** Partial UNIQUE INDEX `ux_wallet_refund_dedup ON wallet_transactions (gen_id, type) WHERE type='refund'`. | DB-level + DLQ uses `ON CONFLICT DO NOTHING`. |
| **F7** | **CostGuard Ceiling Enforcement.** Per-gen COGS may not exceed plan ceiling (₹2 / ₹10 / ₹14). Pre-check before LLM dispatch; record after (Stage 4 of chat chain) before OutputGuard. | `CostGuard.pre_check` + `CostGuard.record` + post-hoc audit at `preview_ready`. |
| **F8** | **COGS-First Recording.** Cost is recorded **before** OutputGuard runs (the rejected-turn-leak fix). Even rejected refinements consume budget; this prevents adversarial budget-draining via repeated unsafe inputs. | Stage 4 fires before Stage 5 in `[TDD-CHAT-CHAIN]`. CI test `tests/test_chat_chain_order.py`. |

### 5.5 Legal & Compliance Invariants

| ID | Invariant | Enforcement |
|---|---|---|
| **L1** | **100% IT Rules 2026 + DPDP Act 2023 conformance.** Every export bears SGI burn-in and C2PA signature. | `[TDD-VIDEO]-B` drawtext + `[TDD-WORKERS]-I` `c2patool` returncode-checked. |
| **L2** | **Declaration Provenance.** Every export declaration captures user IP, User-Agent, server timestamp, and SHA-256 hash; persisted to monthly-partitioned `audit_log` table. | `[TDD-API]-F` declaration handler. |
| **L3** | **Atomic Re-Sign on Stale Declaration.** When `audit_log.signed_at` > 24h on a retry, server returns 428 ECM-020 without state change; subsequent retry with `declarations:[1,1,1]` INSERTs a new `audit_log` row in the same transaction as the lock + state update + ARQ enqueue. | `[TDD-API]-G` 9-step chain. |
| **L4** | **Audit Log Immutability.** DB role REVOKE UPDATE, DELETE on every audit_log partition. Append-only forever. 5-year retention via DETACH at anniversary. | `[TDD-MIGRATIONS]` partition_rotator + role grants. |
| **L5** | **Data Minimization.** Source assets purged at 7d (Starter) or 30d (Paid). Finalized SGI exports kept exactly 5 years. Daily 02:00 IST retention sweep + weekly Mon 02:30 IST orphan sweep. | `[TDD-R2-RETENTION]`. |
| **L6** | **Auto-Takedown SLA <60 min.** Grievance pipeline ACK <24h, content delete <60min from grievance trigger. Grafana alert tier `GA-Critical` at T+90min. | `[TDD-TAKEDOWN]-A/B/C/D`. |
| **L7** | **Three-Checkbox Independence.** The 3 declaration checkboxes are independent legal assertions; bundling them creates collateral-attack risk. UI renders 3 separate checkboxes; server validates all-three-true. | `DeclarationRequest` Pydantic validator. |

### 5.6 UX & Product Identity Invariants

| ID | Invariant | Enforcement                                                                                                                                    |
| ------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| **U1** | **Product-Visual First.** The user's actual product is the hero asset in every ad. Stock product footage and avatar-led ads are forbidden. | Product comes from `isolated_png_url` (BiRefNet (Apache 2.0). B-Roll planner excludes faces/hands/locations via `chk_broll_safety` constraint. |
| **U2** | **Green Zone Restriction.** Only 5 categories accepted. Red Zone → `failed_category`. | `[PRD-GREENZONE]` ENUM + Worker-EXTRACT raises `CategoryError`.                                                                                |
| **U3** | **Zero Free-Text Primary Inputs.** Open-ended prompting banned. Free-text only inside the 3-turn bounded chat. | UI: enum chips only. Chat: ≤500 chars, ≤20 words, ComplianceGate filtered.                                                                     |
| **U4** | **Mandatory Intent Gate.** HD-4 Strategy Card is a hard stop. No render dispatched without explicit human approval click. | `[PRD-HD4]` server-driven 3-mode primary button. No auto-progression.                                                                          |
| **U5** | **Co-Pilot Refinement Constraint.** Only Phase 2. Cannot change product facts, introduce unsupported claims, bypass framework constraints, or pivot framework angle. | Prompt-level system instructions in `script-refine.v1.0.0.yaml`.                                                                               |

### 5.7 System Predictability Invariants

| ID | Invariant | Enforcement |
|---|---|---|
| **S1** | **Strictly Linear Flow.** Every screen HD-1 → HD-6 always shown. Confidence scores adapt visuals (border color, primary CTA), never skip screens. | `[PRD-CONFIDENCE]`. Overlays (Top-Up Drawer, Plan Modal) preserve underlying screen state. |
| **S2** | **State is DB-Backed.** `generations.status` is the single source of truth. Frontend hydrates via `GET /api/generations/{gen_id}` on every mount and SSE reconnect. | `[TDD-API]-B`. |
| **S3** | **Idempotency Everywhere.** Every mutating endpoint uses `@idempotent(ttl=300, action_key, cache_only_2xx=True)` plus client `localStorage` key plus server `actlock` Redis fence (10s TTL). | `[TDD-CONCURRENCY]-A`. |
| **S4** | **2xx-Only Cache.** Recoverable 4xx (400, 402, 409, 428) NEVER cached. Client clears localStorage on receipt and re-issues fresh UUIDv4. | Decorator config + client `lib/api/client.ts` 4xx-drop rule. |
| **S5** | **Monotonic Retry-Export Key.** Idempotency key for `/retry-export` embeds `export_retry_count`: `{gen_id}:retry-export:{n}`. Prevents cache collision across retries. | `[PRD-IDEMPOTENCY]` + `lib/idempotency/keys.ts`. |
| **S6** | **`pre_topup_status` Coupling.** `status='awaiting_funds'` IFF `pre_topup_status IN ('strategy_preview','failed_export')`. Other states require NULL. Enforced by CHECK constraint AND state-transition trigger. | `[TDD-FSM]` CHECK + trigger. |
| **S7** | **State-Guarded UPDATE.** Every state transition includes `WHERE status = expected_status` — optimistic concurrency. `RETURNING gen_id` rowcount=0 → 409. | `[TDD-CONCURRENCY]-B`. |
| **S8** | **Ledger-First Write.** Every wallet mutation writes the immutable Postgres row before the Redis Lua call. On Lua fail, DELETE the optimistic row inside the same DB transaction. | `[TDD-CONCURRENCY]-C`. |
| **S9** | **Origin-Preserving Webhook Restoration.** Razorpay webhook `captured` event UPDATEs `status = pre_topup_status, pre_topup_status = NULL WHERE user_id=? AND status='awaiting_funds'` — multi-row safe; webhook never hardcodes a destination state. | `[TDD-API]-H`. |
| **S10** | **Coordinator Halts at `preview_ready`.** `phase4_coordinator` writes the `composing → preview_ready` UPDATE but never enqueues `worker_export`. The CI rule `ci/check_banned_patterns.py` blocks `arq.enqueue.*worker_export` inside coordinator code. | `[TDD-WORKERS]-J` disambiguation block. |
| **S11** | **Dual-Branch DLQ Routing.** `on_job_dead` dispatches strictly by `job.function_name`: `phase4_coordinator → failed_render`; `worker_export → failed_export`. Never branches on `gen.status`. | `[TDD-DLQ]-A/B`. |
| **S12** | **Worker `pre_topup_status` Denial.** No worker (L5/L6) writes this column. Only L2 routes (`/approve-strategy`, `/retry-export`) and the webhook handler. | `[TDD-WORKERS]-A` + `ci/check_pre_topup_writes.py`. |

### 5.8 Freeze Rules (Locked by `[PRD-UX-FREEZE]`)

| ID | Freeze | Enforcement |
|---|---|---|
| **Z1** | **Screen-Count Freeze.** Exactly 6 screens: HD-1..HD-6 (plus the peripheral `/grievance` route which is excluded from the linear flow). No more, no fewer in the linear flow. | `ux_freeze_guard.yml` CI job. |
| **Z2** | **22-State FSM Freeze.** No new ENUM values. Copy tweaks allowed; transitions are not. | `fsm_freeze_guard.py`. |
| **Z3** | **Layout Freeze.** HD-3 4-zone desktop / Tabs+FAB mobile is locked. HD-6 is one state-aware component, not split into routes. | Code-review CODEOWNERS. |
| **Z4** | **HD-4 Primary Button Freeze.** Exactly 3 modes: `approve`, `top_up`, `upgrade`. No 4th mode. | Server-driven mode field; CI checks. |
| **Z5** | **ECM Code Freeze.** ECM-001..ECM-020 are frozen. New copy requires PM sign-off on PRD itself. | `app/ui/copy/errors.ts` requires 2-reviewer approval. |
| **Z6** | **Flow Linearity.** Forward-only HD-1 → HD-6. Back-navigation only via the 4 [Edit] targets on HD-4 with NULL-downstream cascade. | Trigger-enforced FSM transitions. |
| **Z7** | **Migration Freeze (post-Day-10).** No destructive migrations after Sprint Day 10 (May 5). | Convention + Founder gate. |
| **Z8** | **FFmpeg `-shortest` Ban.** No FFmpeg command in the worker layer may use the `-shortest` flag. Audio is padded/trimmed to canonical 15s explicitly via `tpad` / `apad`. | `ci/check_banned_patterns.py` greps worker files. |

### 5.9 Dependencies with other sections

§5 is referenced by every later section. §7 (FSM) operationalizes S6, S7. §8 (Phase Architecture) operationalizes S10, S11. §12 (API Surface) operationalizes S3, S4, S5, S8. §13 (Failure Logic) operationalizes F2, F3, S11. §14 (Compliance) operationalizes L1..L7. §15 (Testing) verifies all of them.

---

## 6. Sequence User Journey HD-1 → HD-6

This section narrates, screen by screen, exactly what the user sees, what they do, what the system does in response, and which states the system traverses — in the order the user experiences them.

### 6.1 Purpose

This section is the linear UX contract; it is the projection of §7 (FSM) onto the user surface.

### 6.2 What this section defines

- Per-screen: entry state, primary user action, system response, transient states, exit state, mobile vs desktop variations, failure modes that stay on this screen.
- The strict linearity invariant and the four legal back-navigation targets (HD-4 [Edit] buttons).
- The two overlay surfaces (Top-Up Drawer, Plan Modal) that preserve resident state.

### 6.3 What this section does NOT define

- The 22-state FSM ENUM details (lives in §7).
- The technical implementation of any phase (lives in §8).
- The pixel-level UI tokens (lives in §10).
- The API endpoints invoked at each step (referenced here, defined in §12).

### 6.4 The Linear Map (Per `[PRD-FLOW]`)

| # | Screen | Resident State(s) | Transient States | Phase | Primary Action | Exit On Success |
|---|---|---|---|---|---|---|
| HD-1 | Product Ingestion | `queued` | `extracting` | 1 | Paste URL or upload image | Phase 1 complete → HD-2 |
| HD-2 | Isolation Review | `brief_ready` | — | 1 | Approve isolation | `/advance` → HD-3 |
| HD-3 | Creative Workspace | `scripts_ready` | `scripting`, `critiquing`, `safety_checking`, `regenerating` | 2 | Pick a script + optional Co-Pilot Chat | `/advance` → HD-4 |
| HD-4 | Your Ad Plan · Credit Gate | `strategy_preview` | `awaiting_funds`(pre='strategy_preview') (overlay) | 3 | Confirm & Use 1 Credit | `/approve-strategy` → HD-5 |
| HD-5 | Render Progress | `rendering` | `funds_locked`, `reflecting`, `composing` | 4 | Passive watch | `preview_ready` → HD-6 |
| HD-6 | Your Ad · Preview + Download | `preview_ready` → `export_queued` → `export_ready`; failure: `failed_export` (4a/4b); `awaiting_funds`(pre='failed_export') (overlay) | — | 4 | Sign 3 declarations → Download HD; Retry on failure | `export_ready` (terminal) |

### 6.5 HD-1 — Product Ingestion

**User sees:** A two-tab input — paste URL field (default) or upload image button (≤10MB JPEG/PNG). A list of the 5 supported Green Zone categories. An estimated-time microcopy ("Takes about 10 seconds…").

**User does:** Submits a URL or uploads an image.

**System does:** L2 validates → InputScrubber sanitizes (per F-501) → INSERT generation row at `status='queued'` → ARQ enqueues `phase1_extract` on `phase1_to_3_workers`. Worker-EXTRACT runs Firecrawl (15s timeout) → BiRefNet (Apache 2.0) (local) → Gemini Vision via gateway. Status transitions `queued → extracting → brief_ready`.

**Failures that stay on HD-1 (IF / THEN / ELSE branching):**

- **IF** category resolves to a Red Zone value → **THEN** transition to `failed_category`, emit ECM-001, surface `[Start Over]` (fresh `gen_id`); **ELSE** continue.
- **IF** InputScrubber detects prompt-injection or control characters → **THEN** transition to `failed_compliance`, emit ECM-002, surface `[Start Over]`; **ELSE** continue.
- **IF** Firecrawl exceeds the 15s timeout → **THEN** emit ECM-015, auto-select the upload tab; **ELSE** continue.
- **IF** the user's upload exceeds 10MB → **THEN** return 413 with ECM-014 inline-validation message; **ELSE** continue.
- **IF** the scraped image exceeds 15MB → **THEN** raise `CategoryError` and emit ECM-001 with `[Start Over]`; **ELSE** continue to BrifNet .

**Mobile:** single-column layout; upload uses `<input type="file" accept="image/*" capture>`.

### 6.6 HD-2 — Isolation Review

**User sees:** The isolated PNG on a checkerboard background, an ambient confidence ring around the image (green ≥0.90, yellow 0.85–0.89, red <0.85), a Source/Isolated toggle, primary and secondary buttons. Headline copy varies by confidence band.

**User does:** Approves isolation (`✓ Continue to Scripts →`) or re-uploads (`↻ Re-upload`).

**System does:** GET hydrates the row; SSE attaches. On `/advance`, status `brief_ready → scripting`; ARQ enqueues `phase2_chain`.

**Confidence is a visual signal only.** Per `[PRD-CONFIDENCE]`:

- **IF** `confidence_score < 0.85` → **THEN** primary CTA changes from "Continue" to "Re-upload" while keeping "Continue Anyway" as secondary; **ELSE** primary CTA remains "Continue".
- **No screen is skipped at any band.** Confidence never routes around HD-2.

### 6.7 HD-3 — Creative Workspace

**User sees (desktop ≥768px, 4-zone):** sticky chip bar (Audience · Benefit · Emotion · Language · Duration) at top. Below: SCRIPT zone (3 framework-tagged tiles, top pre-selected, each showing framework name + CRITIC score 0–100), STYLE zone (motion archetype, environment preset, voice, duration), CHAT zone (Co-Pilot, "X of 3 turns" counter, quick-action chips Punchier/Hinglish/Diwali, free-text ≤500 chars), DIRECTOR TIPS zone. Sticky bottom CTA "Continue to Strategy →".

**User sees (mobile <768px):** sticky horizontal-scroll chip bar; Tabs (Script | Style); FAB button opens Co-Pilot Chat in a Shadcn `Sheet` bottom-sheet (~70% viewport).

**User does:**

- **IF** the user changes a chip → **THEN** call `/regenerate`, run a full Phase 2 re-run, and reset the chat counter to 3 (this is irreversible to chat history); **ELSE** continue.
- **IF** the user types a refinement → **THEN** call `/chat` and run the 5-stage canonical chain (see §9); **ELSE** continue.
- **IF** the user clicks `✓ Continue` → **THEN** call `/advance`, run Worker-STRATEGIST in-process (zero external API), transition `scripts_ready → strategy_preview`, and route to HD-4; **ELSE** stay on HD-3.

**Failures that stay on HD-3 (IF / THEN / ELSE branching):**

- **IF** all three scripts fail safety → **THEN** transition to `failed_safety`, emit ECM-003, auto-retry with `SAFE_TRIO` once; if the retry also fails → surface `[Back to Scripts]`; **ELSE** continue.
- **IF** chat budget is exhausted (CostGuard) → **THEN** emit ECM-009, disable the chat input, keep "Continue" active; **ELSE** continue.
- **IF** chat turn count == 3 → **THEN** emit ECM-008, disable the chat input; **ELSE** continue.
- **IF** ComplianceGate rejects the prompt → **THEN** emit ECM-011, clear and re-enable the input, do **NOT** count the turn; **ELSE** continue.
- **IF** OutputGuard rejects the output → **THEN** emit ECM-010, re-enable the input, preserve COGS per F8, do **NOT** count the turn; **ELSE** continue.

### 6.8 HD-4 — Your Ad Plan · Credit-Usage Approval Gate

**User sees:** A "Strategy Card" summarizing 6 rows (Product · Targeting · Script · Style · Voice · Duration), each with `[Edit]`. A motion GIF preview loops. A Compliance Trust Row (✅ SGI · ✅ C2PA · ✅ 5-yr audit). Estimated render time. Credit balance + post-render balance. Server-driven primary button in one of three modes:

| Tier × Balance | Label | Behavior |
|---|---|---|
| Essential/Pro · ≥1 credit | `✓ Confirm & Use 1 Credit → Render` | `/approve-strategy` → Lua lock → `funds_locked` → HD-5 |
| Essential/Pro · =0 credits | `+ Add Credits to Render` | `awaiting_funds`(pre='strategy_preview') → Top-Up Drawer overlay |
| Starter | `⚡ Upgrade to Render` | Plan Modal; defensive 403 ECM-006 if direct-call attempted |

**User does:** Either edits one of the four legal targets, or confirms and spends a credit, or upgrades, or adds credits.

**[Edit] back-navigation matrix:**

| Target | Returns to | NULLed downstream | Pipeline re-runs |
|---|---|---|---|
| Product | `brief_ready` | scripts, scores, strategy, selection, motion, scene, b_roll_plan | Phase 2 full |
| Targeting | `scripts_ready` (then `regenerating`) | strategy, scripts, etc. | Phase 2 full |
| Script | `scripts_ready` | strategy_card, b_roll_plan | STRATEGIST only |
| Style | `scripts_ready` | strategy_card, b_roll_plan, motion, scene | STRATEGIST only |

**Top-Up Drawer overlay:** HD-4 dimmed but visible underneath; Shadcn `Sheet` (right on desktop, bottom on mobile) shows Essential ₹399 / Pro ₹1,499 cards with `Pay with UPI`. On Razorpay webhook `captured`, drawer auto-closes; user is restored to `strategy_preview` per S9.

### 6.9 HD-5 — Render Progress

**User sees:** Progress bar with percent, ETA seconds remaining, four named stage rows (Voice · Render · Select · Compose) with per-stage icons (⏳ pending, 🔄 running, ✅ complete). Provider-fallback toast appears as a transient banner if the gateway swaps a provider. On DLQ failure, an inline error card with "Your credit has been refunded" plus `[↻ Try Again]` and `[← Back to Strategy]`.

**User does:** Watches passively. On failure, clicks Try Again or Back to Strategy.

**System does:** `phase4_coordinator` runs the smart-stitch pipeline: parallel TTS + LLM prompt-preflight, then I2V attempt 1 (sequential early-exit), Worker-REFLECT (SSIM + deformation guard), fallback I2V attempt 2 if needed, then Worker-COMPOSE (FFmpeg filter_complex: 3s hook B-roll + 9s I2V + 3s CTA B-roll, LUT colour grade by benefit, SGI drawtext at bottom-left, AAC audio padded/trimmed to 15s — never `-shortest` per Z8). On success: `composing → preview_ready` → HD-6.

**Failure path (DLQ Branch A — Phase-4 Render):**

- **IF** any child of `phase4_coordinator` raises and exceeds `max_tries` → **THEN** `on_job_dead(function_name='phase4_coordinator')` invokes `wallet_refund.lua` plus the ledger refund row, transitions to `failed_render`, and emits SSE `render_failed` (<5s); **ELSE** continue.

**Recovery rationale (per F3):** because Phase-4 assets are incomplete on render failure, Try Again routes to HD-4 to re-lock — a full re-render is legitimate. This is the only state in the system where a fresh full render lock is acquired after a failure.

### 6.10 HD-6 — Your Ad · Preview + Download

HD-6 is one state-aware component with five visible states. The video player and download buttons are persistent across all five; only the upper inline panel changes.

**State 1 — `preview_ready` (landing):** 480p preview player (SGI-watermarked), three unsigned legal declaration checkboxes, two HD download buttons rendered but disabled. Microcopy: "Before you download the HD versions:".

**State 2 — `export_queued` (transient ~5–10s):** "Declaration signed · Processing HD exports…" Both HD buttons show "Preparing… C2PA signing…".

**State 3 — `export_ready` (terminal):** Both HD buttons active. "Your style has been saved for next time." with Manage / Reset Style Memory links. Quiet celebration: background fades to warm cream over 400ms (no confetti). "Credits remaining: N" + `[+ Create Another Ad →]`.

**State 4a — `failed_export`, fresh declaration ≤24h:** Player still visible. Inline card: "Export Failed. Your credit has been refunded. Your preview is intact — we just need to retry the final signing step. This uses 1 credit (no re-rendering needed)." `[↻ Retry Export · 1 Credit]` button. Retry counter "1 of 3".

**State 4b — `failed_export`, declaration stale >24h:** Inline 3-checkbox bank rendered above retry button. Retry disabled until 3/3 checked. On click, body carries `declarations:[true,true,true]`; server INSERTs new `audit_log` row atomically before lock per L3.

**`awaiting_funds`(pre='failed_export') overlay:** when retry Step 7 (lock) fails, HD-6 dims under the Top-Up Drawer. On Razorpay webhook `captured`, drawer closes and user is restored to `failed_export` (NOT to `strategy_preview`) per S9.

**Terminal failure variants (IF / THEN / ELSE):**

- **IF** `export_retry_count == 3` → **THEN** emit ECM-019 "Contact Support" with `[Start New Generation]`; **ELSE** continue.
- **IF** R2 HEAD on `preview_url` returns 404 (preview asset purged after >30d retention) → **THEN** emit ECM-018 "Assets Expired" with `[Start New Generation]`; **ELSE** continue.

**Why HD-6 is one state-aware component (not multiple routes):** the player and download buttons are visually persistent across all 5 states; only the upper inline panel changes. Splitting into routes would force the player to re-mount on every state transition and would conflict with the SSE-driven state model.

### 6.11 The Two Overlay Surfaces

| Overlay | Trigger | Underlying Screen Preserved | Dismissal |
|---|---|---|---|
| Top-Up Drawer (`<TopUpDrawer/>`) | `awaiting_funds` ENTER (Lua lock fail at HD-4 OR HD-6) | Yes (state and `pre_topup_status` both retained) | Webhook `captured` event auto-closes; SSE pushes restored state |
| Plan Modal (`<PlanModal/>`) | Starter clicks render → 403 ECM-006 | Yes (HD-4 underneath) | User clicks `[View Plans]` (links out) or `[Close]` |

These overlays are **not new screens**. They project onto the resident screen's state. The agent must not add new routes for them.

### 6.12 Dependencies with other sections

§6 is the user-facing projection of §7 (FSM). It depends on §10 (component tree) for which React component owns each surface. It depends on §12 (API surface) for which endpoint each action invokes. It depends on §13 (Failure Logic) for the ECM recovery flows referenced in each "Failures that stay on this screen" subsection.

---

## 7. Define 22-State FSM and Screen Mapping

This section enumerates the 22 ENUM values of `generations.status`, the legal transitions among them, the paired `pre_topup_status` invariant, and the deterministic mapping from each ENUM value to its resident screen and UI treatment.

### 7.1 Purpose

The FSM is the engineering source of truth; the UI is its reactive projection. UI is a function of `(status, pre_topup_status)`.

### 7.2 What this section defines

- The 22 status values grouped by phase.
- The legal-transitions DAG (per the Postgres trigger in `[TDD-FSM]`).
- The `pre_topup_status` paired-write invariant and the four `awaiting_funds` corner cases.
- The state → screen → UI-treatment matrix (MECE coverage of all 22 values plus 4a/4b sub-states).
- The role of `status_history` for forensic replay.

### 7.3 What this section does NOT define

- The user journey narrative (lives in §6).
- The phase-level orchestration (lives in §8).
- The DB schema details (column types, indices) — those live in §11.
- The retry-export 9-step chain — that lives in §13.

### 7.4 The 22 ENUM Values, Grouped by Phase

| Phase | ENUM Value | Resident Screen | Transient? |
|---|---|---|---|
| 1 (Ingestion) | `queued` | HD-1 | Resident |
| 1 | `extracting` | HD-1 | Transient |
| 1 | `brief_ready` | HD-2 | Resident |
| 2 (Strategy) | `scripting` | HD-3 | Transient |
| 2 | `critiquing` | HD-3 | Transient |
| 2 | `safety_checking` | HD-3 | Transient |
| 2 | `scripts_ready` | HD-3 | Resident |
| 2 | `regenerating` | HD-3 | Transient |
| 3 (Intent Gate) | `strategy_preview` | HD-4 | Resident |
| 3 | `awaiting_funds`(pre='strategy_preview') | HD-4 (Top-Up Drawer overlay) | Resident |
| 3 | `funds_locked` | HD-5 | Transient (<1s) |
| 4 (Production) | `rendering` | HD-5 | Transient |
| 4 | `reflecting` | HD-5 | Transient |
| 4 | `composing` | HD-5 | Transient |
| 4 | `preview_ready` | HD-6 | Resident |
| 4 | `export_queued` | HD-6 | Transient (~5–10s) |
| 4 | `export_ready` | HD-6 | Terminal (success) |
| 4 | `awaiting_funds`(pre='failed_export') | HD-6 (Top-Up Drawer overlay) | Resident |
| Failures | `failed_category` | HD-1 (re-entry) | Terminal |
| Failures | `failed_compliance` | HD-1 (re-entry) | Terminal |
| Failures | `failed_safety` | HD-3 (inline) | Recoverable |
| Failures | `failed_render` | HD-5 (inline) | Recoverable → HD-4 re-lock |
| Failures | `failed_export` | HD-6 (inline, 4a/4b) | Recoverable → /retry-export |

FSM transitions are externalized in `/state_transitions.yaml`. Execution **must**:

- Read transitions from YAML.
- Never embed transitions in code.
- CI (`ci/validate_state_machine.py`) enforces correctness before merge.

**MECE audit:** 22 ENUM values + 2 `awaiting_funds` projections (disambiguated by `pre_topup_status`) + 2 `failed_export` UI sub-states (4a/4b, disambiguated client-side by `NOW() - declaration_accepted_at > 24h`). 0 orphan states. 0 ambiguous resident screens.

### 7.5 The `pre_topup_status` Column

A second column on `generations`, ENUM-typed (same as `status`), nullable. It snapshots the origin screen at entry to `awaiting_funds` so the Razorpay webhook can restore the user atomically without hardcoding a destination.

| Outgoing State | `pre_topup_status` Value | Restored On Webhook |
|---|---|---|
| `strategy_preview` (lock fail at `/approve-strategy`) | `'strategy_preview'` | → `strategy_preview` (HD-4) |
| `failed_export` (lock fail at `/retry-export` Step 7) | `'failed_export'` | → `failed_export` (HD-6) |

**Coupling invariant (S6, enforced by CHECK + trigger):**

- `status='awaiting_funds'` IFF `pre_topup_status IN ('strategy_preview','failed_export')`.
- `status≠'awaiting_funds'` IFF `pre_topup_status IS NULL`.

**Write privilege:** only L2 routes (`/approve-strategy`, `/retry-export`) and the Razorpay webhook handler. All workers DENIED. CI rule `ci/check_pre_topup_writes.py` greps `app/workers/` for any UPDATE touching this column.

### 7.6 Legal Transitions DAG (Per `[TDD-FSM]` Trigger)

| From | Allowed To |
|---|---|
| `queued` | `extracting`, `failed_category`, `failed_compliance` |
| `extracting` | `brief_ready`, `failed_category`, `failed_compliance` |
| `brief_ready` | `scripting` |
| `scripting` | `critiquing`, `failed_safety` |
| `critiquing` | `safety_checking` |
| `safety_checking` | `scripts_ready`, `failed_safety` |
| `scripts_ready` | `strategy_preview`, `regenerating`, `brief_ready` |
| `regenerating` | `scripts_ready`, `failed_safety` |
| `strategy_preview` | `funds_locked`, `awaiting_funds`, `scripts_ready`, `brief_ready` |
| `awaiting_funds` | `strategy_preview`, `failed_export` *(both transitions clear `pre_topup_status` to NULL per Rule 2 below)* |
| `funds_locked` | `rendering`, `failed_render` |
| `rendering` | `reflecting`, `composing`, `failed_render` |
| `reflecting` | `composing`, `rendering`, `failed_render` |
| `composing` | `preview_ready`, `failed_render` |
| `preview_ready` | `export_queued` |
| `export_queued` | `export_ready`, `failed_export` |
| `export_ready` | (terminal) |
| `failed_category` | (terminal) |
| `failed_compliance` | (terminal) |
| `failed_safety` | `scripting` |
| `failed_render` | `strategy_preview` |
| `failed_export` | `export_queued`, `awaiting_funds` |

Any other transition raises `Invalid state transition` from the trigger function. The agent must not bypass the trigger via SQL.

### 7.7 The Three `awaiting_funds` Trigger Rules (Per `[TDD-FSM]`)

| Rule | Condition |
|---|---|
| **Rule 1 — Entering `awaiting_funds`** | `OLD.status='strategy_preview'` requires `NEW.pre_topup_status='strategy_preview'`; `OLD.status='failed_export'` requires `NEW.pre_topup_status='failed_export'`. |
| **Rule 2 — Exiting `awaiting_funds`** | Must clear `pre_topup_status` (NEW=NULL). Must restore to the snapshot: pre=`'strategy_preview'` → `NEW.status='strategy_preview'`; pre=`'failed_export'` → `NEW.status='failed_export'`. |
| **Rule 3 — All other transitions** | `NEW.pre_topup_status` MUST be NULL. |

Violations raise an exception inside the trigger; the application must handle as a 409 ECM-012 to the user.

### 7.8 `export_retry_count` Monotonicity

A separate trigger `enforce_export_retry_monotonic` ensures: NEW value ≥ OLD value (no decrement) AND NEW ≤ OLD + 1 (no skip). Increment happens exactly once per successful Step 8 of the `/retry-export` 9-step chain. Capped at 3 by CHECK constraint.

### 7.9 `status_history` — Forensic Replay

Every state transition writes a row to `status_history` (BIGSERIAL primary key, gen_id, from_status, to_status, from_pre_topup_status, to_pre_topup_status, changed_by, created_at). This table is the forensic record used in:

- DLQ post-mortem investigation (§13).
- State-corruption recovery (per `[TDD-ROLLBACK]-C`).
- AC-1..AC-6 audit verification (§15).

The table is never UPDATEd or DELETEd; it is append-only and `idx_status_history_gen_created` indexes the gen_id + created_at descending lookup pattern.

### 7.10 State → Screen → UI Treatment Matrix

| ENUM | `pre_topup_status` | Screen | UI Treatment |
|---|---|---|---|
| `queued` | NULL | HD-1 | Inline spinner; CTA disabled |
| `extracting` | NULL | HD-1 | "Analyzing your product…" shimmer |
| `brief_ready` | NULL | HD-2 | Isolated PNG + ambient confidence border |
| `scripting` | NULL | HD-3 | Shimmer over script-card zone |
| `critiquing` | NULL | HD-3 | "Scoring drafts…" shimmer |
| `safety_checking` | NULL | HD-3 | "Running safety filter…" shimmer |
| `scripts_ready` | NULL | HD-3 | Full workspace |
| `regenerating` | NULL | HD-3 | Single-card or full shimmer |
| `strategy_preview` | NULL | HD-4 | Strategy Card · primary `Confirm & Use 1 Credit` |
| `awaiting_funds` | `'strategy_preview'` | HD-4 | Strategy Card dimmed + Top-Up Drawer overlay |
| `awaiting_funds` | `'failed_export'` | HD-6 | Preview + failed_export context dimmed + Top-Up Drawer |
| `funds_locked` | NULL | HD-5 | "Starting render…" (transient <1s) |
| `rendering` | NULL | HD-5 | Progress + 4 stage rows |
| `reflecting` | NULL | HD-5 | "Selecting best render…" stage |
| `composing` | NULL | HD-5 | "Composing final video…" stage |
| `preview_ready` | NULL | HD-6 | Player + 3 unsigned declarations + disabled downloads |
| `export_queued` | NULL | HD-6 | Player + signed decls + "Preparing…" buttons |
| `export_ready` | NULL | HD-6 | Player + active downloads + Style Memory ack |
| `failed_category` | NULL | HD-1 (re-entry) | ECM-001 error card (full-screen) |
| `failed_compliance` | NULL | HD-1 (re-entry) | ECM-002 error card (full-screen) |
| `failed_safety` | NULL | HD-3 (inline) | ECM-003 alert; auto-retry 1×; else `[Back to Scripts]` |
| `failed_render` | NULL | HD-5 (inline) | ECM-004 alert + refund toast · `[↻ Try Again]` → HD-4 re-lock |
| `failed_export` (4a) | NULL | HD-6 (inline) | ECM-005 alert + refund toast + `[↻ Retry Export · 1 Credit]` |
| `failed_export` (4b) | NULL | HD-6 (inline) | ECM-005 + 3 inline checkboxes; retry disabled until 3/3 |

### 7.11 Dependencies with other sections

§7 is referenced by §8 (which phase owns which transition), §10 (which component renders which UI treatment), §12 (which endpoint legal-checks which transition), §13 (which failure ENUM maps to which recovery flow). The mock JSONs in `[PRD-UI-MOCKS]` MOCK-01..MOCK-19 are the storyboard for §10's Storybook coverage of every state.

---

## 8. Sequence 4-Phase Pipeline Build Order

This section defines the four-phase pipeline that transforms a product URL/image into a signed, downloadable HD ad — including which workers run in which phase, the canonical ARQ topology, and the explicit halt points.

### 8.1 Purpose

To make the build order phase-by-phase explicit so the agent always knows which worker depends on which.

### 8.2 What this section defines

- Phase 1 (Ingestion): EXTRACT pipeline + GreenZone gate.
- Phase 2 (Strategy): the dynamic playbook (12 frameworks → execute 3) + COPY/CRITIC/SAFETY chain + 5-stage Co-Pilot Chat.
- Phase 3 (Intent Gate): the mandatory HD-4 halt + the 4 [Edit] back-paths + the wallet lock entry point.
- Phase 4 (Production): the smart-stitch render + the decoupled Worker-EXPORT.
- The ARQ two-process bulkhead: `phase1_to_3_workers` vs `phase4_workers`.
- The cron jobs that run on `phase1_to_3_workers`.

### 8.3 What this section does NOT define

- The state machine transitions per phase (lives in §7).
- The API endpoints that trigger each phase (lives in §12).
- The recovery flows when a phase fails (lives in §13).
- The prompts each LLM call uses (lives in §9).

### 8.4 Phase 1 — Ingestion

**Entry:** `POST /api/generations` accepted; row inserted at `queued`.
**Trigger:** ARQ enqueue `phase1_extract` on `phase1_to_3_workers`.
**Workers involved:** Worker-EXTRACT.
**External calls:** Firecrawl scraper API (15s timeout) → BiRefNet (Apache 2.0) (local; pipeline globally loaded at worker startup) → Gemini Vision (via gateway, capability='vision').
**Outputs:** `isolated_png_url` (R2), `confidence_score`, `product_brief` JSONB (with category, key_features, color_palette, shape, optional price_inr), `agent_motion_suggestion` (only when confidence ≥ 0.90).

**Gates (IF / THEN):**

- **IF** upload exceeds 10MB → **THEN** L2 returns 413 ECM-014.
- **IF** scraped image exceeds 15MB → **THEN** Worker-EXTRACT raises `CategoryError` → ECM-001.
- **IF** category resolves to a Red Zone value → **THEN** raise `CategoryError` → ECM-001.
- **IF** L2 ingest InputScrubber detects prompt-injection patterns or control characters → **THEN** ECM-002.

**State transition:** `queued → extracting → brief_ready` (success) or `→ failed_category | failed_compliance` (failure, terminal on HD-1 re-entry).
**Exit:** SSE `phase_complete`; user lands on HD-2.

### 8.5 Phase 2 — Strategy (Dynamic Playbook)

**Entry:** `POST /gen/{id}/advance` from HD-2.
**Trigger:** ARQ enqueue `phase2_chain` on `phase1_to_3_workers`.
**Workers involved (canonical order):** Worker-COPY (router mode) → Worker-COPY (generate mode, parallel) → Worker-CRITIC → Worker-SAFETY → optional Co-Pilot Chat (Worker-COPY refine mode invoked from `/chat` route).

**The dynamic playbook (`[PRD-PLAYBOOK]`):**

1. Worker-COPY.framework_router: single LLM call with strict ENUM output. Returns `selected: [3 distinct AdFramework values]` + `rationale: dict` + `fallback_triggered: bool`. Default trio = 1 logic + 1 emotion + 1 conversion. On weak evidence → SAFE_TRIO = `[pas_micro, usage_ritual, social_proof]`.
2. Worker-COPY.generate_per_framework: `asyncio.gather` × 3, one LLM call per selected framework. Each script tagged with framework + framework_angle + evidence_note + suggested_tone.
3. Worker-CRITIC: scores all 3 scripts (no filtering). Tie-breaker by framework_angle (conversion > emotion > logic).
4. Worker-SAFETY: per-script moderation + PII regex (phone, email, Aadhaar) + competitor-name denylist. **IF** all 3 are rejected → **THEN** raise `SafetyError`; the caller auto-retries once with SAFE_TRIO; **ELSE** continue.

**Co-Pilot Chat (Phase 2 only, ≤3 turns):** 5-stage canonical chain — see §9 for details.

**Cardinality enforcement:** Postgres CHECK constraint `chk_routed_frameworks_cardinality` ensures `routed_frameworks` is exactly 3 distinct values when set.

**Outputs:** `routed_frameworks ad_framework[]`, `routing_rationale JSONB`, `raw_scripts JSONB[3]`, `critic_scores JSONB`, `safe_scripts JSONB`, `selected_script_id INTEGER` (defaulted to top scorer).
**State transition:** `scripting → critiquing → safety_checking → scripts_ready` (success) or `→ failed_safety` (terminal-recoverable, auto-retry-once with SAFE_TRIO).
**Exit:** SSE `phase_complete`; user lands on HD-3.

**Chip-change re-runs:** A chip change on HD-3 triggers `POST /regenerate` which UPDATEs the chip and NULLs all downstream fields (scripts, scores, refined_script, chat_history, chat_turns_used, motion, environment, b_roll_plan, strategy_card), enqueues `phase2_chain` again, and resets chat counter to 3. State `scripts_ready → regenerating → scripts_ready`.

### 8.6 Phase 3 — Intent Gate (HD-4)

**Entry:** Final Worker-STRATEGIST invocation from `POST /gen/{id}/advance` (the same advance route that closes Phase 2 also invokes STRATEGIST in-process — STRATEGIST is **never** enqueued as an ARQ job).
**Worker involved:** Worker-STRATEGIST. **ZERO external API access** — CI-enforced via `ci/strategist_sandbox_check.py` (AST-based import guard blocks httpx, requests, aiohttp, openai, anthropic, google.genai, boto3 from the strategist file).
**Reads:** `safe_scripts`, `user_style_profiles` (Style Memory), `health:{provider}` (Redis DB3), `cogs:{gen_id}` (Redis DB2), `director_tips`, `chat_turns_used`, `broll_clips`.
**Calls:** `BRollPlanner.plan(framework_angle, category)` — deterministic SQL query, no LLM, returns up to 3 clips matching archetype × category × is_active=TRUE × all-3-safety-flags-true.
**Writes:** `strategy_card JSONB`, `b_roll_plan JSONB`.

**The mandatory halt:** Phase 3 STOPS at `strategy_preview`. No render dispatched until the user clicks `Confirm & Use 1 Credit → Render`. This is the financial firewall (per U4).

**The four [Edit] back-paths (per §6.8):** Each NULLs the appropriate downstream fields and conditionally re-enqueues `phase2_chain` (for product/targeting) or just sets the status back (for script/style).

**The credit-lock entry point — `POST /approve-strategy`:**

1. `@idempotent` cache check (2xx-only).
2. `actlock:{gen_id}:approve-strategy` Redis fence (10s).
3. `SELECT ... FOR UPDATE` → assert `status='strategy_preview'`, `plan_tier ≠ 'starter'`. **IF** Starter → **THEN** 403 ECM-006; **ELSE** continue.
4. INSIDE `db.transaction()`: INSERT `wallet_transactions(type='lock', status='locked', credits=-1, gen_id)` → ledger first.
5. `redis_lua.wallet_lock(user_id, gen_id, credits=1)`.
6. **IF** lua returns 0 → **THEN** DELETE the optimistic ledger row, ATOMIC UPDATE `status='awaiting_funds', pre_topup_status='strategy_preview'`, raise 402 ECM-007; **ELSE** UPDATE `status='funds_locked'`.
7. After COMMIT: `arq.enqueue_job("phase4_coordinator", ...)` on `phase4_workers` queue.

**State transition:** `strategy_preview → funds_locked → (Phase 4)` (happy) or `strategy_preview → awaiting_funds → strategy_preview (after webhook restore) → funds_locked` (top-up path).

### 8.7 Phase 4 — Production (HD-5 → HD-6)

**Phase 4a — Render (Coordinator):**

Worker `phase4_coordinator` runs the smart-stitch pipeline:

1. State `funds_locked → rendering`.
2. **Parallel:** TTS (Sarvam Bulbul V3 for Indic; ElevenLabs/Google Cloud as fallbacks via gateway capability='tts') + LLM prompt-preflight (DeepSeek V3.2 via gateway capability='llm') optimizing the I2V prompt.
3. **Sequential early-exit:** I2V attempt 1 (9-second clip via Fal.ai primary, Minimax fallback) → state `rendering → reflecting` → Worker-REFLECT (SSIM + deformation guard).
4. **Fallback (IF / THEN):** **IF** REFLECT raises `ReflectError` → **THEN** run I2V attempt 2; re-run REFLECT. **IF** both attempts fail quality gates → **THEN** fall back to attempt 2 to avoid pipeline death; **ELSE** proceed.
5. State `reflecting → composing`.
6. Worker-COMPOSE (FFmpeg `filter_complex`: inject 2–4 B-roll clips fetched from DB intercut between A-roll segments based on scene_type mapping (Transition → motion/texture, Context → warehouse/packaging, etc.), LUT colour grade by benefit, SGI drawtext at bottom-left, AAC audio padded/trimmed to canonical duration via `tpad`/`apad` — never `-shortest` per Z8).
7. UPDATE `preview_url`, status `composing → preview_ready`.
8. `cost_guard.check_post_hoc(gen_id)` — emits `aw_cogs_overshoot_total` if ceiling breached (graceful, does not block user).
9. SSE `state_change: preview_ready` → user lands on HD-6.

**★★★ Coordinator STOPS HERE. ★★★** It does NOT enqueue `worker_export`. The state UPDATE to `preview_ready` IS authored by the coordinator; the enqueue of Worker-EXPORT is exclusively the responsibility of L2 routes `/declaration` (first-time) or `/retry-export` (retries). CI rule `ci/check_banned_patterns.py` blocks `arq.enqueue.*worker_export` inside `phase4_coordinator`.

**Phase 4b — Export (Decoupled Worker-EXPORT):**

Triggered by:

- `POST /declaration` (first-time): captures provenance, INSERTs `audit_log` row, transitions `preview_ready → export_queued`, enqueues `worker_export`.
- `POST /retry-export` (Steps 4–9 atomic chain): see §13 for the 9-step chain.

Worker-EXPORT (standalone ARQ job on `phase4_workers`):

1. SELECT generation row at `status='export_queued'` (idempotent — early return if not).
2. Validate `declaration_accepted = TRUE`.
3. R2 HEAD on `preview_url` (defensive); **IF** 404 → **THEN** `failed_export` + ECM-018; **ELSE** continue.
4. Download preview from R2 (credentialed boto3, NOT presigned).
5. FFmpeg scale to 1080×1080 + 1080×1920 (CRF=18).
6. `c2patool` sign each format. **Returncode strictly checked.** **IF** non-zero → **THEN** `C2PASignError` → DLQ branch B → `failed_export` + refund; **ELSE** continue.
7. Upload both signed exports to R2 (overwrites previous retry artifacts at the same path).
8. **Atomic DB transaction:** UPDATE `exports JSONB + c2pa_manifest_hash + status='export_ready'` AND UPDATE `wallet_transactions.status='consumed'` AND `redis_lua.wallet_consume`.
9. Best-effort: `StyleMemory.upsert_on_export` (200ms timeout; failure logged but not blocking).
10. SSE `state_change: export_ready`.

### 8.8 ARQ Two-Process Bulkhead

| Process | Queue Name | Functions Hosted | Concurrency | Job Timeout |
|---|---|---|---|---|
| **Process A — Interactive** | `phase1_to_3_workers` | `phase1_extract`, `phase2_chain`, `phase3_strategist` *(registered for ARQ but invoked **in-process** from `/advance` — never enqueued)*, `retention_sweep` (cron 02:00 IST), `r2_orphan_sweep` (cron Mon 02:30 IST), `partition_rotator` (cron 02:15 IST), `grievance_processor` (event-triggered), `takedown_sla_watchdog` (cron 5min) | tunable | per-job |
| **Process B — Heavy** | `phase4_workers` | `phase4_coordinator`, `worker_export` | `max_jobs=6` | `300s` (coord), `45s` (export) |

**Why two processes:** Phase 4 jobs are minutes-long, GPU/I/O intensive, and would starve the interactive workers if pooled together. The bulkhead prevents a stuck I2V job from blocking new HD-1 ingestions.

**ARQ deployment is fixed at exactly 2 processes per `[PRD-NON-GOALS-INFRA]`.** Adding a third worker process is a PRD change.

**Per-capability timeouts (ModelGateway):** I2V=180s, TTS=30s, COMPOSE=60s, EXPORT=45s, COORD=300s, LLM=15s.

### 8.9 Cron Schedule (All on `phase1_to_3_workers`)

| Job | Schedule (IST) | Purpose |
|---|---|---|
| `retention_sweep` | Daily 02:00 | Starter 7d / Paid 30d source/preview purge + 5y export purge (DB-first, R2-second atomicity) |
| `partition_rotator` | Daily 02:15 | Pre-create next-month `audit_log` partition + REVOKE UPDATE/DELETE on PUBLIC |
| `r2_orphan_sweep` | Weekly Mon 02:30 | Catch any R2 objects whose DB row no longer references them |
| `takedown_sla_watchdog` | Every 5 min | Page on grievance unresolved <1h before 24h ACK or 15-day deadline |
| `cb_state_publisher` | Every 1 min (optional) | Publish circuit-breaker state to Grafana metrics |

### 8.10 Dependencies with other sections

§8 implements §7's transitions. §9 details the LLM orchestration inside Phase 2 and inside the coordinator's prompt-preflight call. §11 details the worker-permission matrix and the schema rows each worker reads/writes. §12 details the API entry points that trigger each phase. §13 details what happens when each phase fails. §14 details the compliance writes (audit_log, c2pa) embedded in Phase 4.

---

## 9. Wire Playbook Routing and Co-Pilot Chain

This section defines the bounded AI orchestration patterns that distinguish AdvertWise from open-ended generative tools: the 12-framework dynamic playbook, the 5-stage Co-Pilot Chat chain, the deterministic B-Roll Planner, and the ModelGateway with capability-keyed routing and circuit-breaker FSM.

### 9.1 Purpose

To make the playbook routing logic, chat chain ordering, and gateway selection deterministic and CI-asserted.

### 9.2 What this section defines

- The 12-framework ENUM, the 4 routing dimensions, the safety rules, the SAFE_TRIO fallback.
- The canonical 5-stage Co-Pilot Chat chain order and the rejected-turn-leak fix.
- The deterministic B-Roll Planner archetype map.
- The ModelGateway capability pool, scoring engine, circuit-breaker FSM.
- The PromptOps directory layout and the strict input/output schema invariant.

### 9.3 What this section does NOT define

- The user-facing chat UI (lives in §10).
- The chat API endpoint shape (lives in §12).
- The chat failure ECM codes (lives in §13).
- The prompt content of each YAML file (lives in TDD `[TDD-PROMPTS]-D..F`).

### 9.4 The 12-Framework Dynamic Playbook

The `ad_framework` Postgres ENUM is the single source of truth. The 12 values group into four families:

| Family | Frameworks | Default Angle |
|---|---|---|
| Problem/Efficacy | `pas_micro`, `clinical_flex`, `myth_buster` | logic |
| Sensory/Desire | `asmr_trigger`, `usage_ritual`, `hyper_local_comfort` | emotion |
| Status/Value | `spec_drop_flex`, `premium_upgrade`, `roi_durability_flex` | logic or emotion |
| Urgency/Conversion | `festival_occasion_hook`, `scarcity_drop`, `social_proof` | conversion |

**Routing inputs (4 dimensions):** Creative Goal (e.g., stop-scroll, build-trust), Evidence Strength (e.g., spec/claim, demo/texture, social-proof), Visual Fit (e.g., close-up, packaging, before-after), Audience State (cold, warm-retargeting, festival-buyer, etc.).

**Selection rule:** Worker-COPY.framework_router selects exactly 3 distinct frameworks. Default trio covers 1 logic + 1 emotion + 1 conversion. On weak evidence, falls back to **SAFE_TRIO = [pas_micro, usage_ritual, social_proof]**.

**Safety rules (IF / THEN):**

- **IF** evidence is weak → **THEN** avoid claim-led (`clinical_flex`, `spec_drop_flex`).
- **IF** evidence is strong factual → **THEN** prefer claim-led.
- **IF** visuals are motion/texture-rich → **THEN** prefer sensory.
- **IF** product is premium / high-consideration → **THEN** prefer `premium_upgrade` / `roi_durability_flex`.
- **IF** date falls in festival/payday calendar → **THEN** prefer `festival_occasion_hook`.
- **IF** no framework matches → **THEN** fall back to SAFE_TRIO.

**Output contract (Pydantic `FrameworkRoutingOutput`):** `selected: list[str] (min=3, max=3)` + `rationale: dict[str, str]` + `fallback_triggered: bool`. Validator enforces `len(set(selected)) == 3`. CI fixtures `[TDD-API-STUBS]-C` test high-evidence, low-evidence (SAFE_TRIO), and schema-violation cases.

**Cardinality enforcement at DB:** CHECK constraint `chk_routed_frameworks_cardinality` ensures the array always contains exactly 3 distinct values when set.

### 9.5 The 5-Stage Canonical Co-Pilot Chat Chain

Bounded refinement layer above the framework engine. Phase 2 only. Max 3 turns/gen, ~₹0.08/turn. Each turn is a separate POST `/api/generations/{gen_id}/chat`.

**Stage order (CI-asserted by `tests/test_chat_chain_order.py`):**

| #   | Stage                                   | Module                                        | Purpose                                                                                                                         | On Reject                                                                                                             |
| --- | --------------------------------------- | --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| 0   | Pre-chain                               | `@idempotent` + `actlock:{gen_id}:chat` (10s) | Prevent double-click + cross-tab race                                                                                           | Cached 2xx returned, OR 409 ECM-012                                                                                   |
| 1   | ComplianceGate.check_input              | `app/services/compliance_gate.py`             | Prompt-injection + control chars + word count ≤20                                                                               | 400 ECM-011, no LLM call, turn NOT counted, NO COGS                                                                   |
| 2   | CostGuard.pre_check (est_cost=0.08)     | `app/services/cost_guard.py`                  | Budget projection vs ceiling                                                                                                    | 429 ECM-009, no LLM call, turn NOT counted, NO COGS                                                                   |
| 3   | LLM via gateway.route(capability='llm') | `app/infra_gateway.py`                        | Render `script-refine.v1.0.0.yaml` prompt; DeepSeek V3.2 via gateway pool; 15s timeout                                          | ProviderUnavailableError → 503; turn NOT counted; NO COGS                                                             |
| 4   | **CostGuard.record (immediate)**        | `app/services/cost_guard.py`                  | HINCRBYFLOAT cogs:{gen_id} + INSERT agent_traces row                                                                            | (always fires before Stage 5)                                                                                         |
| 5   | OutputGuard.check_output                | `app/services/output_guard.py`                | Llama Guard via gateway capability='moderation' + PII regex + competitor name regex                                             | 422 ECM-010; UPDATE generations.cogs_total += last_cost (sync Postgres ledger with Redis); turn NOT counted; NO cache |
| 6   | COMMIT                                  | atomic state-guarded UPDATE                   | Increment `chat_turns_used`, append `chat_history`, accumulate `cogs_total`. WHERE status='scripts_ready' AND chat_turns_used<3 | rowcount=0 → 409 ECM-012, NO cache                                                                                    |

**The rejected-turn-leak fix:** Stage 4 fires BEFORE Stage 5. This means a prompt that produces unsafe output STILL records its COGS — preventing adversarial budget-draining via repeated `/chat` calls that intentionally trip OutputGuard.

**Cache semantics:** Only the COMMIT path (success) caches the response (300s TTL). All 4xx and 5xx paths skip the cache. Client drops localStorage idempotency key on receipt of any 4xx and re-issues a fresh UUIDv4.

### 9.6 Deterministic B-Roll Planner

**Why deterministic:** the B-Roll planner avoids LLM calls and pgvector searches to keep Worker-STRATEGIST true to its zero-external-API invariant. Same `(framework_angle, category)` always returns the same `clip_id` list.

**Method:** `BRollPlanner.plan(framework_angle, category)` runs SQL against `broll_clips` filtered by:

- `archetype = ANY($archetypes_for_angle)` (e.g., emotion → sensory archetypes)
- `category = $category::green_zone_category`
- `is_active = TRUE`
- `excludes_faces = TRUE AND excludes_hands = TRUE AND excludes_locations = TRUE` (also enforced by `chk_broll_safety` constraint at insert time)

**ORDER BY:** `array_position($archetypes, archetype) ASC, clip_id ASC` — total ordering ensures determinism.

**Output:** up to 3 BRollClip dicts; empty list is valid (graceful degrade — STRATEGIST proceeds without B-Roll); `chk_b_roll_plan_shape` constraint caps storage at 3.

**Integration:** Worker-STRATEGIST persists `b_roll_plan` to `generations` row; Worker-COMPOSE reads it at composition time and intercuts per the 15s smart-stitch timeline.

### 9.7 ModelGateway — Capability-Keyed Routing

**The single chokepoint for all external API calls.** Every worker (except STRATEGIST, which has zero external access) routes through `gateway.route(capability=..., input_data=...)`. CI rule blocks direct httpx/requests/aiohttp imports in worker files.

**Capability pool (per `[TDD-OVERVIEW]` L8):**

- `llm`: DeepSeek V3.2, Groq, Gemini, Together AI, SiliconFlow.
- `vision`: Gemini Vision Pro, GPT-4V.
- `tts`: Sarvam (Bulbul V3), ElevenLabs, Google Cloud.
- `i2v`: Fal.ai (primary), Minimax (fallback). [PRD lists Wan2.2 + Kling 2.6 as roadmap; MVP uses Fal/Minimax.]
- `moderation`: Groq (Llama Guard).
- `embedding`: OpenAI text-embedding-3-small (1536-dim).
- `scraping`: Firecrawl.

**Scoring engine (`_rank_providers`):**

1. Block 1: Capability candidate list.
2. Block 2: Context check — Indic language → preferred Sarvam (boost +500 to health score guaranteeing top placement).
3. Block 3: Health score from Redis DB3 `health:{provider}` (default 100 if unset).
4. Sort: highest health first, ties broken by lowest cost weight.

**Circuit Breaker FSM (`circuit_breaker.lua`):** CLOSED (healthy) → OPEN (failure threshold breached, 60s cooldown) → HALF_OPEN (3 probes during cooldown expiry; success → CLOSED, failure → re-OPEN). Per-provider hash in Redis DB3.

**Fallback execution loop:** for each ranked provider, check breaker, attempt with capability-specific timeout; on success, record success + COGS, return; on failure, record failure (which may trip OPEN), continue to next. If all exhausted: raise `ProviderUnavailableError`.

**SSE event:** every fallback emits `provider_fallback` toast on the client (informational; no state change).

### 9.8 PromptOps — Versioned YAML Contracts

Every prompt lives in `app/prompts/<domain>/<id>.v<semver>.yaml` with strict Pydantic / JSON-schema input and output contracts.

**Catalog (Phase 2 + 3 + 4 prompts):**

- Extraction: `product-brief.v3.2.0.yaml`, `category-classifier.v1.1.0.yaml`.
- Copywriting: `framework-router.v1.0.0.yaml`, `script-generator-per-framework.v1.0.0.yaml`, `script-refine.v1.0.0.yaml`, `hinglish-adapter.v1.0.0.yaml`.
- Critique: `script-critic.v2.5.0.yaml`, `brand-safety.v1.2.0.yaml`.
- Strategy (UI-only, no LLM): `motion-recommendation.v1.0.0.yaml`, `environment-recommendation.v1.0.0.yaml`, `reasoning-templates.v1.0.0.yaml`.
- Reflection: `deformation-guard.v1.3.0.yaml`, `i2v-selector.v1.0.0.yaml`.
- Composition (deterministic, but kept here for LUT-policy versioning): `timeline-composer.v1.1.0.yaml`.

**Loading:** `PromptCatalog._load_all` reads `catalog.yaml` index, asserts `prompt_id` and `system_prompt` and `user_prompt_template` keys present, registers as `{prompt_id}@{version}` for grep.

**Rendering:** Jinja2 with `StrictUndefined` (any unfilled variable raises). Output validated against the YAML's `output_schema` block via `PromptCatalog.validate_output`.

**Token compression:** all system prompts enforce minified, schema-less JSON output. No conversational filler. No reasoning trace. Pure JSON object.

**CI:** `ci/validate_prompts.py` parses every YAML and asserts the contract keys exist plus the version semver matches the filename.

### 9.9 The Phase-4 Coordinator's LLM Prompt-Preflight

Inside `phase4_coordinator`, after acquiring funds_lock and before the I2V call, the coordinator runs an LLM prompt-preflight in PARALLEL with TTS:

> System prompt: "You are a master cinematographer. Convert the inputs into a highly dense, comma-separated camera and lighting prompt optimized for AI video models. Max 30 words."
>
> User prompt: "Product: {product_brief.product_name}. Motion: {MOTION_NAMES[motion_archetype_id]}. Environment: {ENV_NAMES[environment_preset_id]}."

The output is fed into `WorkerI2V.process` as `optimized_i2v_prompt`. This is the only LLM call inside Phase 4; everything else (TTS, I2V, REFLECT, COMPOSE) is non-LLM external API or local subprocess.

### 9.10 Dependencies with other sections

§9 is invoked by §8 (Phase 2 chain, Phase 4 coordinator). §11 hosts the `ad_framework` ENUM and `broll_clips` table. §12's `/chat`, `/regenerate`, `/advance` routes are the user-facing surfaces of this section. §15 lists the CI tests that lock this orchestration.

---

## 10. Compose UI Tree and Design Tokens

This section defines the frontend execution surface: the Next.js 15 app router structure, the component hierarchy that maps 1:1 to the 6 screens and the overlays, the design-token dictionary, the state-management pattern, and the storyboard mock JSONs.

### 10.1 Purpose

To make every UI artifact name and slot deterministic so the agent never has to invent a component name or tailwind token.

### 10.2 What this section defines

- The `frontend/` directory tree (per `[PRD-UI-TREE]`).
- The 14 ShadcnUI primitives allowed for MVP (and the rule that no others may be imported).
- The design-token tables (colors, typography, spacing, motion, breakpoints).
- The state hydration pattern: `GET /api/generations/{gen_id}` on mount BEFORE SSE attach.
- The 19 mock JSONs that fixture every UI state, plus the SSE event examples.
- The error-to-component mapping: which ECM code renders which React component.

### 10.3 What this section does NOT define

- The actual component code (lives in implementation, scaffolded by TDD).
- The state machine values (lives in §7).
- The API call sequence (lives in §12).
- The error copy text — that's frozen in `[PRD-ERROR-COPY]`.

### 10.4 Frontend Directory Tree (Top-Level)

```
frontend/
├── app/
│   ├── (root layout, tailwind globals, error boundaries)
│   └── [gen_id]/
│       ├── page.tsx                 # Entry; routes to HD-1..HD-6 by status
│       └── error.tsx                # Boundary for ECM-013 HYDRATION_FAILED
├── components/
│   ├── hd/
│   │   ├── HD1Ingestion.tsx
│   │   ├── HD2IsolationReview.tsx
│   │   ├── HD3CreativeWorkspace/
│   │   │   ├── ScriptZone.tsx
│   │   │   ├── StyleZone.tsx
│   │   │   ├── ChipBar.tsx
│   │   │   ├── DirectorTips.tsx
│   │   │   └── CoPilotChatSheet.tsx
│   │   ├── HD4StrategyCard.tsx
│   │   │   ├── StrategySummary.tsx
│   │   │   ├── ComplianceTrustRow.tsx
│   │   │   └── MotionGifPreview.tsx
│   │   ├── HD5RenderProgress.tsx
│   │   └── HD6Preview.tsx           # Single state-aware composite (5 states + 4a/4b)
│   │       ├── StatePreviewReady.tsx
│   │       ├── StateExportQueued.tsx
│   │       ├── StateExportReady.tsx
│   │       ├── StateFailedExport4a.tsx
│   │       ├── StateFailedExport4b.tsx
│   │       ├── VideoPlayer.tsx
│   │       ├── DeclarationCheckboxes.tsx
│   │       ├── RetryExportPanel.tsx
│   │       └── StyleMemoryAck.tsx
│   ├── shared/
│   │   ├── ConfidenceBorder.tsx
│   │   ├── FrameworkLabel.tsx
│   │   ├── ScriptCard.tsx
│   │   ├── MotionSelector.tsx
│   │   ├── SceneSelector.tsx
│   │   ├── TopUpDrawer.tsx          # State-aware: overlays HD-4 OR HD-6 by pre_topup_status
│   │   ├── PlanModal.tsx
│   │   ├── ErrorToast.tsx           # sonner wrapper
│   │   ├── EcmErrorCard.tsx         # Full-screen for ECM-001/002/013
│   │   └── LoadingShimmer.tsx
│   └── ui/                          # Shadcn primitives (generated, not hand-edited)
├── lib/
│   ├── api/{client.ts, types.ts, endpoints.ts}
│   ├── sse/client.ts                # EventSource wrapper, exponential backoff 1→2→4→30s
│   ├── idempotency/keys.ts          # localStorage key schema
│   ├── state/store.ts               # Zustand
│   ├── tokens.ts                    # Design-token TS constants (mirror of CSS vars)
│   └── utils.ts
├── shared/types/                    # Symlinked source-of-truth shared with backend
│   ├── job_status.ts                # JobStatus union (22 values)
│   ├── ad_framework.ts              # AdFramework enum + FRAMEWORK_ANGLE_MAP + SAFE_TRIO
│   ├── ecm_codes.ts                 # ECM_CODES const record
│   ├── generation.ts                # GenerationState interface
│   └── api.ts
├── tailwind.config.ts
├── components.json                  # Shadcn config
├── next.config.mjs
└── package.json
```

**Hard rules:**

- No new top-level routes under `/app/*` that don't map to HD-1..HD-6 (per Z1 + `ux_freeze_guard.yml`).
- No hand-edits to `components/ui/*` (shadcn-cli owns these).
- `shared/types/` is symlinked from backend; both layers consume the same types.
- Peripheral route `/grievance` exists outside the 6-screen linear flow. Accessible only via footer. No impact on execution sequence.

### 10.5 ShadcnUI Allowlist (14 primitives)

`Button`, `Card`, `Dialog`, `Sheet`, `Tabs`, `Checkbox`, `Input`, `Label`, `Toast` (via `sonner`), `Progress`, `Skeleton`, `Badge`, `Alert`, `AlertDialog`. Any additional component requires a PRD change. ShadcnUI base config: `style: new-york`, `rsc: true`, `tsx: true`, `baseColor: slate`, `cssVariables: true`.

### 10.6 Design Token Dictionary

Per `[PRD-DESIGN-TOKENS]`, the agent builds `tailwind.config.ts` verbatim from these tables.

**Brand:**

- `brand.primary`: teal-600 (#0D9488 light) / teal-300 (#5EEAD4 dark)
- `brand.primary-hover`: teal-700 / teal-400
- `brand.primary-fg`: white / slate-900
- `brand.accent`: amber-500 / amber-400 (Credit/₹ indicators)
- `brand.muted`, `brand.border`, `brand.fg`, `brand.fg-muted`: slate variants

**Confidence (non-negotiable per `[PRD-CONFIDENCE]`):**

- `confidence.high`: emerald-500 (#10B981) — `score ≥ 0.90`
- `confidence.medium`: amber-500 — `0.85 ≤ score < 0.90`
- `confidence.low`: red-500 — `score < 0.85`
- Each has a paired `-bg` token for ambient fill.

**State semantic tokens:**

- `state.success`: emerald-500 (`export_ready`, `declaration_signed`)
- `state.warning`: amber-500 (`awaiting_funds` drawer header, retry counter)
- `state.danger`: red-500 (`failed_render`, `failed_export`, ECM-018, ECM-019)
- `state.info`: sky-500 (provider-swap toasts, SSE reconnect banner)

**Typography:**

- `font.sans`: system stack including `Noto Sans Devanagari` (REQUIRED for ₹ glyph and future Indic UI). No webfont downloads — first-paint performance on Indian 3G/4G networks is a constraint.
- Scale: text-xs (12px) through text-3xl (30px).
- Weights: 400 / 500 / 600 / 700 (700 reserved for screen titles only).

**Spacing / Radius / Shadow:** per `[PRD-DESIGN-TOKENS]`. `space.4` (16px) is mobile card padding; `space.6` (24px) is desktop. `radius.lg` (14px) for cards/script tiles; `radius.xl` (20px) for sheets/modals.

**Motion:** `motion.fast` (150ms hover), `motion.base` (250ms sheet/tab), `motion.slow` (400ms — reserved for the **quiet celebration** background fade on `export_ready`). `motion.reduce` honors `prefers-reduced-motion`.

**Breakpoints:** `bp.md` (768px) is the **mobile/desktop split** for HD-3 layout switch.

### 10.7 State Hydration Pattern

The frontend maintains a single Zustand store hydrated from `GET /api/generations/{gen_id}` on every mount and on every SSE reconnect. This is the resilience contract:

1. On mount: synchronous GET completes BEFORE the SSE EventSource is attached. Closes the missed-event gap from server warm-up.
2. SSE attach: subscribes to `/api/sse/{gen_id}`. Events update the store reactively.
3. SSE reconnect: exponential backoff (1s → 2s → 4s → max 30s). On reconnect, re-issue GET to close any missed-event gap during the disconnect window.
4. Cross-tab sync: `storage` event listener on `localStorage` propagates idempotency keys and triggers refresh in other tabs.

### 10.8 Idempotency Keys

`localStorage` schema: `aw_idem_{user_id}_{gen_id}_{action}`. UUIDv4 generated per click. Sent in `Idempotency-Key` HTTP header on every mutating call.

**Special case — `/retry-export`:** monotonic key suffix `:{export_retry_count}` — the 2nd retry uses `:retry-export:2`, not `:retry-export:1`. Prevents cache collision across retries.

**Client clear rule:** on receipt of 4xx (400, 402, 409, 428), client drops the localStorage key and generates a fresh UUIDv4 for the next click.

### 10.9 Mock JSON Fixtures (Storyboard for Storybook + Playwright)

The 19 mocks in `[PRD-UI-MOCKS]` MOCK-01..MOCK-19 are the canonical fixtures. Every component has a Storybook story per relevant mock. Playwright E2E tests seed state via an internal `/api/test/seed-mock` route accepting any of these mocks verbatim.

**Coverage by screen:**

- HD-1: MOCK-01 (queued/extracting).
- HD-2: MOCK-02 (high confidence), MOCK-03 (low confidence).
- HD-3: MOCK-04 (scripts_ready, 3 framework-tagged), MOCK-05 (post-chat refinement).
- HD-4: MOCK-06 (essential, balance ≥1), MOCK-07 (awaiting_funds pre='strategy_preview'), MOCK-08 (Starter, upgrade button).
- HD-5: MOCK-09 (rendering 62%), MOCK-10 (failed_render).
- HD-6: MOCK-11 (preview_ready), MOCK-12 (export_queued), MOCK-13 (export_ready), MOCK-14 (failed_export 4a fresh), MOCK-15 (failed_export 4b stale), MOCK-16 (awaiting_funds pre='failed_export'), MOCK-17 (ECM-019 retry exhausted), MOCK-18 (ECM-018 assets expired).
- SSE events: MOCK-19 (samples of state_change, chat_turn, provider_fallback, lock_failed, render_failed, export_failed, topup_captured).

### 10.10 Error-to-Component Mapping

Per `[PRD-ERROR-MAP]`, each ECM code routes to a specific component. The agent must use the Target Component column verbatim — no new error surfaces.

| ECM | Surface | Component Path |
|---|---|---|
| ECM-001, ECM-002 | `<EcmErrorCard/>` full-screen | `components/shared/EcmErrorCard.tsx` |
| ECM-003 | `<Alert variant="destructive"/>` inline on HD-3 | inside `HD3CreativeWorkspace.tsx` |
| ECM-004 | `<Alert/>` + buttons on HD-5 | `HD5RenderProgress.tsx` |
| ECM-005, ECM-016 | `<StateFailedExport4a/4b/>` inline on HD-6 | `HD6Preview/StateFailedExport*.tsx` |
| ECM-006 | `<PlanModal/>` Shadcn Dialog | `shared/PlanModal.tsx` |
| ECM-007 | `<TopUpDrawer/>` Shadcn Sheet | `shared/TopUpDrawer.tsx` |
| ECM-008, ECM-009, ECM-010, ECM-011 | `<Alert/>` inside `<CoPilotChatSheet/>` | `HD3CreativeWorkspace/CoPilotChatSheet.tsx` |
| ECM-012 | `<ErrorToast/>` (sonner) | `shared/ErrorToast.tsx` |
| ECM-013 | `app/[gen_id]/error.tsx` (Next.js error boundary) | full-screen route boundary |
| ECM-014 | inline Label error on HD-1 | `HD1Ingestion.tsx` |
| ECM-015 | inline Alert + tab auto-switch on HD-1 | `HD1Ingestion.tsx` |
| ECM-017 | red flash on unchecked Checkbox | `HD6Preview/DeclarationCheckboxes.tsx` |
| ECM-018, ECM-019 | terminal inline card on HD-6 | `HD6Preview/StateFailedExport*.tsx` (terminal variants) |
| ECM-020 | `<StateFailedExport4b/>` inline checkbox bank | `HD6Preview/StateFailedExport4b.tsx` |

**Surface-type decision rule (IF / THEN):**

- **IF** the error is unrecoverable on the same screen (ECM-001/002/013) → **THEN** render full-screen.
- **ELSE IF** the error is recoverable on the same screen (ECM-003–005, 014–020) → **THEN** render inline.
- **ELSE IF** the error is ephemeral (ECM-012) → **THEN** render as toast.
- **ELSE IF** the error requires user action (ECM-006/007) → **THEN** render as drawer or modal.

### 10.11 Dependencies with other sections

§10 implements §6 (the user journey is rendered by these components), §7 (the resident screen for each ENUM determines which component mounts), §13 (the ECM error surface routing). The mock JSONs in §10.9 are the test fixtures used in §15 (Testing Strategy).

---

## 11. Catalog Postgres/Redis/R2 Storage Substrate

This section catalogs every persistent storage surface — Postgres (Neon, ledger), Redis (6-DB namespace, lock + cache), Cloudflare R2 (asset storage with retention rules) — plus the worker-permission matrix that governs read/write privileges across them.

### 11.1 Purpose

To enumerate the storage substrate so the agent never invents a table, key, or bucket path.

### 11.2 What this section defines

- Postgres tables (purpose, key columns, key constraints, key indices). Implementation lives in TDD; this section is the catalog.
- Redis 6-DB namespace (DB0..DB5) with key patterns and TTLs.
- R2 bucket structure with retention and overwrite semantics.
- The worker-permission matrix: which worker may read/write which table.
- The external-services and credentials catalog (§11.11 below).

### 11.3 What this section does NOT define

- The full DDL (lives in `[TDD-SCHEMA]` and `[TDD-MIGRATIONS]`).
- The Lua script bodies (lives in `[TDD-REDIS]-B/C/D/E`).
- The retention sweep cron logic (lives in `[TDD-R2-RETENTION]`).
- The SQL triggers (lives in `[TDD-FSM]`).

### 11.4 Postgres Tables (Catalog)

| Table | Purpose | Key Columns / Constraints | Notes |
|---|---|---|---|
| **`generations`** | The JSONB god-table; one row per generation | `gen_id PK`, `user_id FK`, `status job_status`, `pre_topup_status job_status NULL`, `plan_tier`, `routed_frameworks ad_framework[]`, `raw_scripts JSONB[3]`, `chat_turns_used 0..3`, `export_retry_count 0..3`, `strategy_card JSONB`, `b_roll_plan JSONB ≤3`, `preview_url`, `exports JSONB`, `cogs_total DECIMAL`, `declaration_*` provenance columns, `dlq_dead_at`, `dlq_original_task`. Constraints: `chk_pre_topup_coupling`, `chk_routed_frameworks_cardinality`, `chk_product_brief_shape`, `chk_exports_shape`, `chk_strategy_card_shape`, `chk_b_roll_plan_shape`. | Pillar 4 (Deep Module). All Phase 1–4 fields in one row. |
| **`users`** | User identity + plan + session versioning | `user_id PK`, `google_id UNIQUE`, `email UNIQUE`, `plan_tier`, `credits_remaining`, `plan_expires_at`, `session_version` (instant token revocation), `beta_invited` | `idx_users_beta_invited` partial. |
| **`wallet_transactions`** | Immutable financial ledger (split-status schema) | `txn_id PK`, `type` ('topup'\|'lock'\|'consume'\|'refund'\|'expire'), `credits`, `razorpay_payment_id`, `payment_status payment_status` (topup only), `status wallet_status` (lock/consume/refund only), `gen_id FK`. Constraints: `chk_wallet_status_coupling`. | Indices: `ux_wallet_topup_dedup`, `ux_wallet_active_lock`, `ux_wallet_refund_dedup`. |
| **`audit_log`** | Partitioned monthly; immutable; 5-year DETACH retention | `id BIGSERIAL`, `gen_id`, `user_id`, `action`, `payload JSONB`, `ip_address INET`, `user_agent TEXT`, `declaration_sha256`, `created_at` (partition key). PRIMARY KEY (id, created_at). | DB role REVOKE UPDATE/DELETE on every partition; daily `partition_rotator` cron pre-creates next-month partition. |
| **`status_history`** | Forensic record of every FSM transition | `id BIGSERIAL`, `gen_id FK`, `from_status`, `to_status`, `from_pre_topup_status`, `to_pre_topup_status`, `changed_by`, `created_at` | Index: `idx_status_history_gen_created`. Append-only. |
| **`compliance_log`** | Compliance check events with strict 4-string `check_type` taxonomy | `gen_id FK`, `check_type` IN ('c2pa_sign','sgi_burn_in','declaration_capture','freshness_check'), `result` IN ('pass','fail','warn'), `details JSONB` | CI: `validate_compliance_taxonomy.py`. |
| **`agent_traces`** | Per-LLM-call cost ledger | `gen_id FK`, `worker`, `framework ad_framework NULL`, `input_summary`, `output_summary`, `model_used`, `tokens_in/out`, `cost_inr DECIMAL`, `latency_ms`, `selection_reason` | Index: `idx_agent_traces_gen_framework`. |
| **`user_signals`** | Granular user behavior telemetry (positive/negative/neutral × stage) | `gen_id FK`, `user_id FK`, `signal_type`, `polarity`, `stage`, `signal_data JSONB` | Powers internal admin dashboard for safety-filter tuning. |
| **`user_style_profiles`** | pgvector Style Memory (one row per user × category) | `user_id FK`, `category UNIQUE`, `language`, `motion_archetype`, `environment_preset`, `preferred_framework ad_framework`, `embedding vector(1536)`, `export_count` | Index: `ivfflat (embedding vector_cosine_ops) WITH (lists=100)`. Active gating: `export_count >= 2`. |
| **`director_tips`** | Static pre-authored advice keyed by category × tip_type | `category`, `tip_text`, `tip_type` IN ('lighting','environment','motion','general'), `confidence_threshold`, `active` | Read-only at runtime; seeded via migration. |
| **`grievances`** | IT Rules 2026 grievance pipeline tickets | `id BIGSERIAL`, `user_id`, `gen_id`, `type`, `description`, `status` ('open' default), `created_at`, `resolved_at` | SLA Watchdog cron polls. |
| **`broll_clips`** | Static B-Roll library | `clip_id VARCHAR(20) PK`, `archetype`, `category green_zone_category`, `duration_ms 1000..5000`, `r2_url`, `excludes_faces/hands/locations BOOLEAN NOT NULL` (all must be TRUE per `chk_broll_safety`), `is_active`, `license_ref` | Index: `idx_broll_archetype_category` partial. |
| **`feature_flags`** | Toggles for Tier 1–4 degradation modes + beta gate | `key TEXT PK`, `value JSONB`, `description`, `updated_at` | Founder toggles via psql; agent never writes. |
| **`schema_migrations`** | Migration applied-history (created by `ci/run_migrations.py`) | `filename TEXT PK`, `applied_at` | Used to skip already-applied migrations. |

### 11.5 Postgres ENUMs

- `job_status` — 22 values. The single source of truth for FSM. Frozen by `fsm_freeze_guard.py`.
- `pre_topup_status` — same type as `job_status`, used as a separate column.
- `plan_tier` — `starter`, `essential`, `pro`.
- `payment_status` — `pending`, `captured`, `failed`, `refunded`. Topup-only FSM.
- `wallet_status` — `locked`, `consumed`, `refunded`. Lock-lifecycle FSM.
- `green_zone_category` — 5 values: `d2c_beauty`, `packaged_food`, `hard_accessories`, `electronics`, `home_kitchen`.
- `ad_framework` — 12 values (the dynamic playbook).

ENUMs can only grow (new values), per `[TDD-MIGRATION-SAFETY]-A`. Removing or renaming a value is forbidden.

### 11.6 Redis 6-DB Namespace

| DB | Purpose | Key patterns | TTL |
|---|---|---|---|
| **DB0** | Wallet cache + per-gen lock fields + Balance SSE | `wallet:{user_id}` (hash: balance, consumed_total), `walletlock:{user_id}:{gen_id}` (lock marker) | 5min cache, 300s lock |
| **DB1** | ARQ job queues | `arq:queue:phase1_to_3`, `arq:queue:phase4_workers` | per-job |
| **DB2** | COGS per-gen tracker | `cogs:{gen_id}` (hash: total, chat) | 24h |
| **DB3** | Provider health + Circuit Breaker FSM + feature flags cache | `health:{provider}`, `cb:{provider}`, `feature_flags:{key}` | 5min |
| **DB4** | Rate limiting | `rl:user:{user_id}:{endpoint}:{window}` | sliding window |
| **DB5** | Idempotency cache + actlock fence | `idem:{user_id}:{gen_id}:{action}`, `actlock:{gen_id}:{action}` | 300s / 10s |

**Bulkhead rationale:** a hot key in one DB cannot starve another. Wallet contention (DB0) is isolated from idempotency churn (DB5) and from ARQ queue depth (DB1).

### 11.7 The 4 Lua Scripts

| Script | Purpose | Invoked By |
|---|---|---|
| `wallet_lock.lua` | Atomic per-gen credit lock | `/approve-strategy`, `/retry-export` Step 7 |
| `wallet_consume.lua` | Convert lock → consumed | Worker-EXPORT after C2PA signing succeeds |
| `wallet_refund.lua` | Convert lock → refunded | DLQ handler `on_job_dead` (both branches) |
| `circuit_breaker.lua` | CB FSM: check / record_success / record_failure | ModelGateway routing |

All four scripts are idempotent on re-invocation:

- `wallet_lock` returns 1 if the lock already exists (network-retry safe).
- `wallet_consume` returns 0 if no active lock (already consumed).
- `wallet_refund` returns 0 if no active lock (already refunded).

**Wrapper invariant (`[TDD-CONCURRENCY]-D`):** the DLQ handler wraps `wallet_refund.lua` with a Postgres `INSERT INTO wallet_transactions (type='refund') ON CONFLICT DO NOTHING` to keep the immutable ledger synced with Redis state and prevent double-refund.

### 11.8 Cloudflare R2 Bucket Structure

```
advertwise-assets/
├── {user_id}/
│   ├── {gen_id}/
│   │   ├── source/original.{jpg|png}
│   │   ├── isolated/product.png
│   │   ├── tts/voiceover.{mp3|wav}
│   │   ├── i2v/candidate_0.mp4
│   │   ├── i2v/candidate_1.mp4
│   │   ├── compose/preview.mp4
│   │   └── export/
│   │       ├── square_1x1.mp4        (1080×1080, C2PA-signed)
│   │       └── vertical_9x16.mp4     (1080×1920, C2PA-signed)
│   └── style-memory/profile.json
```

**Worker-EXPORT overwrite policy:** retry export overwrites the same path. Previous `c2pa_manifest_hash` is overwritten in the same atomic UPDATE — no orphan hashes.

**Retention:**

- Source/isolated/preview: 7d Starter, 30d Paid (DPDP §8(7)).
- Exports: 5 years (IT Rules 2026 §5 + DPDP over-retention).
- Audit logs (Postgres, partitioned): 5 years.

**Sweep cadence:**

- Daily 02:00 IST: `retention_sweep` (DB-first, R2-second atomicity).
- Weekly Mon 02:30 IST: `r2_orphan_sweep` (catches R2 objects whose DB row is gone).
- Daily 02:15 IST: `partition_rotator` (next-month audit_log partition + REVOKE).

**Workers use credentialed boto3 access**, NOT presigned URLs. Presigned URLs (10-min TTL) are minted only at the L2 hydration time for client consumption. Workers running minutes after URL minting would expire — banned per `[TDD-OVERVIEW]`.

### 11.9 Worker Permission Matrix (Authority on Reads/Writes)

| Worker | May Read | May Write | DENIED |
|---|---|---|---|
| EXTRACT | source_url, source_image | product_brief, isolated_png_url, agent_motion_suggestion | wallet, scripts |
| COPY (router) | product_brief, campaign_brief | routed_frameworks, routing_rationale | wallet, raw_scripts |
| COPY (generate) | product_brief, campaign_brief, routed_frameworks | raw_scripts | wallet, refined_script |
| COPY (refine) | refined_script (or selected from safe_scripts), user_instruction, product_brief | refined_script | wallet, raw_scripts, safe_scripts |
| CRITIC | raw_scripts, product_brief | critic_scores, rationale | wallet, modify scripts |
| SAFETY | raw_scripts (or chat-refined script) | safety_flags, safe_scripts | wallet, publish |
| **STRATEGIST** | safe_scripts, style_memory, health_scores, cogs_estimate, director_tips, chat_turns_used, broll_clips | strategy_card, b_roll_plan | wallet, render, publish, **ALL external APIs**, **pre_topup_status** |
| TTS | selected_script (or refined_script) | tts_audio_url | wallet, I2V |
| I2V | isolated_png, motion_id, env_id | i2v_candidates[] | wallet, TTS |
| REFLECT | i2v_candidates[], source_png | selected_i2v_url | wallet, re-render |
| COMPOSE | tts, selected_i2v, benefit, b_roll_plan | preview_url | wallet |
| **EXPORT** | preview_url, declaration | exports JSONB, c2pa_manifest_hash, style_memory_update | wallet (refund only via DLQ), **pre_topup_status** |
| **phase4_coordinator** | gen_id only | status transitions {funds_locked → rendering → reflecting → composing → preview_ready} | wallet, **EXPORT enqueue (must NOT)** |

**The two zero-knowledge invariants:**

1. **Worker-STRATEGIST has zero external API access.** CI: `ci/strategist_sandbox_check.py` AST-parses imports; blocks httpx/requests/aiohttp/openai/anthropic/google.genai/boto3 in `app/workers/strategist.py`.
2. **No worker writes `pre_topup_status`.** Only L2 routes and the webhook handler. CI: `ci/check_pre_topup_writes.py` greps `app/workers/` for any UPDATE touching this column.

### 11.10 Migration Safety Policy

Per `[TDD-MIGRATION-SAFETY]`, the production DB is treated as append-only.

**Allowed:** `CREATE TABLE IF NOT EXISTS`, `ALTER TABLE ... ADD COLUMN ... NULL` or `DEFAULT`, `CREATE INDEX CONCURRENTLY IF NOT EXISTS`, `ALTER TYPE <enum> ADD VALUE`, `CREATE OR REPLACE FUNCTION/TRIGGER`, partition pre-creation, batched backfill scripts.

**Forbidden:** `DROP TABLE/COLUMN/TYPE/CONSTRAINT/INDEX` (without CONCURRENTLY), `ALTER COLUMN TYPE`, `ALTER COLUMN SET NOT NULL`, `TRUNCATE`, `RENAME`, removing ENUM values, destructive changes after Sprint Day 10 (May 5).

**CI enforcement:** `ci/migration_safety_guard.py` greps every `.sql` migration on every PR and blocks PRs containing forbidden patterns. Pairs verification: every `V*.sql` requires a matching `rollback_*.sql`.

**Migration runner:** `ci/run_migrations.py --dry-run` / `--apply` per `[TDD-IDE]-A` step 2a is the canonical migration tool. Alembic is not used (see GAP-09 in §16.7).

**Agent prohibition:** the Antigravity agent is physically forbidden from authoring destructive migrations. If the agent determines a DROP or RENAME is necessary, it must HALT and instruct the Founder to author a human-reviewed RFC.

### 11.11 External Services & Credentials

This subsection defines all external services, infrastructure dependencies, and required environment variables for AdvertWise MVP. All credentials must be stored in `.env.local` (development) and a secure secret manager (production). No secrets are committed to version control.

#### 11.11.1 Infrastructure

- `DATABASE_URL=` — Primary Postgres database (Neon). Source of truth for FSM, ledger, and system state.
- `REDIS_URL=redis://localhost:6379/0` — Redis instance for caching, ARQ queues, Lua locks, and idempotency (DB0–DB5 separation per §11.6).

#### 11.11.2 Cloud Storage (Cloudflare R2)

- `R2_ACCOUNT_ID=`
- `R2_ACCESS_KEY_ID=`
- `R2_SECRET_ACCESS_KEY=`
- `R2_BUCKET_NAME=advertwise-dev-assets`
- `R2_ENDPOINT_URL=`
- `R2_PUBLIC_URL=`

Purpose: store all media assets (preview, exports, B-roll). Used by workers via boto3 (NOT presigned URLs — see §11.8).

B-roll structure: `/broll/abstract/`, `/broll/motion/`, `/broll/texture/`, `/broll/warehouse/`, `/broll/packaging/`.

#### 11.11.3 Core AI & Model Providers

- `OPENAI_API_KEY=` — embeddings (text-embedding-3-small, 1536-dim) for Style Memory (pgvector).
- `DEEPSEEK_API_KEY=` — primary LLM for reasoning and script generation.
- `GROQ_API_KEY=` — primary routing layer for fast inference and Llama Guard moderation.
- `GEMINI_API_KEY=` — fallback LLM (Google AI Studio).
- `TOGETHER_API_KEY=` — model aggregation fallback.
- `SILICONFLOW_API_KEY=` — additional model fallback provider.

#### 11.11.4 Video Generation (I2V)

- `FAL_KEY=` — primary I2V provider.
- `MINIMAX_API_KEY=` — fallback I2V provider.

#### 11.11.5 Voice (TTS)

- `SARVAM_API_KEY=` — primary Indic TTS (Hindi, Marathi, Bengali, etc.).
- `ELEVENLABS_API_KEY=` — premium English voice (restricted usage).
- Google Cloud TTS uses Application Default Credentials (ADC) via `gcloud auth application-default login`. No JSON credential file or ENV path required.

#### 11.11.6 Utilities

- `FIRECRAWLER_API_TOKEN=` — product URL scraping (Phase 1).
- BiRefNet (Apache 2.0— runs locally inside Worker-EXTRACT; no API key required.
- `c2patool` — local Rust binary for C2PA signing; no API key required.

#### 11.11.7 Authentication (OAuth)

- `GOOGLE_OAUTH_CLIENT_ID=`
- `GOOGLE_OAUTH_CLIENT_SECRET=`

Used for Google 1-tap login.

#### 11.11.8 Payments (Razorpay)

- `RAZORPAY_KEY_ID=`
- `RAZORPAY_KEY_SECRET=`
- `RAZORPAY_WEBHOOK_SECRET=`

Used for UPI payments and webhook-based FSM restoration.

#### 11.11.9 Internal Configuration

- `JWT_SECRET=` — signing session tokens.
- `NEXT_PUBLIC_APP_URL=http://localhost:3000` — base URL for frontend (OAuth redirects, API calls).
- `ENV=development` — environment flag (development / staging / production).

#### 11.11.10 Monitoring & Observability

- `POSTHOG_API_KEY=` — product analytics.
- `POSTHOG_HOST=` — PostHog host endpoint.
- Grafana Cloud — Prometheus-compatible metrics; alerts handled via Grafana (no PagerDuty in MVP).
- Implemented skeleton setup: PostHog account + API key generated; Grafana Cloud account + Prometheus credentials generated; Grafana alerts wired; keys added to `.env.example` and stored in GCP Secret Manager.

#### 11.11.11 Security Rules

- Never commit `.env` files to Git.
- Use `.gitignore` for all secrets.
- Rotate keys before production launch.
- Restrict API usage via provider dashboards (rate limits, quotas).
- Use separate keys for dev and production.

### 11.12 Dependencies with other sections

§11 is the storage substrate that §7 (FSM), §8 (phases), §9 (orchestration), §12 (API), §13 (failure logic) all read and write to. §14 (Compliance) operates on `audit_log` + `compliance_log` + `grievances`. §15 (Testing) operates on `schema_migrations` and the migration-runner CLI.

---

## 12. Specify HTTP Routes and SSE Event Catalog

This section enumerates every HTTP endpoint, every SSE event, every idempotency contract, and the canonical 5-step API anatomy that all mutating endpoints must follow.

### 12.1 Purpose

To make the API surface complete and unambiguous. The agent never invents an endpoint or event type.

### 12.2 What this section defines

- The L2 endpoints (1 GET hydration, 8 POST mutating, 1 SSE, 1 webhook, 1 grievance, 1 download).
- The canonical API anatomy: actlock → ledger-first → state-guarded UPDATE → enqueue.
- The idempotency-key contract per endpoint.
- The SSE event taxonomy (state_change, chat_turn, provider_fallback, etc.).
- The 9-step atomic chain of `/retry-export`.

### 12.3 What this section does NOT define

- The full route handler implementations (lives in TDD `[TDD-API]-A..H`).
- The frontend client wrapper (lives in §10).
- The DLQ branching logic (lives in §13).
- The Razorpay HMAC verification details (lives in `[TDD-SECURITY]-C`).

### 12.4 Endpoint Catalog

| Method | Path | Auth | Idempotency Required | Purpose | Pre-Tx State | Post-Tx State |
|---|---|---|---|---|---|---|
| POST | `/api/generations` | JWT | ✅ | Create gen + enqueue Phase 1 | n/a (creates row) | `queued` |
| GET | `/api/generations/{gen_id}` | JWT | ❌ (read-only) | Hydrate state | any | (no change) |
| POST | `/api/generations/{gen_id}/advance` | JWT | ✅ | HD-2 → HD-3 (+ STRATEGIST at end of Phase 2) | `brief_ready` or `scripts_ready` | next phase |
| POST | `/api/generations/{gen_id}/selections` | JWT | ✅ | Set motion/env/lang chips | `brief_ready` | (mutates JSON, no state change) |
| POST | `/api/generations/{gen_id}/regenerate` | JWT | ✅ | Chip change → re-run Phase 2 | `scripts_ready` | `scripts_ready → regenerating → scripts_ready` |
| POST | `/api/generations/{gen_id}/chat` | JWT | ✅ | 5-stage Co-Pilot Chat refinement | `scripts_ready` | (no state change; mutates `refined_script`, increments `chat_turns_used`) |
| POST | `/api/generations/{gen_id}/edit-back` | JWT | ✅ | HD-4 [Edit] target → NULL downstream | `strategy_preview` | `brief_ready` or `scripts_ready` (or `regenerating`) |
| POST | `/api/generations/{gen_id}/approve-strategy` | JWT | ✅ | Lua lock + Phase 4 dispatch | `strategy_preview` | `funds_locked` (or `awaiting_funds` on lock-fail) |
| POST | `/api/generations/{gen_id}/declaration` | JWT | ✅ | Capture provenance + enqueue worker_export | `preview_ready` | `export_queued` |
| POST | `/api/generations/{gen_id}/retry-export` | JWT | ✅ (monotonic) | 9-step atomic retry chain | `failed_export` | `export_queued` (or `awaiting_funds` on lock-fail; no change on 428) |
| POST | `/api/wallet/topup` | JWT | ❌ (Razorpay payment_id is natural key) | Razorpay order creation | n/a | (creates pending payment) |
| POST | `/api/webhook/razorpay` | HMAC (no JWT) | ❌ (idempotent by design via UNIQUE INDEX) | Origin-preserving multi-row restoration | any (user gens in `awaiting_funds`) | restored from `pre_topup_status` |
| POST | `/api/grievance` | JWT | ❌ | Create takedown ticket; enqueue grievance_processor | any | (creates grievance row) |
| GET | `/api/sse/{gen_id}` | JWT (cookie) | ❌ | Server-Sent Events subscription | any | (no change) |
| GET | `/api/generations/{gen_id}/download/{format}` | JWT | ❌ (idempotent) | Returns presigned R2 URL | `export_ready` | (no change) |

### 12.5 The Canonical 5-Step API Anatomy (Per `[TDD-CONCURRENCY]`)

Every mutating endpoint composes these five canonical patterns in this strict order:

1. **Step 1 — Action Lock (outside).** `actlock:{gen_id}:{action}` Redis SET NX EX 10. Cross-tab race → 409 ECM-012.
2. **Step 2 — Ledger-First Write.** Inside `db.transaction()`, INSERT `wallet_transactions` (or other immutable ledger row) BEFORE the Redis Lua call. **IF** Lua subsequently fails → **THEN** DELETE the optimistic row inside the same transaction.
3. **Step 3 — Redis Lua Validation.** `wallet_lock.lua` (or other atomic op). **IF** result `0` → **THEN** rollback ledger, transition state to recoverable failure (e.g., `awaiting_funds`), return 4xx; **ELSE** continue.
4. **Step 4 — State-Guarded UPDATE (inside).** `UPDATE generations SET status = $new WHERE gen_id = $1 AND status = $expected RETURNING gen_id`. **IF** rowcount=0 → **THEN** 409 ECM-012.
5. **Step 5 — Enqueue Background Job (after COMMIT).** `arq.enqueue_job(...)` strictly AFTER `db.commit()`. Prevents the race where the job runs before the row is visible.

**Final step — release actlock** in `finally` block. Always release, even on exception.

### 12.6 Idempotency Contract

Per `[PRD-IDEMPOTENCY]` and `[TDD-CONCURRENCY]-A`:

- Every mutating endpoint requires a `Idempotency-Key` HTTP header (UUIDv4).
- `@idempotent(ttl=300, action_key, cache_only_2xx=True)` decorator outside the actlock fence.
- localStorage key schema: `aw_idem_{user_id}_{gen_id}_{action}`.
- Cross-tab via `storage` event listener.
- `cache_only_2xx=True`: ONLY 2xx responses cached. Recoverable 4xx (400, 402, 409, 428) and 5xx NEVER cached. Client drops localStorage key on receipt of any 4xx.
- `/retry-export` uses monotonic key suffix `:{export_retry_count}` to prevent collision across retries.

### 12.7 The 9-Step Atomic Chain of `/retry-export`

Per `[PRD-HD6]` and `[TDD-API]-G`:

| # | Step | Failure Behavior |
|---|---|---|
| 1 | Validate ownership, state='failed_export', `export_retry_count < 3` | 404 / 409 ECM-012 / 410 ECM-019 |
| 2 | (handled by Step 1's count check) | — |
| 3 | Validate plan_tier ≠ 'starter' (defensive) | 403 ECM-006 |
| 4 | **Declaration freshness:** SELECT MAX(`audit_log.created_at`) for `action IN ('declaration_accepted','declaration_resigned')`. Compute `is_stale = (NOW() - latest) > 24h`. **IF** STALE AND `declarations` missing → **THEN** **428 ECM-020** (no state change, no ledger). **IF** STALE AND `declarations==[True,True,True]` → **THEN** INSERT new `audit_log` row atomically (preamble) → continue. **ELSE** continue. | 428 ECM-020 (state stays) |
| 5 | R2 HEAD on `preview_url` | 410 ECM-018 (terminal) |
| 6 | (handled by Step 3's tier check) | — |
| 7 | INSIDE `db.transaction()`: INSERT `wallet_transactions(type='lock', status='locked')` + `redis_lua.wallet_lock`. **IF** lua=0 → **THEN** DELETE the row + ATOMIC UPDATE `status='awaiting_funds', pre_topup_status='failed_export'` + ROLLBACK; **ELSE** continue. | 402 ECM-007 (HD-6 Top-Up Drawer overlay) |
| 8 | Conditional UPDATE: `status='export_queued', export_retry_count=export_retry_count+1 WHERE status='failed_export'` (cross-tab race guard) | 409 ECM-012 |
| 9 | After COMMIT: `arq.enqueue_job("worker_export", ...)` on `phase4_workers` | — |

**Step ordering invariant (legal-first, money-second):**

```
audit_log INSERT (Step 4)  →  wallet lock (Step 7)  →  state UPDATE (Step 8)  →  enqueue (Step 9)
   ↑ legal ack first
                              ↑ money moves second
                                                       ↑ state flips third
                                                                                   ↑ compute dispatched last
```

**IF** audit_log INSERT succeeds but Lua lock subsequently fails (Step 7 → `awaiting_funds`) → **THEN** the newly-inserted row is **kept** — legally valid regardless of money movement. On topup resumption, **IF** declaration is still fresh (<24h) → **THEN** the next retry skips Step 4 re-sign; **ELSE** re-sign required.

### 12.8 SSE Event Taxonomy

Per `[PRD-UI-MOCKS]` MOCK-19:

| event type | Emitted On | Payload Shape |
|---|---|---|
| `state_change` | Every status transition | `{type, gen_id, state, pre_topup_status, ...optional fields like preview_url, exports}` |
| `chat_turn` | Successful chat COMMIT (Stage 6) | `{type, gen_id, turns_used, turns_remaining}` |
| `provider_fallback` | ModelGateway swaps a provider | `{type, gen_id, from, to, capability}` (toast-only; no state change) |
| `lock_failed` | Atomic transition into `awaiting_funds` | (an alias of state_change with the new state field) |
| `render_failed` | DLQ Branch A | `{type, gen_id, state: 'failed_render', error_code: 'ECM-004'}` |
| `export_failed` | DLQ Branch B | `{type, gen_id, state: 'failed_export', error_code: 'ECM-005'}` |
| `topup_captured` | Razorpay webhook restoration | state_change with `source: 'topup_captured'` |
| `regenerating_start`, `regenerating_complete` | Chip-change re-run boundaries | `{type, gen_id}` |
| `phase_complete` | At each phase boundary (1→2, 2→3, 3→4) | `{type, gen_id, target_screen}` |
| `worker_complete:{tts\|i2v\|reflect\|compose\|export}` | Per-worker completion within Phase 4 | `{type, gen_id}` |

**Reconnect contract:** SSE EventSource exponential backoff 1s → 2s → 4s → max 30s. On reconnect, the client re-issues `GET /api/generations/{gen_id}` to close any missed-event gap.

### 12.9 Webhook Contract

`POST /api/webhook/razorpay` is the most security-sensitive endpoint:

1. **HMAC verification** via `X-Razorpay-Signature` header. Constant-time `hmac.compare_digest` comparison (no timing attacks). **IF** verification fails → **THEN** 401, no mutation.
2. **Event mapping (IF / THEN):**
   - **IF** `payment.captured` → **THEN** target_status='captured'.
   - **ELSE IF** `payment.failed` → **THEN** target_status='failed'.
   - **ELSE** → ignored, return 200 OK.
3. **Amount mapping (IF / THEN):**
   - **IF** `amount_paise == 39900` → **THEN** 4 credits, plan='essential', 30-day validity.
   - **ELSE IF** `amount_paise == 149900` → **THEN** 25 credits, plan='pro', 45-day validity.
   - **ELSE** → 400.
4. **Idempotent insert:** INSERT `wallet_transactions(type='topup', payment_status, razorpay_payment_id)`. UNIQUE INDEX `ux_wallet_topup_dedup` on `razorpay_payment_id` WHERE `type='topup' AND payment_status='captured'` rejects duplicates → return `{ok:true, dedup:true}`.
5. **Origin-preserving multi-row restore (per S9):**
   ```sql
   UPDATE generations
   SET status = pre_topup_status, pre_topup_status = NULL
   WHERE user_id = $1 AND status = 'awaiting_funds'
   RETURNING gen_id, status;
   ```
6. **SSE broadcast** to all restored `gen_id`s, push `state_change` with `source='topup_captured'`. Each user's open tabs receive their gen's specific restoration.

**The reorder safety FSM:** `pending → captured` ✅, `pending → failed` ✅, `captured → failed` ❌ (ignored, terminal), `failed → captured` ❌ (ignored, terminal). Re-ordered webhook events are gracefully no-op.

### 12.10 Dependencies with other sections

§12 invokes §11 (DB writes) and §9 (gateway calls) and §7 (state transitions) on every mutating endpoint. §13 governs the failure paths of every endpoint. §15 has the contract-test fixtures for every endpoint via the API stub harness.

---

## 13. Branch DLQ Recovery and Atomic Refunds

This section enumerates every failure mode, the recovery flow it routes to, the refund semantics, and the dual-branch DLQ that distinguishes Phase-4 render failures from Worker-EXPORT failures.

### 13.1 Purpose

The economic linchpin: render failures and export failures must never be conflated, because re-running render is ~₹10 wasted compute when the export retry path is ~₹0.35.

### 13.2 What this section defines

- The 20 ECM error codes and their recovery targets (from `[PRD-ERROR-MATRIX]`).
- The dual-branch DLQ handler (`on_job_dead`) and its function-name dispatch.
- The double-refund defense (Lua + Postgres + application layers).
- The retry-export atomic re-sign for stale declarations (428 ECM-020 → atomic Step 4).
- The terminal failure variants (ECM-018 R2 expired, ECM-019 retry exhausted).
- The Tier 1–4 graceful degradation feature flags.

### 13.3 What this section does NOT define

- The error copy strings (frozen in `[PRD-ERROR-COPY]`).
- The component each ECM renders to (lives in §10).
- The retention sweep that enforces ECM-018 (lives in §11).

### 13.4 The 20 ECM Error Codes (Per `[PRD-ERROR-COPY]`)

| ID | Code | HTTP | Origin | Recovery Target | Mechanism | Compute Impact |
|---|---|---|---|---|---|---|
| ECM-001 | `failed_category` | SSE | HD-1 (Worker-EXTRACT) | HD-1 (fresh `gen_id`) | `[Start Over]` | None |
| ECM-002 | `failed_compliance` | SSE | HD-1 (InputScrubber) | HD-1 (fresh `gen_id`) | `[Start Over]` | None |
| ECM-003 | `failed_safety` | SSE | HD-3 (Worker-SAFETY) | HD-3 (auto-retry SAFE_TRIO 1×; else `[Back to Scripts]`) | System retry → user edits chips | Phase 2 re-run ~₹0.30 |
| ECM-004 | `failed_render` | SSE | HD-5 (DLQ Branch A) | HD-4 re-lock | `[↻ Try Again]` → fresh `/approve-strategy` | Full Phase 4 re-run (legitimate — assets incomplete) |
| ECM-005 | `failed_export` | SSE | HD-6 (DLQ Branch B) | HD-6 inline | `[↻ Retry Export · 1 Credit]` → `/retry-export` | Worker-EXPORT only (~₹0.35); preserves ~₹10 of Phase-4 |
| ECM-006 | `STARTER_RENDER_BLOCKED` | 403 | HD-4 (or `/retry-export` defensive) | HD-4 modal | Plan Modal | None |
| ECM-007 | `INSUFFICIENT_FUNDS` | 402 | HD-4 OR HD-6 (Lua lock-fail) | Top-Up Drawer overlay on origin screen | `pre_topup_status` snapshot + webhook restore | None |
| ECM-008 | `CHAT_LIMIT_REACHED` | 429 | HD-3 chat (turn 4+) | HD-3 inline | Chat disabled; Continue active | None |
| ECM-009 | `CHAT_CEILING_HIT` | 429 | HD-3 chat (CostGuard) | HD-3 inline | Chat disabled (budget); Continue active | None |
| ECM-010 | `CHAT_SAFETY_REJECT` | 422 | HD-3 chat (OutputGuard) | HD-3 inline | Input re-enabled; counter preserved; **COGS preserved per F8** | None additional |
| ECM-011 | `CHAT_COMPLIANCE_REJECT` | 400 | HD-3 chat (ComplianceGate) | HD-3 inline | Input cleared, re-enabled | None (no LLM call) |
| ECM-012 | `CROSS_TAB_CONFLICT` | 409 | Any mutating call (actlock or rowcount=0) | Current screen | `[Refresh]` toast | None |
| ECM-013 | `HYDRATION_FAILED` | — | Any mount | Current | `[Refresh Page]` boundary | None |
| ECM-014 | `UPLOAD_TOO_LARGE` | 413 | HD-1 | HD-1 inline | error clears on next file selection | None |
| ECM-015 | `FIRECRAWL_TIMEOUT` | SSE | HD-1 (Worker-EXTRACT) | HD-1 (auto-tab-switch to Upload) | `[Upload Image]` · `[Try URL Again]` | None |
| ECM-016 | `C2PA_SIGN_FAILED` | DLQ | HD-6 (Worker-EXPORT c2patool returncode≠0) | Same as ECM-005 | `[↻ Retry Export]` | Same as ECM-005 |
| ECM-017 | `DECLARATION_INVALID` | 400 | HD-6 (`/declaration` <3 boxes) | HD-6 (checkbox flash) | UI flashes 800ms | None |
| ECM-018 | `EXPORT_ASSETS_EXPIRED` | 410 | HD-6 (`/retry-export` Step 5 R2 HEAD 404) | HD-6 (terminal) | Only CTA: `[Start New Generation]` | Credit refunded; new `gen_id` required |
| ECM-019 | `EXPORT_RETRY_EXHAUSTED` | 410 | HD-6 (`/retry-export` Step 3, count==3) | HD-6 (terminal) | `[Contact Support]` · `[Start New Generation]` | All credits refunded; no further retries |
| ECM-020 | `DECLARATION_REFRESH_REQUIRED` | **428** | HD-6 (`/retry-export` Step 4 stale, no `declarations` body) | HD-6 (stays `failed_export`, State 4b) | 3 inline checkboxes; next call `declarations:[true,true,true]` | None on 428; retry cost on subsequent atomic retry |

**Dead-end audit:** 20 / 20 ECM codes have a defined recovery + mechanism. Zero dead ends.

### 13.5 Dual-Branch DLQ Handler

`on_job_dead(job, ctx)` is the centralized handler for any ARQ job that exceeds `max_tries`. The dispatch is strictly by `job.function_name`:

- **IF** `job.function_name == 'phase4_coordinator'` → **THEN** Branch A: refund via `wallet_refund.lua` + ledger row, transition `failed_render`, emit `render_failed` SSE, surface HD-5 inline → `[↻ Try Again]` re-locks at HD-4.
- **ELSE IF** `job.function_name == 'worker_export'` → **THEN** Branch B: refund via `wallet_refund.lua` + ledger row, transition `failed_export`, emit `export_failed` SSE, surface HD-6 inline (4a or 4b) → `[↻ Retry Export]` → 9-step chain.
- **ELSE** (unmapped function name) → **THEN** no action; warning log; manual investigation; capture `dlq_original_task` for forensics.

| `function_name` | Branch | Target State | Refund? | SSE event | Recovery surface |
|---|---|---|---|---|---|
| `phase4_coordinator` | A | `failed_render` | ✅ | `render_failed` | HD-5 inline → `[↻ Try Again]` re-locks at HD-4 |
| `worker_export` | B | `failed_export` | ✅ | `export_failed` | HD-6 inline (4a or 4b) → `[↻ Retry Export]` → 9-step chain |
| any other (unmapped) | — | (no action) | ❌ | (warning log) | (manual investigation) |

**The dispatch invariant (per `[TDD-DLQ]-B`):** `function_name` is the ONLY dispatch key. The DLQ MUST NOT branch on `gen.status`, because the worker may have died mid-transition leaving FSM state ambiguous. Forensic information is captured in `dlq_original_task` for post-mortem.

**No cascading enqueues:** the DLQ halts the pipeline. Recovery is strictly user-initiated. The agent must not author DLQ logic that auto-retries either branch.

### 13.6 Refund Semantics — The Triple Defense

To guarantee a user cannot receive two refunds for the same generation:

1. **Lua-level:** `wallet_refund.lua` checks `GET walletlock:{user_id}:{gen_id}`. **IF** absent → **THEN** return 0 (already refunded); **ELSE** apply.
2. **Postgres schema:** `ux_wallet_refund_dedup` UNIQUE INDEX on `(gen_id, type)` WHERE `type='refund'`. Physically prevents two refund rows per gen.
3. **Application:** DLQ wrapper uses `INSERT ... ON CONFLICT DO NOTHING` for the ledger refund, gracefully ignoring duplicate DLQ events (zombie workers, network retries).

**Metric:** `aw_refund_dedup_hits_total` counts how often the dedup check fires. Sustained increase indicates a zombie-worker problem.

### 13.7 The Retry-Export Atomic Re-Sign (ECM-020 Path)

The most architecturally novel failure-recovery flow in the system. **IF** a user's declaration is >24h stale AND they attempt retry without acknowledging the 3 declarations → **THEN** the server returns 428 ECM-020 — explicitly NO state change, NO ledger action.

**Why no state change?** Because moving to `preview_ready` and back would create a state-thrash visible in `status_history` and obscure the user's retry intent. Keeping the user on `failed_export` while the client renders the inline 3-checkbox bank above the retry button preserves both UX clarity and audit-trail accuracy.

**Why no ledger action?** Because no compute will be spent until the user acknowledges. The only ledger event that should fire is the new `audit_log` row recording the re-sign — and that fires only on the next `/retry-export` call carrying `declarations:[true,true,true]`.

**The atomic chain on the second attempt:**

1. Step 4 INSERTs the new `audit_log` row (legally valid) BEFORE
2. Step 7 acquires the wallet lock BEFORE
3. Step 8 transitions state BEFORE
4. Step 9 enqueues compute.

**IF** Step 7 fails after Step 4 succeeds → **THEN** the audit row is preserved; the user enters `awaiting_funds(pre='failed_export')`. On webhook restore, the user lands back on `failed_export`. **IF** declaration is still fresh (<24h since the row inserted in Step 4) → **THEN** the next retry skips re-sign; **ELSE** re-sign required.

### 13.8 Terminal Failure Variants (HD-6)

- **ECM-019 `EXPORT_RETRY_EXHAUSTED`:** triggered when `export_retry_count == 3`. The retry button is disabled; CTAs collapse to `[Contact Support]` and `[Start New Generation]`. All 3 credits used in the failed attempts have been refunded — net debit is zero.
- **ECM-018 `EXPORT_ASSETS_EXPIRED`:** triggered when `/retry-export` Step 5 R2 HEAD on `preview_url` returns 404. This means the daily retention sweep purged the preview asset (>30d for Paid users). The credit lock had not been acquired yet (Step 5 precedes Step 7), so no refund is necessary on this specific call — but earlier failed attempts have already issued refunds. Only CTA: `[Start New Generation]` (fresh `gen_id`).

### 13.9 Tier 1–4 Graceful Degradation Feature Flags

Per `[TDD-MIGRATIONS]` (20), four feature flags exist for emergency degradation. Founder toggles via psql; agent never writes.

| Flag | Effect When ON |
|---|---|
| `tier1_degradation_enabled` | pgvector heuristic fallback (Style Memory uses last-row-by-category instead of vector search) |
| `tier2_degradation_enabled` | B-Roll intercut disabled (Worker-COMPOSE generates 9s I2V-only without 3s hook/CTA bookends — out of canonical 15s but better than failing) |
| `tier3_degradation_enabled` | Style Memory disabled (no upserts, no retrievals — system-wide) |
| `tier4_degradation_enabled` | Reflect step disabled (use I2V attempt 1 directly without SSIM/deformation gates) |

Default: all OFF. Toggling is a P1/P2 incident response, not a routine action.

### 13.10 Dependencies with other sections

§13 implements the failure paths referenced by §6 (per-screen failures), §8 (per-phase failures), §12 (per-endpoint failure responses). §11's `wallet_transactions` and `audit_log` are the storage substrate for refunds and re-signs. §14's compliance writes are the legal counterparts to the Step-4 re-sign INSERT.

---

## 14. Enforce IT Rules 2026 Compliance Pipeline

This section defines the closed-loop compliance system that makes IT Rules 2026 + DPDP Act 2023 a **product moat**, not an afterthought.

### 14.1 Purpose

To make compliance an active, testable, observable subsystem — SGI watermark burn-in + C2PA cryptographic signing + immutable partitioned audit trail + 24-hour ACK / <60-min auto-takedown + declaration provenance with atomic re-sign.

### 14.2 What this section defines

- The four canonical `compliance_log.check_type` strings and their emission sites.
- The SGI watermark burn-in policy (FFmpeg drawtext at all resolutions).
- The C2PA signing flow with returncode-checked `c2patool`.
- The audit_log immutability policy (DB-role REVOKE + monthly partitioning + 5-year DETACH archival).
- The auto-takedown pipeline + SLA Watchdog (Grafana-alert escalation).
- The data-minimization retention sweep cadence and atomicity.
- The declaration provenance contract (IP + UA + timestamp + SHA-256) and its 24-hour freshness window.

### 14.3 What this section does NOT define

- The schema columns of `audit_log` (lives in §11).
- The grievance form UI (lives in §10).
- The retry-export 9-step chain (lives in §13).

### 14.4 The Four Canonical Compliance Check Types

`compliance_log.check_type` is a strict enum-by-convention, enforced by `ci/validate_compliance_taxonomy.py`. Only these 4 strings are valid:

| `check_type` | Emitting Source | Trigger |
|---|---|---|
| `c2pa_sign` | `app/workers/export.py` | C2PA manifest written; `c2patool` returncode == 0 |
| `sgi_burn_in` | `app/workers/compose.py` + `app/workers/export.py` | FFmpeg drawtext SGI watermark applied |
| `declaration_capture` | `app/api/routes/declaration.py` | First-time HD-6 declaration accepted (audit_log INSERT) |
| `freshness_check` | `app/api/routes/retry_export.py` Step 4 | 24h freshness validated OR atomic re-sign performed |

### 14.5 SGI Watermark Burn-In

Per `[TDD-VIDEO]-B` and Worker-COMPOSE / Worker-EXPORT:

- FFmpeg `drawtext=text='AI Generated Content':fontsize=14:fontcolor=white@0.7:x=10:y=h-30`.
- Applied AFTER LUT colour grading in the filter graph.
- Visible at both export resolutions (1080×1080 and 1080×1920).
- Burned into the pixel data — cannot be removed without re-encoding (and re-encoding without C2PA invalidates the manifest).

**Verification:** Founder's manual checkpoint G4 includes visual inspection of the watermark on both formats.

### 14.6 C2PA Cryptographic Signing

Per `[TDD-WORKERS]-I` Worker-EXPORT:

- Each of the 2 export formats is signed with `c2patool video_path --output signed_path --manifest <json>`.
- `c2patool` is a local Rust binary (not an external API).
- Returncode is **explicitly checked**. **IF** non-zero → **THEN** raise `C2PASignError` → DLQ Branch B → `failed_export` + refund.
- `c2patool` is timeout-bounded at 30s per signing (asyncio.wait_for); **IF** timeout → **THEN** kill → `C2PASignError`.
- The manifest hash (`sha256(manifest)`) is stored in `generations.exports.c2pa_manifest_hash` and on retry, the new hash overwrites the previous one in the same atomic UPDATE — no orphans.

All C2PA verification is executed locally via `c2patool --verify`. No external verification services (e.g., Adobe VerifyContentCredentials) are part of the execution flow — forbidden in CI and runtime per `[PRD-FEATURES-COMPLIANCE]`.

**CI runner setup:** GitHub Actions Linux runners must install `c2patool` from the official release. Required FFmpeg filter set: `lut3d`, `tpad`, `apad`, `drawtext`.

### 14.8 Declaration Provenance

Captured per `[TDD-API]-F` (first-time) and `[TDD-API]-G` Step 4 (re-sign):

| Field | Source |
|---|---|
| `ip_address` | `request.client.host` |
| `user_agent` | `request.headers["user-agent"]` |
| `created_at` | server `NOW()` |
| `declaration_sha256` | `sha256("{gen_id}\|{user_id}\|{ip}\|{ua}\|{iso_timestamp}[\|resigned]")` |
| `payload JSONB` | `{commercial_use, image_rights, ai_disclosure}` (each true) for `declaration_accepted`; `{inline_resign: true}` for `declaration_resigned` |

The 24-hour freshness window (`DECLARATION_FRESHNESS_SECONDS = 24*3600`) is the boundary at which the user must re-sign for any new export.

### 14.9 The Three Mandatory Declaration Checkboxes

Per `[PRD-HD6]`:

| # | Checkbox Text | Legal Basis |
|---|---|---|
| 1 | "I confirm this is for commercial advertising purposes." | Commercial use affirmation — distinguishes from personal/satirical use |
| 2 | "I have rights to use this product image." | Rights attestation — shifts liability to user for copyright/trademark claims |
| 3 | "I understand this is AI-generated per IT Rules 2026." | SGI disclosure acknowledgment — statutory requirement per §5 of IT Rules 2026 |

**Independence invariant (L7):** these are **three independent legal assertions**; bundling them creates collateral-attack risk. UI renders 3 separate checkboxes; server validates all-three-true.

### 14.10 Auto-Takedown Pipeline (Per `[TDD-TAKEDOWN]-A/B/C/D`)

The IT Rules 2026 grievance pipeline has a strict SLA:

| Milestone | Target | Enforcement |
|---|---|---|
| Grievance ACK to user | <24 hours | `grievance_processor` ARQ job + email on INSERT |
| Content deletion from R2 | <60 minutes from trigger | `grievance_processor` calls R2 DELETE + DB soft-delete |
| PagerDuty P0 escalation | T+90 minutes if unresolved | `takedown_sla_watchdog` cron (every 5 min) |
| Audit record | Immutable `audit_log` row `action='takedown_executed'` | Inserted atomically with deletion |
| Founder review | <15 calendar days (per Rules) | Manual; SLA Watchdog pages at T+13d |

**The `grievance_processor` ARQ job (enqueued on INSERT into `grievances`):**
1. Validates grievance type (copyright/defamation/privacy/other).
2. Sends ACK email to user (no SLA miss if email provider fails — logged, not blocking).
3. For content-deletion type: soft-DELETE R2 objects referenced by `gen_id` + UPDATE `generations.takedown_at = NOW()`.
4. INSERTs `audit_log` row.
5. UPDATEs `grievances.status='resolved'`.

**`takedown_sla_watchdog` cron (every 5 min):**
- Queries `grievances WHERE status='open' AND created_at < NOW() - INTERVAL '22 hours'` → sends PagerDuty alert.
- Queries `grievances WHERE status='open' AND created_at < NOW() - INTERVAL '13 days'` → escalates to Founder.

### 14.11 Data Minimization (DPDP §8(7)) — Retention Sweep

Three cron jobs enforce minimization:

| Cron | Schedule | Objects Swept |
|---|---|---|
| `retention_sweep` | Daily 02:00 IST | Starter: source/isolated/preview > 7d. Paid: source/isolated/preview > 30d. All: exports > 5y. DB-first: UPDATE generations.purged_at = NOW(); R2-second: DELETE objects. |
| `r2_orphan_sweep` | Weekly Mon 02:30 IST | R2 objects with no matching active DB row (upload aborts, crash-interrupted extracts). |
| `partition_rotator` | Daily 02:15 IST | Pre-creates next-month audit_log partition with REVOKE policy. DETACH partitions older than 5 years (does NOT DROP). |

**Atomicity:** DB-first, R2-second. If R2 DELETE fails after DB UPDATE, the object is orphaned — caught on next `r2_orphan_sweep`. Never the reverse: a DB purge without R2 delete would be a DPDP violation.

### 14.12 Dependencies with other sections

§14 is the compliance implementation of §5's L1..L7 invariants. §11 provides the `audit_log`, `compliance_log`, and `grievances` tables. §12's `/declaration` and `/retry-export` endpoints insert into `audit_log` per §14.8. §13's DLQ handler triggers refund before takedown in parallel.

---

## 15. Testing Strategy and CI Gates

### 15.1 Purpose

To enumerate the testing layers, the CI job inventory, the manual verification checkpoints, and the release-gate acceptance criteria that together constitute the truth function for the build. Per `[PRD-AC-GLOBAL]` G1..G5 and the §1.4 reading rule "CI is the truth," no file authored by the Agentic IDE is considered done unless the relevant CI job is green. This section is the index of those jobs and their pass criteria; it is not the test code itself.

### 15.2 What this section defines

- The five-layer test pyramid (unit / integration / contract / E2E / manual) and which TDD anchor owns each layer.
- The exact list of CI jobs at `[TDD-CICD]-A..E` with their input, output, and red/green criteria.
- The mapping between PRD acceptance criteria (`[PRD-AC-1..6]`, `[PRD-AC-GLOBAL]` G1..G5) and the CI jobs that prove them.
- The Founder's manual verification checkpoints corresponding to the five approval gates established in §3.
- The Beta gate criteria (B1..B5, E1..E6) per `[PRD-RELEASE-BETA]` and MVP gate criteria (M1..M10) per `[PRD-RELEASE-MVP]`.
- The rollback-drill specification per `[TDD-ROLLBACK]-F`.
- The observability and SLA monitoring surface per `[PRD-FEATURES-INFRA]` F-606/F-607.

### 15.3 What this section does NOT define

- The actual test code, fixtures, or stub bodies — those live in TDD `[TDD-API-STUBS]-*` and the corresponding `tests/` files.
- The five Founder approval gates as halt points in the build sequence — those are defined in §3 and sequenced in §16.5.
- The compliance-taxonomy ENUM members — those are frozen in §14.4.
- The DLQ branch behaviour — that is sequenced in §13.
- Any human QA process beyond what `[PRD-AC-GLOBAL]` and the five gates explicitly require.

### 15.4 The Five-Layer Test Pyramid

|Layer|Scope|Owner|Runs Where|TDD Anchor|
|---|---|---|---|---|
|L1 — Unit|Pure functions, single-class behaviour, prompt template render, FSM transition validity|Per-module `tests/unit/`|Every PR, every push|`[TDD-API-STUBS]-*`|
|L2 — Integration|DB + Redis + ARQ worker round-trip, single phase end-to-end|`tests/integration/`|Every PR; nightly full-suite|`[TDD-WORKERS]-*`|
|L3 — Contract|API request/response schema, idempotency cache shape, webhook signature validity|`tests/contract/`|Every PR|`[TDD-API]-A..H`|
|L4 — E2E|Full HD-1..HD-6 traversal with real Worker chain on staging R2|`tests/e2e/` (Playwright + ARQ)|Pre-merge to `main`; nightly|`[TDD-CICD]-E`|
|L5 — Manual|Founder verification at each of the five gates from §3|Founder|Pre-gate, locally|§15.7 below|

The pyramid is **strict**: a failure in L1 blocks L2, an L2 failure blocks L3, etc. The Agentic IDE may not author code past a layer with a red signal.

### 15.5 The CI Job Inventory `[TDD-CICD]-A..E`

|ID|Script Path|Validates|Red/Green Criteria|
|---|---|---|---|
|A|`ci/validate_state_machine.py`|The 22-state FSM and its legal transitions per `[PRD-FSM]` / `[TDD-FSM]`|Walks all transitions in `state_transitions.yaml`; fails on any orphan state, illegal transition, or unreachable terminal.|
|B|`ci/validate_compliance_taxonomy.py`|The 4 canonical `compliance_log.check_type` strings per §14.4|greps the codebase for `check_type=`; fails on any string not in `{c2pa_sign, sgi_burn_in, declaration_capture, freshness_check}`.|
|C|`ci/validate_idempotency_ttl.py`|24h TTL applied **only** to 2xx responses, per `[PRD-IDEMPOTENCY]` and `[TDD-CONCURRENCY]-A`|Static-analyses `app/middleware/idempotency.py`; fails if a non-2xx code path enters the SETEX call.|
|D|`ci/validate_credit_lock_order.py`|Lock-before-compute invariant per `[TDD-CONCURRENCY]-B/C`|AST scan: every Worker that calls a generation primitive must show a `redis.lock` acquire BEFORE the compute call site.|
|E|`ci/validate_dlq_branches.py`|The three DLQ branches (A/B/C) per `[TDD-DLQ]-A/B` and §13|Asserts every DLQ-emitting raise site maps to exactly one of the three branches; fails on unmapped exception classes.|

**Build seam:** these five jobs run as required GitHub Actions checks on every PR. `main` has branch protection requiring all five green plus L1+L2+L3 layers green.

Observability Setup:
- Skeleton credentials provisioned for PostHog and Grafana Cloud
- No live telemetry required at this stage
- PagerDuty excluded; alerts handled via Grafana

### 15.6 Acceptance Criteria Mapping

`[PRD-AC-1..6]` are the per-screen acceptance criteria (one per HD screen, plus AC-1 for upload). Each maps to an L4 E2E scenario:

|PRD AC|Screen|L4 Scenario|Verified By|
|---|---|---|---|
|AC-1|HD-1|Upload → extract → confidence emit|`tests/e2e/test_hd1_upload.py`|
|AC-2|HD-2|Director Review → confirm intent|`tests/e2e/test_hd2_director.py`|
|AC-3|HD-3|Co-Pilot bounded chat → script lock|`tests/e2e/test_hd3_copilot.py`|
|AC-4|HD-4|Strategist asset selection → credit lock → Phase 4 enqueue|`tests/e2e/test_hd4_strategist.py`|
|AC-5|HD-5|Phase 4 progress → render complete|`tests/e2e/test_hd5_render.py`|
|AC-6|HD-6|Declaration → C2PA sign → export download|`tests/e2e/test_hd6_export.py`|

`[PRD-AC-GLOBAL]` G1..G5 are cross-cutting and verified by dedicated suites:

| AC-GLOBAL | Concern                                                                             | Suite                                                     |
| --------- | ----------------------------------------------------------------------------------- | --------------------------------------------------------- |
| G1        | State machine integrity                                                             | CI-A + `tests/integration/test_fsm_walk.py`               |
| G2        | Idempotency correctness                                                             | CI-C + `tests/contract/test_idempotency.py`               |
| G3        | Credit invariants (no double-charge, no compute-without-lock, refund correctness)   | CI-D + `tests/integration/test_credit_invariants.py`      |
| G4        | Compliance immutability (audit_log append-only, C2PA validity, SGI burn-in present) | CI-B + `tests/integration/test_compliance.py` + Manual G4 |
| G5        | Failure recovery (DLQ branches, refund, retry-export)                               | CI-E + `tests/integration/test_dlq_branches.py`           |

### 15.7 Founder's Manual Verification Checkpoints (at the §3 Gates)

The five approval gates from §3 are halt points in the build sequence (sequenced in §16.5). At each gate the Founder runs the verification checklist below; the Agentic IDE may not proceed until the Founder issues an explicit unblock.

| Gate (per §3)                                | When                                                                                                          | Manual Verification Performed                                                                                                                                                                                                                                                 |
| -------------------------------------------- | ------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Gate 1 — Foundation Sign-Off                 | After §11 schema, §7 FSM, §10 design tokens are wired<br>; verified by successful ECM-007 middleware response | (i) `alembic upgrade head` clean on a fresh DB; (ii) seeded ENUMs match `[TDD-ENUMS]`; (iii) audit_log REVOKE policy verified by attempting an UPDATE as the app role and confirming permission denied; (iv) CI-A green.                                                      |
| Gate 2 — Phase 1 Sign-Off                    | After HD-1 + HD-2 + Worker-EXTRACT operational                                                                | (i) Upload a real product image; (ii) confirm extraction confidence emits to UI; (iii) confirm Director Review surfaces all 5 fields; (iv) AC-1 + AC-2 green.                                                                                                                 |
| Gate 3 — Phase 2 + Phase 3 Sign-Off          | After HD-3 (Co-Pilot) + HD-4 (Strategist) operational                                                         | (i) Walk a bounded chat; confirm chat depth cap enforced; (ii) confirm Strategist returns a credit-locked plan; (iii) confirm credit lock occurs **before** Phase 4 enqueue; (iv) AC-3 + AC-4 green.                                                                          |
| Gate 4 — Phase 4 Sign-Off (Compliance Heavy) | After Worker-COMPOSE, Worker-EXPORT, C2PA, SGI operational                                                    | (i) Visually inspect SGI burn-in on both 1080×1080 and 1080×1920 exports; (ii) upload one signed export to Adobe **VerifyContentCredentials** and confirm green check-mark; (iii) confirm `compliance_log` row written with `check_type='c2pa_sign'`; (iv) AC-5 + AC-6 green. |
| Gate 5 — Pre-Beta Sign-Off                   | After E2E green + rollback drill executed                                                                     | (i) Run the rollback drill in §15.10; (ii) confirm SLA Watchdogs paging; (iii) confirm grievance pipeline completes a synthetic takedown end-to-end; (iv) all five CI jobs green; (v) all four `[PRD-AC-1..6]` E2E suites green.                                              |

### 15.8 Beta Gate Criteria — `[PRD-RELEASE-BETA]`

The Beta gate has two clusters per PRD: **B1..B5 (business / UX)** and **E1..E6 (engineering)**. The specific criteria text is normative in the PRD; this section lists the verification responsibility only.

|Cluster|ID|Verification Owner|Verification Surface|
|---|---|---|---|
|B1..B5|Business / UX|Founder (Manual)|Beta cohort feedback log + retention metric per PRD §RELEASE-BETA|
|E1..E6|Engineering|CI + L4 E2E|All five CI jobs green; L4 suite green; observability dashboard live per `[PRD-FEATURES-INFRA]` F-606|

### 15.9 MVP Gate Criteria — `[PRD-RELEASE-MVP]`

`M1..M10` are the ten MVP release criteria in PRD. They subsume Beta gate plus the additional production-hardening surface. Verification owners:

|Verification|Owner|Surface|
|---|---|---|
|M1..M5 (functional completeness)|CI L4 + Founder Gate 5|E2E suite + Manual checklist|
|M6..M8 (compliance, retention, takedown SLA)|CI-B + cron observation in staging|`compliance_log` integrity, `retention_sweep` dry-run, synthetic takedown|
|M9 (rollback drill executed in past 7 days)|Founder|§15.10 drill log entry|
|M10 (observability + on-call rota live)|Founder|`[PRD-FEATURES-INFRA]` F-606/F-607 dashboards green|

### 15.10 The Rollback Drill — `[TDD-ROLLBACK]-F`

The rollback drill is the **terminal pre-launch check**. It must be executed against staging within the seven days preceding the production launch and re-executed at any deploy that touches the schema, the worker chain, or the payment surface.

**Procedure (must complete in <30 minutes wall-clock):**

1. Tag the current production-equivalent staging deploy as `rollback-drill-pre`.
2. Roll forward one synthetic schema migration + one synthetic worker change.
3. Run a synthetic E2E generation through HD-1..HD-6 to confirm forward path works.
4. Trigger rollback via the documented runbook (Helm rollback + `alembic downgrade -1`).
5. Confirm the in-flight generation lands cleanly in `failed_compose` or `failed_export` with refund issued (DLQ Branch behaviour preserved across rollback).
6. Confirm idempotency cache survives (Redis DB5 not flushed by rollback).
7. Confirm `audit_log` partitions are intact (no DETACH triggered by rollback).
8. Re-run all five CI jobs against the rolled-back deploy; all must remain green.
9. Founder logs the drill in `docs/rollback_drills/<YYYY-MM-DD>.md`.

### 15.11 Observability and SLA Monitoring

Per `[PRD-FEATURES-INFRA]` F-601..F-607 and `[TDD-OBSERVABILITY]`:

|Signal|Source|Threshold|Page|
|---|---|---|---|
|Generation success rate (rolling 1h)|`generations` table|< 92%|PD-Warn|
|Phase 4 p95 latency|ARQ job runtime|> 240s|PD-Warn|
|C2PA sign failure rate|`compliance_log`|> 1%|PD-Critical|
|Grievance ACK SLA breach|`takedown_sla_watchdog`|any breach|PD-Critical|
|Idempotency cache hit-rate|Redis DB5|< 5% on retry traffic|PD-Warn (suggests cache disabled)|
|Credit lock hold time p95|Redis DB2|> 6s|PD-Warn|
|DLQ depth|ARQ DLQ list|> 25 jobs|PD-Critical|

### 15.12 Dependencies with Other Sections

§15 is the verification mirror of §11 (data invariants), §12 (API surface), §13 (failure paths), and §14 (compliance). It depends on §3 (gate definitions) for halt points and on §16 (execution order) for the timeline at which each layer is exercised. 

---

## 16. Execution Order and Open Gaps

### 16.1 Purpose

This is the terminal section of the BEF. It linearises the build into a single deterministic sequence the Agentic IDE can execute, names the five mandatory halt points (the Founder approval gates established in §3), and explicitly enumerates the open gaps where PRD or TDD are silent or in tension. 

### 16.2 What this section defines

- The phase-by-phase build order across the 15-day sprint window.
- The five Founder approval gates as halt points within the sequence.
- The per-task file authorship order.
- The list of open gaps and reconciliation tickets the Founder must resolve.
- The frozen out-of-scope items.

### 16.3 What this section does NOT define

- The content of the Founder approval gates (lives in §3).
- The CI pass criteria (lives in §15).
- New scope, new screens, new states, or new endpoints.

### 16.4 The Build Order

The 15-day build window is partitioned into seven micro-phases.

| #   | Window                 | Micro-phase                                                                                                                                                             | Owning BEF Sections                                                                 | Exit Condition                            |
| --- | ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- | ----------------------------------------- |
| 1   | Days 1–3 (May 1-3)     | **Foundation** — repo scaffold, design tokens, FSM seed, schema migration v1, ENUM seed, audit_log REVOKE policy                                                        | §7, §10, §11                                                                        | Gate 1 Verified                           |
| 2   | Days 4–5 (May 4-5)     | **Phase 1 Build** — HD-1 upload, Worker-EXTRACT, HD-2 Director Review, confidence emit, intent gate                                                                     | §6, §8 (Phase 1), §9 (Director chain), §10, §12 (`/generations`)                    | Gate 2 cleared                            |
| 3   | Days 6–7 (May 6–7)     | **Phase 2 + Phase 3 Build** — HD-3 bounded Co-Pilot, Worker-PHASE2, script lock, HD-4 Strategist, asset selection, credit lock                                          | §6, §8 (Phases 2+3), §9 (Co-Pilot + Strategist), §10, §12 (`/copilot`, `/strategy`) | Gate 3 cleared                            |
| 4   | Days 8–10 (May 8–10)   | **Phase 4 Build (Heavy)** — Worker-COMPOSE, FFmpeg filter graph, Worker-EXPORT, C2PA signing, SGI burn-in, HD-5 progress, HD-6 declaration                              | §6, §8 (Phase 4), §10, §12 (`/render`, `/declaration`, `/export`), §14              | Gate 4 cleared                            |
| 5   | Days 11–12 (May 11-12) | **Cross-Cutting Hardening** — DLQ branches A/B/C, refund/retry-export, idempotency middleware, payment FSM, webhook origin-restore, retention sweeps, takedown pipeline | §11 (concurrency), §12 (`/retry-export`, `/webhook`), §13, §14.10–§14.11            | All five CI jobs green                    |
| 6   | Days 13–14 (May 13–14) | **L4 E2E + Observability** — full Playwright walks for AC-1..AC-6, observability dashboard wiring, SLA watchdogs, on-call rota                                          | §15.5–§15.6, §15.11                                                                 | E2E suite green; dashboards live          |
| 7   | Day 15 (May 15)        | **Pre-Beta Lock** — rollback drill, MVP gate dry-run, freeze of `main`                                                                                                  | §15.10, §16.5                                                                       | Gate 5 cleared → enter closed beta May 10 |

### 16.5 The Five Mandatory Founder Approval Gates (Halt Points)

The agent must STOP at each gate, post the verification artifact bundle defined in §15.7, and wait for an explicit Founder unblock before authoring any file in the next micro-phase.

| Gate   | Halt After Micro-phase  | Verification Surface                                                                                                                                                  | Unblock Signal                               |
| ------ | ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------- |
| Gate 1 | 1 (Foundation)          | §15.7 row 1 + CI-A green                                                                                                                                              | Founder posts `unblock: gate-1` in build log |
| Gate 2 | 2 (Phase 1)             | §15.7 row 2 + AC-1 + AC-2 green                                                                                                                                       | Founder posts `unblock: gate-2`              |
| Gate 3 | 3 (Phase 2+3)           | §15.7 row 3 + AC-3 + AC-4 green                                                                                                                                       | Founder posts `unblock: gate-3`              |
| Gate 4 | 4 (Phase 4)             | §15.7 row 4 + C2PA manifest validates using local `c2patool --verify`. External verification tools are optional and not part of system execution. + AC-5 + AC-6 green | Founder posts `unblock: gate-4`              |
| Gate 5 | 6 (E2E + Observability) | §15.7 row 5 + rollback drill log entry + all dashboards live                                                                                                          | Founder posts `unblock: gate-5 → enter-beta` |

### 16.6 Per-Task File Authorship Order (Within a Micro-phase)

Within any micro-phase, file authorship follows a fixed local order derived from §1.4:

1. **Schema / migration** (if any) — authored and reviewed before any code that depends on it.
2. **ENUMs / types** — authored before the routes/workers that import them.
3. **Worker / domain logic** — authored before the API route that enqueues it.
4. **API route** — authored before the UI component that calls it.
5. **UI component** — authored last in the slice.
6. **Test file for the slice** — authored immediately after the file it tests.

### 16.7 Open Gaps and Reconciliation Tickets

| GAP-ID | Surface                                                                                                                             | Description                                                                                                                                                               | Blocking Micro-phase | Resolution Owner                                                                      |
| ------ | ----------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------- | ------------------------------------------------------------------------------------- |
| GAP-01 | Beta engineering criteria E1..E6                                                                                                    | PRD enumerates the IDs but the criterion text is not reproduced in TDD §CICD. Per §15.8, agent must read PRD at execution time.                                           | 6                    | Founder confirms PRD §RELEASE-BETA is current                                         |
| GAP-02 | Co-Pilot chat depth cap                                                                                                             | PRD `[PRD-COPILOT]` specifies "bounded"; TDD `[TDD-CHAT-CHAIN]` specifies a numeric cap. If they disagree at execution time, PRD wins per §2.6.                           | 3                    | Founder reads both, confirms numeric cap                                              |
| GAP-03 | Idempotency TTL on 4xx responses                                                                                                    | PRD `[PRD-IDEMPOTENCY]` says cache 2xx only; TDD `[TDD-CONCURRENCY]-A` confirms. CI-C enforces. No gap; flagged for visibility in case of future drift.                   | 5                    | None — already enforced                                                               |
| GAP-04 | Audit log partition retention beyond 5 years                                                                                        | PRD `[PRD-FEATURES-RETENTION]` says DETACH at 5y; TDD `[TDD-MIGRATIONS]` confirms. The offline archive destination is **not specified** in either document.               | Post-MVP             | Founder defines archive sink before first DETACH (anniversary)                        |
| GAP-05 | C2PA signing key rotation                                                                                                           | TDD `[TDD-WORKERS]-I` references the signing key but does not specify the rotation cadence. PRD is silent.                                                                | 4                    | Founder defines rotation policy before Gate 4                                         |
| GAP-06 | Grievance form UI surface                                                                                                           | §14.10 specifies the pipeline; PRD `[PRD-FEATURES-COMPLIANCE]` F-505 references the form but the BEF §10 component tree (already frozen) does not place it in HD-1..HD-6. | Post-MVP             | Founder confirms grievance form lives at `/grievance` route outside the 6-screen flow |
| GAP-07 | C2PA manifest validates using local `c2patool --verify`. External verification tools are optional and not part of system execution. | §15.7 Gate 4 requires Adobe verification. The tool is external; SLA is uncontrolled.                                                                                      | 4                    | Founder accepts external dependency risk; fallback is `c2patool --verify` local       |
| GAP-08 | Rollback drill cadence post-launch                                                                                                  | §15.10 specifies pre-launch and at-deploy. PRD `[PRD-RELEASE-MVP]` M9 says "past 7 days." The post-MVP cadence is not specified.                                          | Post-MVP             | Founder sets ongoing drill cadence post-May-20                                        |
| GAP-10 | confidence_score computation source | [TDD-WORKERS]-B description implied Vision model returns confidence alongside product_brief. Decision: compute deterministically from BiRefNet alpha mask using foreground_ratio × edge_sharpness_penalty. Reason: deterministic, controllable, tweakable at code level, ₹0 marginal cost. Output contract float ∈ [0.0, 1.0] unchanged. PRD unaffected. | 2 | Founder + Architect approved — mask-based computation |
| GAP-11 | HD-3 script tile count when partial Worker-SAFETY pass | `[PRD-HD3]` describes "3 framework-tagged tiles" but PRD is silent on what HD-3 renders when Worker-SAFETY rejects 1 or 2 of the 3 scripts (i.e., `safe_scripts` has 1 or 2 items, not 3). TDD `[TDD-WORKERS]-F` defines `SafetyError` only for the all-3-rejected case, leaving the partial pass case unspecified. Resolution (Founder-approved 2026-05-07): (a) HD-3 renders ONLY the tiles present in `safe_scripts`. If 2 pass, show 2 tiles. If 1 passes, show 1 tile. Never render a placeholder or empty slot for a rejected script. (b) The SSE `scripts_ready` event payload gains two new fields: `scripts_available: int` (count of safe_scripts items, 1–3) and `rejected_frameworks: [{framework: string, reason: string}]` (empty array when all 3 pass; populated for client telemetry only — never rendered as user-visible error text). (c) Zero-tile state is impossible at `scripts_ready`: phase2_chain enters `failed_safety` before `scripts_ready` if all 3 fail. (d) UI pre-selects tile 1 (highest CRITIC score) regardless of how many tiles are shown. | 3 | Resolved — Founder + Architect approved 2026-05-07 |
| GAP-12 | Worker-STRATEGIST cold-start style defaults for new users | `[TDD-WORKERS]-G` states Worker-STRATEGIST "falls back to heuristics" when `user_style_profiles` is empty (new user, first generation), but the heuristics are defined nowhere in PRD or TDD. This leaves `strategy_card.style_summary` and HD-4's motion/environment display fields unspecified for every first-generation user. Resolution (Founder-approved 2026-05-07): Freeze the following `COLD_START_DEFAULTS` constant in `app/workers/strategist.py`. This constant is the sole authoritative source for first-gen style defaults. Values keyed by `product_brief["category"]` (a `GreenZoneCategory` ENUM value): `packaged_food` → `{motion: "gentle_zoom", environment: "kitchen_warm"}`; `d2c_beauty` → `{motion: "product_reveal", environment: "clean_white"}`; `electronics` → `{motion: "spec_overlay", environment: "minimal_studio"}`; `fashion` → `{motion: "slow_pan", environment: "outdoor_natural"}`; `home_decor` → `{motion: "ambient_float", environment: "living_room_warm"}`. Any category not in this dict uses fallback `{motion: "gentle_zoom", environment: "clean_white"}` silently — no error, no log. Once a user completes their first generation, the style memory upsert in Worker-EXPORT (`[TDD-WORKERS]-I`) fires, and `COLD_START_DEFAULTS` is never consulted again for that user. | 3 | Resolved — Founder + Architect approved 2026-05-07 |

### 16.8 Frozen Out-of-Scope Items (Post-MVP)

Per `[PRD-UX-FREEZE]`, the following are **explicitly out of scope** for v1.0 and must not be authored, scaffolded, or stubbed by the Agentic IDE during the 15-day build:

- Multi-language UI (English ,Hindi/Hinglish/Marathi/Punjabi/Bengali/Tamil/Telugu,  at MVP).
- A/B testing infrastructure beyond the observability dashboard.
- Programmatic API access for external developers (no public API at MVP).
- Multi-user / team accounts (single-user accounts only).
- Custom LUT upload (LUTs are seeded constants per `[TDD-VIDEO]-A`).
- Watermark customisation by user (SGI watermark is fixed per §14.5).
- Export formats beyond 1080×1080 and 1080×1920.
- Self-serve refund without DLQ trigger (refunds are DLQ-driven only per §13).
- Style Memory cross-user sharing — `user_style_profiles` is strictly per-user per `[PRD-MOATS]`.
- Webhook destinations other than the configured payment provider.
- Any modification of the 6-screen linear flow, the 4-phase pipeline, or the 22-state FSM.

### 16.9 Sprint Calendar (Concrete Dates)

| Date   | Micro-phase / Milestone                                  |
| ------ | -------------------------------------------------------- |
| May 1  | Build starts; foundation begins                          |
| May 2  | Foundation expected complete; Gate 1 due                 |
| May 3  | Phase 1 complete; Gate 2 due                             |
| May 4  | Phase 2+3 complete; Gate 3 due                           |
| May 5  | Phase 4 complete; Gate 4 due                             |
| May 6  | Cross-cutting hardening complete; all 5 CI jobs green    |
| May 7  | E2E + observability green                                |
| May 8  | Gate 5 cleared; rollback drill logged; closed beta opens |
| May 9  | Closed beta cohort run; B1..B5 + E1..E6 monitored        |
| May 10 | M1..M10 verified; production launch                      |

### 16.10 Definition of Done — Document Level

The BEF v1.0 is considered done when all of the following hold:

1. Sections 1–16 are present, MECE-separated, and free of cross-section content duplication.
2. Every PRD anchor referenced in §2.5 maps to at least one BEF section that sequences it.
3. Every TDD anchor referenced in §2.5 maps to at least one BEF section that sequences it.
4. Every open gap in §16.7 has either been resolved or is explicitly flagged with a blocking micro-phase.
5. The five Founder approval gates from §3 are placed on the timeline in §16.5 in the same order they appear in §3.
6. No section contains code blocks, SQL DDL, or other implementation artefacts that belong in the TDD.
7. No section invents a feature, screen, state, ENUM value, or endpoint not present in PRD v3 or TDD v3.

### 16.11 Closing Authority Statement

This Blueprint Execution File v1.0 is the operating contract under which Google Antigravity (the Agentic IDE) authors AdvertWise code and the Founder reviews it during the Apr 26 → May 20 sprint. It is a **third-tier authority document**: subordinate to PRD v3 on contract questions, subordinate to TDD v3 on implementation questions, and authoritative on execution sequencing, halt points, and gap resolution.

Any divergence between this BEF and PRD v3 / TDD v3 on a non-execution matter is automatically resolved in favour of PRD or TDD per §2.4. Any divergence on an execution matter (order, gates, single-file scope, halt rules) is resolved in favour of this BEF. 

### 16.12 Dependencies with Other Sections

§16 is the closing index. It depends on §1 for reading rules, §2 for the authority hierarchy, §3 for gate definitions, §11–§14 for the implementation surfaces it sequences, and §15 for the verification surface that proves each gate. No section depends on §16 — it is a strict consumer.
