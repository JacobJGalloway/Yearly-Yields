# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Stack

- **Backend:** Python 3.12, FastAPI, async SQLAlchemy 2.0 + asyncpg, PostgreSQL 16 + pgvector, Alembic, Anthropic SDK (Claude Sonnet 4.6)
- **Frontend:** Angular 21, Angular Material 3, NgRx, Vitest
- **Infrastructure:** Docker (PostgreSQL + pgvector), SendGrid (email), NOAA API (weather), voyage-3 (embeddings)

## Commands

### Backend (run from `backend/`)

```bash
docker compose up -d                         # Start PostgreSQL (required first)
python -m uvicorn app.main:app --reload      # Dev server → http://127.0.0.1:8000
python -m alembic upgrade head               # Apply migrations
python -m alembic revision --autogenerate -m "describe change"  # New migration

# Tests (separate yearly_yields_test DB required — create once via docker exec)
python -m pytest tests/ -v --cov=app --cov-report=term-missing
python -m pytest tests/test_api/test_alerts.py::test_create_alert -v
python -m pytest tests/ -k "alert" -v
```

### Frontend (run from `frontend/yearly-yields-ui/`)

```bash
npm start          # Dev server → http://localhost:4200 (proxies /api to :8000)
npm test           # Vitest
npm test -- --include="**/alert.service.spec.ts"  # Single test file
npm run build      # Production build
npx prettier --write src/   # Format
```

No backend linter is configured. Frontend uses Prettier only (100-char lines, single quotes).

## Architecture

### Backend layout

```
app/
  main.py                  # FastAPI app, CORS, lifespan
  config.py                # Settings (pydantic)
  dependencies.py          # get_current_user, require_role
  api/v1/                  # Endpoint modules (auth, crops, fields, readings, alerts, etc.)
  agent/
    loop.py                # ReAct anomaly-detection agent (MAX_ITERATIONS=10)
    tools.py               # Tool schemas (ANOMALY_CHECK_TOOLS, YIELD_PLAN_TOOLS)
    tool_handlers.py       # Tool execution dispatch
    prompts.py             # System prompts
  models/                  # SQLAlchemy models
  schemas/                 # Pydantic schemas
  services/                # Business logic (alert, invoice, vector, crop_cycle_transitions)
  core/
    crop_phases.py         # PhaseDays dataclass + CROP_PHASE_DEFAULTS per crop
    crop_ranges.py         # Ideal temp/humidity ranges per crop + phase
  db/migrations/           # Alembic migrations
```

### Frontend layout

```
src/app/
  app.routes.ts            # Lazy-loaded routes: /login, /dashboard + children
  app.config.ts            # NgRx, interceptor, router, HTTP client wired here
  core/
    guards/auth.guard.ts   # Checks selectIsAuthenticated
    interceptors/auth.interceptor.ts  # Injects Bearer token from NgRx store
    services/              # One service per domain (auth, crop, field, alert, etc.)
  store/auth/              # NgRx — auth is the only fully NgRx-managed domain
  features/                # Feature modules (auth, dashboard, fields, crops, readings, alerts, etc.)
```

NgRx is used **only** for auth and alerts. All other domains use service-level state.

### Key cross-cutting patterns

**Crop phase calculation** — Phases are not tracked state; they're derived at runtime from `(today - planted_at).days` against fixed `PhaseDays` day counts in `crop_phases.py`. The agent in `loop.py` (lines 53–69) resolves the current phase and injects phase-specific ideal ranges from `crop_ranges.py` into Claude's context.

**Sensor reading pipeline** — `POST /api/v1/readings/` stores the row immediately (status=`pending`) and fires a `BackgroundTask` → `run_anomaly_check()` in `agent/loop.py`. The ReAct loop calls up to 7 tools; `log_reading_assessment` is always the terminal tool. Vector similarity via pgvector (voyage-3 embeddings, 1536-dim) finds the 5 most agronomically similar historical weeks.

**Auth** — JWT access tokens (30 min) + refresh tokens (7 days). `dependencies.py::require_role()` is a factory that gates endpoints by role. Owner role bypasses all permission checks. **Token refresh is not yet wired in the Angular interceptor** — known MVP blocker.

**Crop cycle state machine** (`crop_cycle_transitions.py`):
```
active → {harvested, transplanted, abandoned}
fallow → active   (promotes planned_crop_id → crop_id)
harvested / transplanted / abandoned → terminal
```
Transitioning to `harvested` or `transplanted` auto-generates a draft invoice if `actual_yield` is set and a matching `CropRate` + customer exists.

**Invoice lifecycle** — `draft → {sent, voided}`, `sent → {paid, voided}`. `CropRate` is snapshotted at invoice creation (unit_price, unit immutable thereafter). Only quantity/notes are editable post-creation.

**Alert rules** — Alert created on first anomaly; repeat emails gated by `ALERT_EMAIL_INTERVAL_HOURS` (default 24h). Alert auto-resolves after `ALERT_RESOLUTION_THRESHOLD` consecutive normal readings (default 3). Both are env-configurable.

**RBAC** — Roles: `owner` (wildcard bypass), `farmer` (read/write crops/fields/readings/alerts/invoices/customers), `hired_hand` (read areas, write cycles only). Seeded via `Permission` + `RolePermission` tables at startup.

## Environment

Backend requires `.env` in `backend/` — copy from `.env.example`. Key vars: `DATABASE_URL`, `SECRET_KEY`, `ANTHROPIC_API_KEY`, `SENDGRID_API_KEY`, `NOAA_USER_AGENT`. Frontend reads `apiUrl: '/api/v1'` from `environments/environment.ts`; the dev proxy (`proxy.conf.json`) routes `/api` → `http://localhost:8000`.

## Test setup

Tests use a separate `yearly_yields_test` database. Create it once:
```bash
docker exec -it yearly_yields_db psql -U user -c "CREATE DATABASE yearly_yields_test;"
```
Each test runs inside a rolled-back transaction (outer connection-level savepoint in `conftest.py`). Current coverage: 53 tests, ~71% — gaps in invoice service, yield service, vector service.

## Known gaps / active TODOs

- Token refresh not implemented in Angular interceptor (`auth.interceptor.ts`)
- `reading_service.py`, `noaa_service.py`, `email_service.py` are stub implementations
- Crop sub-phases (display-only, crop-specific labels within the three main phases) — planned
- Dashboard nav branding (sidenav logo / header)
- Morristown TN greenhouse growing area setup + NWS station assignment
