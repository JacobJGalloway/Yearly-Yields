# Yearly Yields 1.1 — Architecture

Yearly Yields is an agricultural monitoring and yield prediction system built for Mid-West farmers. The system ingests IoT sensor readings from open fields and greenhouses, runs a ReAct agentic loop powered by Claude to detect anomalies against rolling historical data, fires email alerts, and supports yield planning and invoice tracking across crop cycles.

The architecture is **AI-first by design** — the agent loop is not a feature added to a web app, it is the core of the system. FastAPI serves as the computational middleware that feeds and supports the agent, and Angular 21 surfaces the results in a responsive, farm-appropriate UI. Every layer exists in service of that design center.

**v1.1 adds:**
- A local MCP server exposing the Yearly Yields database as on-demand tools for the agent, replacing full-context payloads and controlling token cost as fIoT reading volume scales
- Prompt caching on stable system prompt sections across the anomaly and chat agents
- Chat session memory persisted between sessions via MCP file-based memory
- NOAA CDO historical backfill trigger with data gap approval and averaged anomaly detection feeding the existing ReAct resolution cycle
- Completion of the brand token system, data retention pipeline, and several targeted bug fixes and constraint enforcements

---

## 2. System Architecture

Yearly Yields is composed of four primary layers — frontend, API middleware, agent, and data — with three external integrations. Every layer is oriented around supporting the agent's ability to make accurate, low-cost anomaly decisions.

```
┌─────────────────────────────────────────────────────┐
│                  Angular 21 Frontend                │
│         (Material 3 · NgRx · Responsive UI)         │
└─────────────────────┬───────────────────────────────┘
                      │ HTTP / JWT
┌─────────────────────▼───────────────────────────────┐
│                FastAPI Middleware                    │
│   (SQLAlchemy async · RBAC · Background Jobs)       │
│                                                     │
│   ┌─────────────┐          ┌─────────────────────┐  │
│   │ Anomaly     │          │ Dashboard Chat      │  │
│   │ Service     │          │ Agent               │  │
│   └──────┬──────┘          └──────────┬──────────┘  │
└──────────┼───────────────────────────┼──────────────┘
           │ Anthropic SDK             │ Anthropic SDK
┌──────────▼───────────────────────────▼──────────────┐
│                 Claude (claude-sonnet-4-6)           │
│              ReAct Loop · Prompt Caching             │
└──────────────────────┬──────────────────────────────┘
                       │ MCP Tool Calls
┌──────────────────────▼──────────────────────────────┐
│              Local MCP Server                       │
│  get_crop_ranges · get_phase_context                │
│  get_recent_readings · get_active_alert             │
└──────────────────────┬──────────────────────────────┘
                       │ SQLAlchemy async
┌──────────────────────▼──────────────────────────────┐
│           PostgreSQL 16 + pgvector                  │
│    sensor_readings · weekly_sensor_summaries        │
│    crop_cycles · alerts · embeddings (voyage-3)     │
└─────────────────────────────────────────────────────┘

External Integrations
─────────────────────
NWS api.weather.gov   →  Live field readings + fIoT greenhouse simulation
NOAA CDO              →  Historical backfill (NOAA_CDO_TOKEN required)
SendGrid              →  Email alert fan-out
```

### Layer Responsibilities

**Angular 21** surfaces agent decisions and farm data in a responsive UI designed for desktop, tablet, and mobile. It does not contain business logic — it renders what the API and agent produce.

**FastAPI** is the computational middleware. It owns the database, enforces RBAC, runs background jobs (nightly purge, quarterly summarization, NWS polling), and orchestrates the agent calls. It is the boundary between the outside world and the agent.

**Claude via ReAct loop** is the decision engine. On every sensor reading it reasons over historical context, live weather, and crop phase data — then acts by raising, updating, or resolving alerts. The dashboard chat agent answers farmer queries against the same data layer.

**Local MCP server** replaces full-context payloads with on-demand tool calls. The agent fetches only what it needs per decision, keeping token cost flat as fIoT reading volume grows.

**PostgreSQL + pgvector** is the single source of truth. pgvector stores voyage-3 embeddings for sensor readings, enabling similarity search that gives the agent historical context without full table scans.

---

## 3. Data Model

Yearly Yields uses PostgreSQL 16 with pgvector. The schema is organized around `growing_areas` as the top-level domain entity — every data-generating table anchors back to it through a compound primary key pattern that keeps reads and writes scoped to their physical origin.

### Primary Key Strategy

A universal compound PK is used across all event-chain tables:

| Table | Primary Key |
|-------|-------------|
| `growing_areas` | own PK |
| `crop_cycles` | own PK |
| `growing_area_plots` | `(growing_area_id, seq)` |
| `sensor_readings` | `(growing_area_id, growing_area_plot_id, seq)` |
| `alerts` | `(growing_area_id, growing_area_plot_id, seq)` |
| `weekly_sensor_summaries` | `(growing_area_id, growing_area_plot_id, seq)` |

This scopes PostgreSQL's integer sequences per growing area, keeping keys meaningful within their physical context and giving technicians a direct path to the source of any anomaly without cross-table joins.

### Row/Plot Model

`growing_area_plots` sits between `growing_areas` and sensor data, providing the granular physical anchor the agent and technicians need:

- **Greenhouses** — must have at least one row/plot recorded (enforced at the API layer). In practice greenhouses will have multiple rows, giving the agent and alert system row-level precision.
- **Open fields** — assigned `growing_area_plot_id = 0` (hardcoded, representing the whole field). The UI suppresses display of row_id = 0 so farmers never see a meaningless "Row 0" on an open field view. If a field is later subdivided for seed testing, additional row/plot records are added without any schema change.

This makes the compound PK universal across all growing area types with no nullable columns and no conditional key logic.

### Crop Cycle Phase

Crop cycle phase is **derived, not stored**. The active phase (Seeding / Growing / Harvesting) and crop-specific sub-phase are calculated at runtime from `planted_at` combined with the per-crop day constants in `app/core/crop_phases.py`. This keeps the constants as the single source of truth — no enum column to migrate when phase definitions change.

### pgvector Embeddings

The `sensor_readings` table carries a voyage-3 embedding column directly on the reading row. The embedding serves as the unique contextual anchor for that reading — analogous to a Cosmos DB RowKey — and supports cosine similarity search for the ReAct loop's historical context retrieval. A default order is maintained but can be reordered per query context or manually reset. This gives the agent relevant historical context rather than simply recent context.

### Event-Chain Tables

`sensor_readings`, `alerts`, and `weekly_sensor_summaries` are the active participants in the system's event chain. A new reading triggers the ReAct loop, which may raise or update an alert, which may trigger email fan-out — each action a potential trigger for the next. The architecture is AI-first but follows the same fundamental pattern as Event Driven Design meeting Domain Driven Design: either side of the agent boundary can initiate a workflow that completes on the other side.

### Data Retention Pipeline

Sensor data is managed across three retention tiers:

| Tier | Schedule | Action |
|------|----------|--------|
| Nightly purge | Every 24h | Hard-deletes `sensor_readings` older than `DATA_RETENTION_DAYS` (default 3 years) |
| Quarterly summarization | Mar 31 / Jun 30 / Sep 30 / Dec 31 | Aggregates daily readings older than `DAILY_RETENTION_DAYS` (default 90 days) into `weekly_sensor_summaries`, then deletes source rows |
| Annual roll-up | Deferred | Held pending user feedback on year-over-year query patterns. Weekly summary granularity is preserved to support farmer-facing seasonal comparisons (e.g. current week vs same week prior years). Annual totals for UI bar charts are derived via aggregation query at render time — no destructive roll-up required. |

The quarterly averaging function is shared with the backfill anomaly averaging path — open field and greenhouse backfill observations are averaged over the gap window before being passed to the ReAct loop, reusing the same logic rather than duplicating it.

---

## 4. API Layer

FastAPI serves as the computational middleware for Yearly Yields — owning the database, enforcing access control, orchestrating background jobs, and managing all external integrations. It is the boundary between the outside world and the agent.

All routes are versioned under `/api/v1/`. Admin bootstrap and seed endpoints are grouped under `/api/v1/admin/` and routed through a dedicated admin controller.

### Route Structure

| Group | Prefix | Notes |
|-------|--------|-------|
| Admin | `/api/v1/admin/` | Bootstrap, seed, and backfill endpoints — owner only, dedicated controller |
| Growing Areas | `/api/v1/growing-areas/` | Field and greenhouse management |
| Row/Plots | `/api/v1/row-plots/` | Row/plot management per growing area |
| Sensor Readings | `/api/v1/readings/` | Ingest and history per growing area and row/plot |
| Crop Cycles | `/api/v1/crop-cycles/` | Start, monitor, and close crop cycles |
| Alerts | `/api/v1/alerts/` | Active and resolved anomaly alerts |
| Yield Plans | `/api/v1/yield-plans/` | AI-generated yield predictions |
| Invoices | `/api/v1/invoices/` | Harvest and transplant invoice lifecycle |
| Customers | `/api/v1/customers/` | Harvest and transplant customer records |
| Users | `/api/v1/users/` | User management and role assignment |
| Auth | `/api/v1/auth/` | JWT login, token refresh, password reset *(v1.1)* |

### Authentication and RBAC

Authentication uses JWT (python-jose) with bcrypt password hashing. Role-based access control is enforced at the **route level** via FastAPI `Depends()` guards — owner, farmer, and hired hand roles each carry a defined permission set injected per endpoint.

> **Known gap:** RBAC is enforced at the route level only. There is no middleware-level safety net — a route that omits its `Depends()` guard is unprotected. Middleware-level hardening is a v1.2 candidate.

New users are assigned an initial password at creation. A forgot password / forced reset flow is added in v1.1 (email link → reset form on the login page).

### Background Jobs

Background jobs run as APScheduler tasks configured at FastAPI lifespan startup. Single-run startup workflows (seed data with PK duplicate ignores) fire once on boot without a persistent listener.

| Job | Trigger | Notes |
|-----|---------|-------|
| NWS polling | Every 6 hours | Fetches live readings per station location; fIoT greenhouse simulation applies per-building temperature and humidity offsets to NWS ambient data. Rate limit is per location — on-prem installs hold naturally at current cadence. Cloud-hosted multi-tenant throttling is a future client-feedback-driven addition. |
| Nightly purge | Every 24h | Hard-deletes `sensor_readings` older than `DATA_RETENTION_DAYS` |
| Quarterly summarization | Mar 31 / Jun 30 / Sep 30 / Dec 31 | Aggregates daily readings into `weekly_sensor_summaries`. A queue-backed worker pattern with a single topic is under consideration for this job given the potential row volume — avoids a second listener picking up the wrong message. |

### NOAA CDO Backfill

Historical backfill is triggered via `POST /api/v1/admin/backfill` — an owner-only admin endpoint. It is a one-time initialization action fired on initial install (on-prem or cloud), not a recurring job. Requires `NOAA_CDO_TOKEN` configured in `.env` before invocation. Once fired, it populates the historical sensor context the agent draws on for similarity search and anomaly baselining.

When the backfill detects a data gap larger than 7 days, a modal surfaces asking the farmer to approve or reject the historical fill. For confirmed gaps, observations are averaged over the gap window using the shared quarterly averaging function before being passed to the ReAct loop. A confirmed anomaly in the average is a stronger signal than any single reading — and the alert then resolves via the standard 3 consecutive normal readings cycle.

### External Integrations

| Integration | Purpose | Notes |
|-------------|---------|-------|
| NWS api.weather.gov | Live field readings + fIoT greenhouse simulation | Polled every 6 hours per station; open API, no token required |
| NOAA CDO | Historical backfill | One-time admin trigger on install; requires `NOAA_CDO_TOKEN` |
| SendGrid | Email alert fan-out | First anomaly + every 24h until 3 consecutive normal readings resolve |
| Anthropic SDK | Agent loop + dashboard chat | Covered in Section 5 |
| voyage-3 | Embedding generation | Called on reading ingest, stored in pgvector |

---

## 5. Agent Architecture

The agent layer is the core of Yearly Yields. Two distinct agents operate concurrently against the same data layer — the anomaly agent running continuously in the background and the farmer's chat agent responding to active user research. Neither interrupts the other.

### Anomaly Agent

The anomaly agent runs a ReAct (Reason + Act) loop on every sensor reading ingested by the system. It is the primary decision engine for alert lifecycle management.

**Loop mechanics:**
- Runs 1–10 reasoning iterations per reading depending on evidence clarity
- Pulls historical context via pgvector cosine similarity search against the reading's voyage-3 embedding — returning relevant historical readings rather than simply recent ones
- Queries live weather from NWS to contextualize the current reading against ambient conditions
- Decides whether to raise a new alert, update an existing alert, or resolve an active alert
- An alert resolves only after 3 consecutive normal readings — the agent will not resolve on a single normal reading regardless of confidence

**Pessimistic bias:**
The agent exhibits a consistent bias toward maintaining active alerts over resolving on insufficient evidence. Whether this is prompt-driven or emergent from Claude's base disposition toward caution when evidence is ambiguous is an open research question. The behavior aligns naturally with the system's agricultural safety goals — a missed anomaly carries real yield consequences — and is documented here as an observed characteristic rather than a configured parameter. Confidence calibration in ReAct agents remains an active area of exploration for v1.2 and beyond.

**Alert lifecycle:**
```
Reading ingested
      │
      ▼
ReAct loop (1–8 iterations)
      │
      ├── No anomaly detected → no action / resolve if 3rd consecutive normal
      │
      ├── Anomaly detected, no active alert → raise alert + fire SendGrid email
      │
      └── Anomaly detected, active alert exists → update alert
                  │
                  └── Every 24h → fire SendGrid reminder email
                              │
                              └── 3 consecutive normal readings → resolve alert
```

### Farmer's Chat Agent

The farmer's chat agent (`agent/chat.py`) is a separate agent with its own system prompt and persona. It responds to active farmer queries against the same data layer the anomaly agent operates on — crop cycles, sensor history, alerts, yield plans — without sharing prompt context with the anomaly loop.

Alert resolutions surface asynchronously from the farmer's active research session. A farmer can be mid-conversation investigating an anomaly while the anomaly agent simultaneously works toward resolution in the background. The chat session presents the resolution when it arrives without interrupting the conversation flow.

**v1.1 additions to both agents:**

| Feature | Impact |
|---------|--------|
| Prompt caching | `cache_control` added to stable system prompt sections in `agent/loop.py` and `agent/chat.py`. Reduces token cost on every agent call. Crop phase context and growing area config are stretch caching candidates for v1.1 or v1.2 depending on VRAM headroom. |
| Chat session memory | Farmer's chat history persisted between sessions via MCP file-based memory. Replaces full sliding-window message history resent on each request. |

### Local MCP Server *(v1.1 centerpiece)*

The local MCP server is the highest-impact architectural addition in v1.1. It exposes the Yearly Yields database as four on-demand tools, replacing full-context payloads passed to the agent on every call.

**Why this matters:** As fIoT reading volume grows, passing full context on every anomaly check and chat request scales token cost linearly with data volume. MCP flips that — the agent fetches only what it needs per decision, keeping token cost flat regardless of how much historical data accumulates.

**Exposed tools:**

| Tool | Purpose |
|------|---------|
| `get_crop_ranges` | Returns valid sensor ranges for the active crop and phase — the baseline the agent compares readings against |
| `get_phase_context` | Returns the current crop cycle phase and sub-phase derived from `planted_at` + `crop_phases.py` constants |
| `get_recent_readings` | Returns recent sensor readings for the growing area and row/plot — scoped to `(growing_area_id, growing_area_plot_id)` so greenhouse queries are row-level precise |
| `get_active_alert` | Returns the current active alert for the growing area and row/plot if one exists — gives the agent state continuity across loop iterations |

**Row/plot awareness:** All four tools are aware of the `row_plot_id` dimension. Greenhouse tool calls are scoped to the specific row throwing anomalies. Open field calls use `growing_area_plot_id = 0` transparently — the MCP layer handles the distinction without the agent needing to reason about growing area type.

**Token cost trajectory:**
```
MVP (full context payload)
  Token cost ∝ reading volume — grows linearly as fIoT data accumulates

v1.1 (MCP on-demand tool calls)
  Token cost ∝ query scope — flat regardless of total data volume
```

---

## 6. Frontend Architecture

The Angular 21 frontend surfaces agent decisions and farm data in a responsive UI designed for desktop, laptop, tablet, and mobile. It does not contain business logic — it renders what the API and agent produce. Every architectural decision in the frontend exists in service of that constraint.

### Stack

| Technology | Role |
|------------|------|
| Angular 21 | Framework — standalone components, signals, `@if`/`@for` control flow |
| Angular Material 3 | Component library — teal/cyan primary palette, Harvest Gold amber chips *(v1.1)* |
| NgRx | State management — feature-scoped lazy-loaded stores |
| JWT | Auth token carried on every HTTP request via interceptor |

### State Management

NgRx stores are **feature-scoped and lazy-loaded** — each route loads only the state it needs rather than hydrating a global store on startup. This keeps initial load performance flat as the application grows and is particularly important for a responsive UI that needs to feel immediate on tablet and mobile devices in the field.

### Brand Token System

The UI is built on an Angular Material 3 custom theme with a defined brand token system:

- **Primary palette** — teal/cyan (active)
- **Chips / FAB / secondary actions** — Material 3 tertiary palette swapped from azure to `mat.$amber-palette` in v1.1, completing the Harvest Gold brand token
- **Token architecture** — designed to support per-client palette overrides without structural changes. No additional palettes are in active scope for v1.1.

### Responsive Strategy

The UI targets four breakpoints — desktop, laptop, tablet, and mobile — using Angular Material's responsive grid and Angular CDK breakpoint observers. Breakpoint response is handled in TypeScript component logic rather than CSS media queries alone, allowing layout and data density decisions to be made at the component level.

### Row/Plot Display

`growing_area_plot_id = 0` (open field default) is suppressed at the presentation layer. Farmers never see a "Row 0" label on an open field view — the UI treats the whole field as the implicit unit. Greenhouse views surface row/plot labels normally.

### Known Issue — Dashboard Spinner Race *(v1.1 bug fix)*

On initial load, multiple async processes complete from different sources simultaneously — API responses, NgRx store hydration, and chart state updates. Without a short intentional bottleneck, a completion event is occasionally lost before the component is ready to receive it. The chart state update render is the most common casualty.

The fix requires either a **route-stable guard** or a **defer-until-stable initialization pattern** — the specific implementation approach is open pending Claude Code's assessment. The architectural requirement is clear: introduce a controlled synchronization point that ensures all async sources have settled before the dashboard renders.

### MVP Pages

| Page | Purpose |
|------|---------|
| Overview | At-a-glance dashboard — active alerts, current crop cycles, recent readings |
| Fields | Manage growing areas (open field / greenhouse), assign sensors |
| Crop Cycles | Start, monitor, and close crop cycles per field |
| Readings | Sensor reading history with anomaly status per growing area |
| Alerts | Active and resolved anomaly alerts with manual resolution |
| Yield Plans | AI-generated yield predictions per active crop cycle |
| Invoices | Review, send, and track harvest and transplant invoices |
| Customers | Manage harvest and transplant customer records |

---

## 7. Testing & Coverage

The backend test suite runs via pytest with coverage reporting. All service and API layers are covered. Remaining gaps are infrastructure-dependent and require integration-level setup to cover meaningfully.

### Current State

| Metric | Value |
|--------|-------|
| Total tests | 282 |
| Coverage | 87.76% |
| Coverage threshold | 50% (enforced via `--cov-fail-under=50`) |

```bash
cd backend
python -m pytest tests/ -v --cov=app --cov-report=term-missing --cov-fail-under=50
```

### Coverage Gaps

| Gap | Reason |
|-----|--------|
| `main.py` lifespan code | Requires full infrastructure startup to exercise meaningfully — not a unit test candidate |
| `agent/chat.py` streaming loop | Requires live Anthropic SDK connection and streaming infrastructure — integration-level coverage only |

Both gaps are documented and accepted. The 87.76% figure accurately represents the testable surface area of the application — the remaining 12.24% is infrastructure-dependent, not untested business logic.

### Philosophy

Coverage threshold is set at 50% as a floor, not a target. The actual coverage reflects that all service and API layers are tested. The agent and lifespan gaps are a known and accepted tradeoff between test suite practicality and infrastructure complexity.

---

## 8. Local Development & Deployment

Yearly Yields runs as three independent processes in local development — each in its own terminal. The startup order is not optional: PostgreSQL must be fully up before FastAPI starts or the database connection fails on lifespan initialization.

### Startup Order

**Terminal 1 — Database**
```bash
cd backend
docker compose up -d
```
PostgreSQL 16 + pgvector runs in Docker. Monitor and control via Docker Desktop if preferred. Must be running before any other process starts.

**Terminal 2 — Backend**
```bash
python -m uvicorn app.main:app --reload
# → http://127.0.0.1:8000
# → Swagger UI: http://127.0.0.1:8000/docs
```

**Terminal 3 — Frontend**
```bash
cd frontend/yearly-yields-ui
npm start
# → http://localhost:4200
```

### Environment Variables

All environment variables must be configured in `.env` before first startup — not just variables relevant to the immediate session. This prevents silent failures mid-session when a background job or agent call reaches a missing key.

| Variable | Purpose | Notes |
|----------|---------|-------|
| `DATABASE_URL` | PostgreSQL connection string | Required for all startup |
| `SECRET_KEY` | JWT signing secret | Required for all startup |
| `ANTHROPIC_API_KEY` | Claude SDK — anomaly agent + chat agent | Required for all startup |
| `SENDGRID_API_KEY` | Email alert fan-out | Required for all startup |
| `NOAA_CDO_TOKEN` | NOAA CDO historical backfill | Required before firing `POST /api/v1/admin/backfill` |
| `DATA_RETENTION_DAYS` | Nightly purge window | Default 3 years |
| `DAILY_RETENTION_DAYS` | Quarterly summarization window | Default 90 days |

> NWS api.weather.gov does not require a token — it is an open API polled on the 6-hour APScheduler job automatically.

### First-Time Setup

After Docker is up and migrations have run, initialize in order:

**1. Bootstrap the first owner account** *(no auth required — endpoint locks once an owner exists)*
```bash
POST /api/v1/admin/bootstrap
{
  "email": "you@example.com",
  "password": "...",
  "full_name": "Your Name",
  "role": "owner"
}
```

**2. Seed reference data** *(crops, customers, permissions — requires owner token)*
```bash
POST /api/v1/admin/seed
```

**3. Trigger NOAA CDO historical backfill** *(one-time, owner only — requires `NOAA_CDO_TOKEN` in `.env`)*
```bash
POST /api/v1/admin/backfill
```
This is a one-time initialization action. It populates the historical sensor context the agent draws on for similarity search and anomaly baselining. Fire once on install and never again under normal operations.

### Seed Data

Crop cycle seed data is backdated so today's date falls in the growing phase of each open field cycle — making the demo immediately meaningful without a time offset setting.

Seeded around **2026-04-17**. To recreate on a future date, recalculate `planted_at` so that `(today - planted_at).days` falls between `seeding_days` and `seeding_days + growing_days` for each crop. See `backend/app/core/crop_phases.py` for phase day constants.

### Account Recovery

No self-service password reset exists yet — that flow is added in v1.1. If locked out before v1.1 lands, reset directly via the database:

```bash
# 1. Generate bcrypt hash (run from backend/)
python -c "from passlib.context import CryptContext; print(CryptContext(schemes=['bcrypt']).hash('your-new-password'))"

# 2. Apply to the account
docker exec yearly_yields_db psql -U user -d yearly_yields -c \
  "UPDATE users SET hashed_password = '<paste hash here>' WHERE email = 'you@example.com';"
```

### Deployment

Yearly Yields is an on-prem / local install environment for v1.1. Cloud deployment is a future trajectory if the product gains traction. The current architecture is well-suited for on-prem — the NWS per-location rate limit and one-time NOAA CDO backfill pattern were both designed with single-install operation in mind.

---

## 9. Known Gaps & Roadmap

### Known Gaps — v1.1

These are documented limitations in the current architecture. None are functionally blocking — the system operates correctly within these constraints.

| Gap | Detail |
|-----|--------|
| RBAC middleware coverage | Access control is enforced at the route level via `Depends()` guards only. A route that omits its guard is unprotected. No middleware-level safety net exists yet. |
| Dashboard spinner race | On initial load, concurrent async completions from API, NgRx store, and chart state updates occasionally lose a completion event before the component is ready. Chart state update render is the most common casualty. Fix approach (route-stable guard vs defer-until-stable) is open pending Claude Code assessment. |
| Confidence calibration | The anomaly agent exhibits a pessimistic bias toward maintaining active alerts over resolving on insufficient evidence. Whether this is prompt-driven or emergent from Claude's base disposition is an open research question. The behavior aligns with agricultural safety goals and is accepted as a documented characteristic rather than a configured parameter. |
| NWS cloud-hosted throttle | NWS rate limits are per location. On-prem installs hold naturally at the 6-hour polling cadence. Cloud-hosted multi-tenant deployments will require per-client request throttling at the service layer. Not in scope until cloud hosting is pursued. |
| Annual roll-up | Deferred pending user feedback on year-over-year query patterns. Weekly summary granularity is preserved to support farmer-facing seasonal comparisons. Annual totals for UI bar charts are derived via aggregation query at render time — no destructive roll-up required. |
| Test coverage gaps | `main.py` lifespan code and `agent/chat.py` streaming loop require integration-level infrastructure to cover meaningfully. Accepted as a known and documented tradeoff. |

---

### Wanted Features — v1.2

These are targeted enhancements. None are functionally blocking current v1.1 features — the system is complete and operational without them.

**AI & Agent**
- **Confidence calibration** — Research and implement explicit confidence scoring in the ReAct loop to give the agent a configurable resolution threshold rather than relying on observed pessimistic bias.
- **pgvector embedding purge** — Remove orphaned voyage-3 embeddings from pgvector for sensor readings that have been deleted or rolled into weekly summaries, preventing the vector store from growing unboundedly. Analogous to the index housekeeping pattern in Cosmos DB.
- **AI-guided yield plan wizard** — Replace the static Generate Yield Plan form with a conversational wizard. The agent asks the farmer structured questions (growing area, current phase, historical yield, market demand) and synthesizes a recommended target yield with reasoning. Final decision stays with the owner or farmer.

**Data & Infrastructure**
- **RBAC middleware hardening** — Add a middleware-level safety net so unguarded routes are caught at the framework layer rather than relying solely on per-route `Depends()` guards.
- **Queue-backed worker** — Introduce a queue-backed worker pattern with a single topic for the quarterly summarization job, avoiding a second listener picking up the wrong message as background job complexity grows.
- **User-to-growing-area assignment** — Farmer-scoped user list views. Currently farmers see all users — scoping requires a join table linking users to specific growing areas they are assigned to work.
- **IoT reading source** — `sensor` covers real device POSTs today. When a pilot client deploys hardware, add a named `IoT` source tied to device identity and registration for audit and traceability.
- **SMS alert notifications** — Send a text message with a deep link to the alert detail when an anomaly is first detected, supplementing the existing SendGrid email fan-out.

**UI & Experience**
- **Dashboard spinner race fix** — Introduce a controlled synchronization point (route-stable guard or defer-until-stable initialization pattern) ensuring all async sources settle before the dashboard renders. *(Promote from v1.1 if not resolved.)*
- **Configurable crop phase day admin UI** — Seeding/growing/harvest day breakdowns and crop-specific sub-phase definitions are currently product-owned constants. Future feature allows per-farm overrides via settings.
- **Gantt-style crop cycle timeline** — Visual timeline per cycle showing all phases proportionally, derived from `planted_at` + per-phase day counts. Extend to overlay actual sensor anomaly events on the timeline for at-a-glance season health.

**Data Model**
- **Coordinate DMS auto-conversion** — Add support for degrees, minutes, and seconds (DMS) input with auto-conversion for farm GPS equipment that outputs DMS natively. *(Promote from v1.1 if not completed.)*
