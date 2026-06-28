<p align="center">
  <img src="frontend/src/assets/brand/Logo Work Default Mode.png" alt="Yearly Yields" width="480"/>
</p>

<p align="center"><strong>v1.2</strong></p>

An agricultural monitoring and yield prediction system built for Mid-West farmers. Ingests IoT sensor readings from open fields and greenhouses, detects anomalies against rolling historical data using a ReAct agentic loop powered by Claude, fires email alerts, and supports yield planning and invoice tracking across crop cycles.

## What it does

- Ingests various types of sensor readings (i.e. air temperature, humidity, pH level, etc.) from IoT sensors across fields and greenhouses
  > *Note: Real IoT sensor data is not yet available. NWS CO-OP station observations (via api.weather.gov) substitute for open field readings. Greenhouse readings use fIoT simulation — NWS ambient data plus per-building temperature and humidity offsets — to approximate controlled growing environments.*
- Runs a ReAct agentic loop (Reason + Act) on every reading — pulling historical context via pgvector similarity search, querying live weather from NWS, and deciding whether to raise, update, or resolve alerts
- Fires email alerts (via Resend) on the first anomaly and every 24 hours until 3 consecutive normal readings resolve the alert
- Tracks crop cycles with greenhouse compatibility enforcement, auto-generates draft invoices on harvest, and emails the PDF to the customer on send
- Guides yield planning through a conversational step-by-step wizard powered by a Claude ReAct agent
- Supports GrowingAreaPlot sub-area tracking — greenhouse rows and open-field trial plots with staggered crop cycles, plot-scoped alerts, and sentinel plot compatibility for NWS area-level readings
- Full JWT authentication with role-based access control (owner, farmer, hired hand)

## AI / RAG Architecture

Anomaly detection and yield reasoning are powered by a Retrieval-Augmented Generation (RAG) pipeline built on `pgvector`, feeding a ReAct (Reason + Act) agentic loop running on Claude.

**Retrieval layer**

- Every sensor reading is embedded using voyage-3 and stored alongside structured aggregates in `historical_summaries` — weekly rollups of temperature, humidity, and reading counts per growing area and crop.
- When a new reading arrives, the agent performs a similarity search against `historical_summaries` to retrieve the most relevant historical context for that growing area and crop — grounding the model's reasoning in actual seasonal patterns rather than generic thresholds.
- Retrieval is scoped at the plot level (see `GrowingAreaPlot`, v1.2) so that conditions in one greenhouse row don't pollute the historical context for another.

**Augmentation + reasoning loop**

- The ReAct loop combines three context sources per decision: the new sensor reading, retrieved historical summaries (RAG), and live weather data from NWS CO-OP / api.weather.gov.
- The agent reasons over this combined context to classify the reading as normal or anomalous, and decides whether to raise, update, or resolve an alert — all decisions are logged with the retrieved context that informed them.
- The same retrieval pipeline backs yield planning: historical summaries for a growing area's crop history are retrieved and synthesized into yield predictions and fallow-field recommendations.

**Lifecycle management**

- A quarterly summarization job aggregates raw sensor readings into `historical_summaries` rows and generates their embeddings, keeping the vector store proportional to the number of growing-area/crop/week combinations rather than raw reading volume.
- Embeddings are refreshed (not deleted) when underlying aggregates change, preserving long-term historical context for retrieval even after source readings are purged.

## Growing Areas / Crops (initial scope)

| Type | Crop | Variety / Notes |
|------|------|-----------------|
| Open field (acres) | Field Corn | Standard field corn — hard planting window April–early June (southern IL) |
| Open field (acres) | Soybeans | Group III (primary) / Group IV; double-crop variant when planted ≥ June 15 |
| DWC greenhouse (sq ft) | Tennessee Britches Tomato | Indeterminate heirloom; staggered quarter seeding (4 simultaneous cycles); typically harvest until first frost, then shutdown (one greenhouse will go for full vine life cycle) |
| DWC greenhouse (sq ft) | Arugula Lettuce | Full leaf (fall/winter/spring) → baby leaf (summer) based on planted_at month |

### Crop cycle phase timeline chart
Each crop stores `seeding_days`, `growing_days`, and `harvest_days` breakdowns (summing to `typical_cycle_days`), plus crop-specific sub-phases within each. The current UI labels the active main phase (Seeding / Growing / Harvesting) and the crop-specific sub-phase below it (e.g. Vegetative, Silking & Pollination, Grain Fill & Drying for corn). A future enhancement would render a visual Gantt-style timeline per cycle showing all phases proportionally, derived from `planted_at` + the per-phase day counts. Could be extended to overlay actual sensor anomaly events on the timeline for at-a-glance season health.

## Invoicing Process

When a crop cycle is marked as harvested, the system automatically generates a draft invoice against the growing area's default harvest customer — no manual entry needed. For greenhouse crops marked as transplanted (an early sale to another grower), a draft invoice is created against the transplant customer instead.

Draft invoices sit in review until an owner or farmer sends them. From there the lifecycle is straightforward: sent → paid, or voided if the deal falls through. Nothing is billed until you explicitly send it.

## MVP Pages

- **Overview** — at-a-glance dashboard: active alerts, current crop cycles, recent readings
- **Fields** — manage growing areas (open field / greenhouse), assign sensors
- **Crop Cycles** — start, monitor, and close out crop cycles per field
- **Readings** — sensor reading history with anomaly status per growing area
- **Alerts** — active and resolved anomaly alerts with manual resolution
- **Yield Plans** — AI-generated yield predictions per active crop cycle
- **Invoices** — review, send, and track harvest and transplant invoices
- **Customers** — manage harvest and transplant customer records

## Tech stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.12 + FastAPI + SQLAlchemy 2.0 async |
| Database | PostgreSQL 16 + pgvector |
| AI | Anthropic Claude (`claude-sonnet-4-6`) + voyage-3 embeddings, ReAct loop |
| Auth  | JWT (python-jose) + bcrypt + RBAC |
| Alerts & invoice email | Resend |
| Weather | NWS CO-OP (api.weather.gov) + NOAA CDO (historical backfill) |
| Frontend | Angular 21 + Angular Material 3 (teal/cyan palette, brand token system) + NgRx |

## Project structure

```
backend/    FastAPI API, ORM models, agent loop, services
frontend/   Angular UI (Angular 21 + Material 3 + NgRx)
docker/     PostgreSQL + pgvector container config
```

API: http://localhost:8000  
Swagger UI: http://localhost:8000/docs

## Running locally

**Prerequisites:** Docker Desktop must be running before step 1.

```bash
# 0. Copy and configure environment (first time only)
cp backend/.env.example backend/.env
# → Fill in DATABASE_URL, SECRET_KEY, ANTHROPIC_API_KEY
# → Fill in RESEND_API_KEY, EMAIL_FROM_ADDRESS (must be a Resend-verified domain or onboarding@resend.dev for dev)

# 1. Start PostgreSQL (required first)
cd backend
docker compose up -d

# 2. Apply database migrations (first time, or after pulling new migrations)
# (still in backend/)
python -m alembic upgrade head

# 3. Start the backend (still in backend/)
python -m uvicorn app.main:app --reload
# → http://127.0.0.1:8000  |  Swagger: http://127.0.0.1:8000/docs

# 4. Start the frontend (new terminal)
cd frontend/yearly-yields-ui
npm start
# → http://localhost:4200
```

## Running tests

```bash
cd backend
python -m pytest tests/ -v --cov=app --cov-report=term-missing --cov-fail-under=50
```

- **Current coverage:** 345 tests, ~84% — all service and API layers covered. Remaining gaps are excluded by design: `agent/chat.py` (streaming loop), `mcp/server.py` (subprocess), `main.py` (lifespan hooks).

## First-time setup

After running migrations, create the first owner account (no auth required — locked out once an owner exists):

```bash
POST /api/v1/admin/bootstrap
{ "email": "you@example.com", "password": "...", "full_name": "Your Name", "role": "owner" }
```
Then seed reference data (crops, customers, permissions) via `POST /api/v1/admin/seed` using your owner token.

## Seed Data Notes

Crop cycle seed data is backdated so that today's date falls in the **growing phase** of each open field cycle, making the demo immediately meaningful without a time offset setting.

The table below reflects the original static seed state as of **2026-04-17**. These dates become stale as time passes — they are kept here as a reference for the initial DB load only.

| Field | Crop | planted_at | Phase on seed date |
|-------|------|------------|-------------------|
| Corn Field | Field Corn | 2026-04-02 | Growing (day 15 of 120) |
| Soybean Field | Soybeans Group III | 2026-04-07 | Growing (day 10 of 112) |
| Morristown GH1 — Bay A | Tennessee Britches Tomato | 2026-01-20 | Growing (day 58 of 80) |
| Morristown GH1 — Bay B | Tennessee Britches Tomato | 2026-02-20 | Growing (day 27 of 80) |
| Morristown GH2 — Bay A | Tennessee Britches Tomato | 2026-01-15 | Growing (day 63 of 80) |
| Morristown GH2 — Bay B | Tennessee Britches Tomato | 2026-03-01 | Growing (day 18 of 80) |
| Morristown GH2 — Bay C | Arugula Lettuce | 2026-04-01 | Growing (day 3 of 11) |

**Use `POST /api/v1/admin/demo-reset` (owner token required) to rebuild cycles before any demo.** It recalculates all `planted_at` values relative to today — greenhouse plots always show varied active phases, open fields reflect the real calendar. The table above is a historical reference only.

When you go to setup a fresh or wiped database and need the seed data loaded back in,
run the following scripts in this order (all scripts are in backend folder) - 
1) seed_demo_farms.py
2) seed_historical_harvests.py
3) seed_morristown_harvests.py
4) seed_sensor_backfill.py
5) patch_target_yields.py
6) backfill_cdo.py

## Account recovery

A forgot password / reset flow is available on the login page (v1.1). If you are locked out and cannot receive the reset email, reset directly via the database:

```bash
# 1. Generate a bcrypt hash for your new password (run from backend/)
python -c "from passlib.context import CryptContext; print(CryptContext(schemes=['bcrypt']).hash('your-new-password'))"

# 2. Apply it to the account
docker exec yearly_yields_db psql -U user -d yearly_yields -c \
  "UPDATE users SET hashed_password = '<paste hash here>' WHERE email = 'you@example.com';"
```

## Data Retention

Sensor data is managed by two background jobs that start automatically with the server — no manual trigger required.

| Job | Schedule | What it does |
|-----|----------|--------------|
| Nightly purge | Every 24h | Hard-deletes `sensor_readings` older than `DATA_RETENTION_DAYS` (default 3 years) |
| Quarterly summarization | End of each quarter (Mar 31, Jun 30, Sep 30, Dec 31) | Aggregates daily readings older than `DAILY_RETENTION_DAYS` (default 90 days) into `weekly_sensor_summaries`, then deletes the source rows |

Weekly summaries store per-area averages for temperature, humidity, pH, wind speed, and wind direction (circular mean). All retention windows are configurable in `.env`. Year-end purge of weekly summaries is planned for v1.1.

## Future Features

### v1.4
Findings from the v1.3 accessibility audit (`docs/accessibility-audit-v1.3.md`) drive this sprint. Priority order matches the audit doc.

- **Harvest gold foreground policy** — `#C9A227` fails WCAG AA as a text/icon color on every surface (1.98:1 on field green, 2.07:1 on parchment, 2.42:1 on white). It passes as a *background* with black text (8.33:1). v1.4 enforces harvest gold as background-only: nav icons and text switch to `--yy-white-board` on the field green sidebar.
- **`aria-label` on all icon-only buttons** — all table action buttons and the toolbar logout button are missing accessible names; `matTooltip` is not a substitute for screen readers.
- **Logo image → semantic button** — the theme-picker trigger is a clickable `<img>`, which is not keyboard-focusable. Wrap in a `<button>` with `aria-label`.
- **Skip-navigation link** — add standard skip-nav at the top of the shell so keyboard users can bypass the sidenav on every page.
- **Mobile nav `aria-label`** — nav items hide their text label in mobile mode without a fallback accessible name on the `<a>` element.
- **Full browser re-audit with axe DevTools** after fixes to catch focus order, form label associations, dialog ARIA, and M3-generated tonal role contrast (not auditable from static CSS).

### Possible Future Features
- **Customer-scoped crop rates** — `CropRate` currently applies globally per crop. Needs a `customer_id` FK so pricing is per-customer per-crop (e.g. international buyers pay differently than local market customers). Required before unit price and total populate correctly on auto-generated invoices.
- **Crop rate seeding** — No active `CropRates` exist in the DB; `generate_draft` silently bails without them. Unit price is now directly editable on draft invoices as a workaround; seed rates per crop (paired with customer once customer-scoped rates land) to automate pricing on invoice creation.
- **Indiscriminate crop invoicing** — `log_harvest_pick` updates `last_harvest_date` only; it does not generate a draft invoice. Tomatoes (and eventually grapes) need a pick-triggered draft invoice rather than waiting for cycle close, since the vine cycle never terminates on a single harvest.
- **User-to-growing-area assignment model** — Allows farmer-scoped user list views (currently farmers see all users; scoping requires a join table linking users to specific growing areas they are assigned to work).
- **Configurable crop phase day admin UI** — Seeding/growing/harvest day breakdowns and crop-specific sub-phase definitions are currently product-owned constants; future feature allows per-farm overrides via settings.
- **IoT reading source** — `sensor` covers real device POSTs today. When a pilot client deploys hardware, add a named `IoT` source tied to device identity and registration for audit and traceability.
- **SMS alert notifications** — Send a text message with a deep link to the alert detail when an anomaly is first detected, supplementing the existing email delivery.
- **Sortable table columns** — Crop Cycles list (and other data tables) are currently unsorted; adding column-header sort would help operators quickly find cycles by phase, planted date, or area name.

