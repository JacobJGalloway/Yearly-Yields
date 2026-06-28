# Yearly Yields — Architecture v1.3

> **Intended audience:** Claude Code, sprint planning sessions, project handoff.
> **Status:** Pre-sprint architectural design. Approved scope, pending sprint start.
> **Parent system:** [Yearly Yields](https://github.com/JacobJGalloway/YearlyYields) (Python / FastAPI / Angular / PostgreSQL + pgvector)
> **Sprint model:** Two-week sprint. Scope not completed by end of sprint moves to v1.4.
> **Sprint goal:** Demo stable — pilot client and user feedback ready.
> **Git history:** Refer to `main` branch merge commit notes for v1.2 and prior landed work.

---

## Table of Contents

1. [Sprint Goal & Definition of Done](#1-sprint-goal--definition-of-done)
2. [v1.3 Scope — In Sprint](#2-v13-scope--in-sprint)
3. [v1.4 Scope — Demo Stable Hardening](#3-v14-scope--demo-stable-hardening)
4. [Feature: pgvector Embedding Purge](#4-feature-pgvector-embedding-purge)
5. [Feature: Invoice Customer Assignment in UI](#5-feature-invoice-customer-assignment-in-ui)
6. [Feature: Demo Reset Endpoint](#6-feature-demo-reset-endpoint)
7. [Feature: Alert / Notification Separation](#7-feature-alert--notification-separation)
8. [Human-in-the-Loop Checkpoints](#8-human-in-the-loop-checkpoints)
9. [Out of Scope — v1.3](#9-out-of-scope--v13)

---

## 1. Sprint Goal & Definition of Done

**Demo stable** means: a pilot client can be walked through a live operational demo session without encountering broken UI states, missing data, or incomplete workflows. Crop cycles must appear visibly mid-season, the alert system must reflect its correct responsibility, and invoice management must not require Swagger access.

A v1.3 release to `main` is considered **complete** when:

- [x] pgvector embedding purge is hooked into the existing deletion and weekly rollup pipeline; the vector store no longer grows unboundedly from deleted or summarized sensor readings
- [x] Invoice detail card has a customer dropdown; no Swagger access required to assign or change a customer on a draft invoice
- [ ] Demo reset endpoint is implemented, tested, and validated end-to-end; demo cycles are visibly mid-season on any run date without manual seed recalculation
- [x] `harvest_ready` is removed from `AlertType` via migration; the alert system is anomaly-detection only
- [ ] Lighthouse baseline audit complete across all three themes; findings list exported and handed off to v1.4
- [ ] All v1.3 items above are merged to `main`

---

## 2. v1.3 Scope — In Sprint

| # | Feature | Weight | Notes |
|---|---------|--------|-------|
| 4 | pgvector embedding purge | Medium | Event hook into existing deletion + rollup pipeline |
| 5 | Invoice customer assignment in UI | Light | Dropdown on invoice detail card; no backend schema change |
| 6 | Demo reset endpoint | Medium | Foundational work from prior sprints is lost — rebuild and validate |
| 7 | Alert / notification separation | Light | Single migration: drop `harvest_ready` from `AlertType` enum |
| 8 | Lighthouse baseline audit | Light | Run Lighthouse against all three themes; export prioritized findings list for v1.4 ARIA + contrast work |

### Task 8 — Lighthouse Baseline Audit

Run Lighthouse (or axe DevTools) against the app in all three themes — light, dark, and client theme — and export a prioritized findings list. This is reconnaissance, not remediation. Color token adjustments and ARIA fixes land in v1.4; this task exists so v1.4 starts with a known hit list rather than a freehand page scan.

Output: a findings list (Markdown or exported report) committed to the repo, covering contrast failures by theme and missing ARIA roles/labels by component. Color token findings feed back into Claude Design for design system documentation updates.

---

## 3. v1.4 Scope — Demo Stable Hardening

Yearly Yields carries three themes (light, dark, and the third client theme), making the ARIA/WCAG pass higher priority than in Switchyard. It is deferred from v1.3 only because it is isolated in scope with no cross-functional dependencies — not because it is optional for the pilot.

| # | Feature | Rationale for deferral |
|---|---------|------------------------|
| 1 | ARIA compliance audit — three-theme surface area, board columns, cards, icon-only buttons, skip-nav | Isolated; no functional dependencies. Higher surface area than Switchyard due to three themes. |
| 2 | Color contrast audit (WCAG AA) — light, dark, and client theme | Isolated; no functional dependencies |

> These land in v1.4 as a hardening sprint before the pilot goes live. They are not "someday" items. The three-theme surface area makes this a meaningful audit — budget accordingly.

---

## 4. Feature: pgvector Embedding Purge

### Problem
Voyage-3 embeddings in `pgvector` for sensor readings are never cleaned up when the source readings are deleted or rolled into weekly summaries. The vector store grows unboundedly over time, which will cause performance and cost problems at scale.

### Target State
Purge orphaned embeddings from `pgvector` when their source sensor readings are either:
- **Deleted** — hook into the existing deletion path
- **Rolled into a weekly summary** — hook into the existing weekly rollup pipeline

### Design Notes
- This is an **event hook**, not a scheduled cron job — purge happens as a side effect of the existing deletion and rollup operations, not independently
- The purge should be transactional with the triggering operation where possible — a rollup that succeeds but leaves orphaned embeddings is a partial failure
- Log purge counts alongside rollup/deletion logs for observability
- No new API endpoints required; this is internal pipeline work

### Constraints & Guardrails for Claude Code
- Do not modify the rollup or deletion logic in ways that change their existing behavior — the embedding purge is additive
- If the existing rollup or deletion paths are not easily hookable, surface the finding rather than restructuring them

---

## 5. Feature: Invoice Customer Assignment in UI

### Problem
Draft invoices currently require Swagger to assign or change the customer. This is a friction point that blocks farmers and hired hands from managing invoices without developer access.

### Target State
A customer dropdown on the invoice detail card that allows the assigned customer to be set or changed directly in the UI.

### Design Notes
- The dropdown should populate from the existing customer list — no new customer management scope is added here
- The interaction is on the **invoice detail card**, not a separate screen
- Only draft invoices should allow customer reassignment; finalized invoices should display the customer as read-only
- No schema change is expected — customer assignment is likely already in the data model; this is a UI exposure of existing functionality

### Constraints & Guardrails for Claude Code
- Confirm whether the customer FK already exists on the invoice model before adding anything to the schema
- If the customer list endpoint does not exist, create a lightweight read-only endpoint — do not expose customer management scope beyond what the dropdown needs

---

## 6. Feature: Demo Reset Endpoint

### Context
Foundational work toward this feature was scoped in v1.1 and v1.2 but did not land in `main`. Treat this as a full rebuild, not a continuation. Validate end-to-end before considering it complete.

### Target State
`POST /api/v1/admin/demo-reset`

- **Auth:** Owner-only. Disabled entirely in production environments.
- **Behavior:** Wipes existing crop cycle demo data and rebuilds it with `planted_at` recalculated relative to today at runtime, so every demo starts with cycles visibly mid-season without manual seed recalculation.
- **Idempotent:** Safe to run multiple times. Each run produces the same relative board state regardless of when it is run.

### Date-Relative Seeding Logic
- **Open fields** reflect the real calendar — if the demo runs in winter, open field cycles appear fallow. No artificial offset. This demonstrates natural seasonal tracking.
- **Greenhouse plots** carry date-relative `planted_at` offsets so cycles always appear at varied active phases regardless of demo run date. This is where anomaly alerts, phase transitions, and monitoring activity are demonstrated.
- Phase offsets across greenhouse plots should be spread across stages — not all plots at the same phase
- `planted_at` offsets should be defined as named constants or a config block, not scattered through seed logic
- The endpoint should return a summary of what was seeded (cycle counts, date ranges, phase distribution per area) so the presenter can confirm the greenhouse plots are in the right phases before the demo

### Production Safety
- The endpoint must be explicitly disabled in production — a feature flag, environment check, or router exclusion, not just an auth check alone
- Document the production disable mechanism in the endpoint's inline comments so it is not accidentally re-enabled

### Validation Requirement
End-to-end validation is part of the Definition of Done for this feature. Claude Code should:
1. Seed via the endpoint
2. Confirm crop cycles appear mid-season in the UI
3. Run the endpoint a second time and confirm idempotency
4. Confirm the endpoint is unreachable in a production environment config

---

## 7. Feature: Alert / Notification Separation

### Problem
`harvest_ready` currently exists in `AlertType`, which is the anomaly-detection alert system. Harvest readiness is not an anomaly — it is a phase transition. Its presence in `AlertType` misrepresents the alert system's responsibility and conflates two distinct concerns.

### Decision
The responsibility for calling the harvest rests with owners, farmers, and hired hands — not the alert system. The system's job is anomaly detection. Phase transitions are human judgment calls.

### Target State
- Remove `harvest_ready` from the `AlertType` enum via database migration
- Remove any code paths that create, read, or route `harvest_ready` alert records
- The UI should not surface `harvest_ready` as an alert type anywhere after this migration

### What This Is Not
This is not the implementation of a phase transition notification service. That service — which would handle signals like `planted → growing`, `growing → flowering`, `growing → harvest_ready` — is a future feature (see Out of Scope). This sprint only removes the misplaced enum value. Do not begin designing or scaffolding the notification service as part of this work.

### Migration Notes
- Write the migration to drop the enum value cleanly
- If any existing demo or test seed data contains `harvest_ready` alert records, the migration or a companion seed cleanup should remove them
- Confirm no foreign key or check constraint references `harvest_ready` before dropping

---

## 8. Human-in-the-Loop Checkpoints

These are points in the sprint where Claude Code should **pause and surface** rather than proceed independently.

| Checkpoint | Feature | What to surface |
|------------|---------|-----------------|
| Demo seed phase distribution | Demo Reset (#6) | Surface the proposed `planted_at` offset constants and greenhouse plot phase distribution before seeding (open fields reflect real calendar state; greenhouse plots carry artificial offsets for active monitoring demo), so the owner can confirm the cycle phases look right before presenting. |
| Customer dropdown behavior on finalized invoices | Invoice UI (#5) | If there is ambiguity about what "finalized" means in the current model, surface the question with a specific example rather than choosing an approach silently. |
| Orphaned embedding discovery | pgvector Purge (#4) | If the audit of existing embeddings reveals a larger-than-expected orphan count or unexpected embedding types, surface the finding before purging. |

---

## 9. Out of Scope — v1.3

The following are explicitly **not** in this sprint. Do not begin work on these without a scope change.

- ARIA compliance audit (v1.4)
- Color contrast audit, WCAG AA, all three themes (v1.4)
- Phase transition notification service (`planted → growing`, `growing → harvest_ready`, etc.) — future architecture; do not scaffold
- User-to-growing-area assignment model
- Configurable crop phase day admin UI
- IoT reading source and device registration
- SMS alert notifications (blocked on free provider availability, not priority)
- Any features listed as "Backlog" in the README
