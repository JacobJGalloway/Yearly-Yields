<p align="center">
  <img src="frontend/src/assets/brand/Logo Work Default Mode.png" alt="Yearly Yields" width="480"/>
</p>

An agricultural monitoring and yield prediction system built for Mid-West farmers. Ingests IoT sensor readings from open fields and greenhouses, detects anomalies against rolling historical data using a ReAct agentic loop powered by Claude, fires email alerts, and supports yield planning and invoice tracking across crop cycles.

## What it does

- Ingests various types of sensor readings (i.e. air temperature, humidity, pH level, etc.) from IoT sensors across fields and greenhouses
  > *Note: Real IoT sensor data is not yet available. NWS CO-OP station observations (via api.weather.gov) substitute for open field readings. Greenhouse readings use fIoT simulation — NWS ambient data plus per-building temperature and humidity offsets — to approximate controlled growing environments.*
- Runs a ReAct agentic loop (Reason + Act) on every reading — pulling historical context via pgvector similarity search, querying live weather from NWS, and deciding whether to raise, update, or resolve alerts
- Fires email alerts on the first anomaly and every 24 hours until 3 consecutive normal readings resolve the alert
- Tracks crop cycles with greenhouse compatibility enforcement and auto-generates draft invoices on harvest
- Supports yield planning and fallow field recommendations based on sensor history
- Full JWT authentication with role-based access control (owner, farmer, hired hand)

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
| Alerts | SendGrid |
| Weather | NWS CO-OP (api.weather.gov) + NOAA CDO (historical backfill) |
| Frontend | Angular 21 + Angular Material 3 (teal/cyan palette, brand token system) + NgRx |

## Project structure

```
backend/    FastAPI API, ORM models, agent loop, services
frontend/   Angular UI (scaffold in progress)
docker/     PostgreSQL + pgvector container config
```

API: http://localhost:8000  
Swagger UI: http://localhost:8000/docs

## Running tests

```bash
cd backend
python -m pytest tests/ -v --cov=app --cov-report=term-missing --cov-fail-under=50
```

- **Current coverage:** 53 tests, 71% coverage (good) — auth, sensor readings, fields, customers, crop cycles, yield plans, and alert services covered. Invoice service, yield service, and vector service are the primary gaps, targeted as integration testing matures.

## First-time setup

After running migrations, create the first owner account (no auth required — locked out once an owner exists):

```bash
POST /api/v1/admin/bootstrap
{ "email": "you@example.com", "password": "...", "full_name": "Your Name", "role": "owner" }
```
Then seed reference data (crops, customers, permissions) via `POST /api/v1/admin/seed` using your owner token.

## Seed Data Notes

Crop cycle seed data is backdated so that today's date falls in the **growing phase** of each open field cycle, making the demo immediately meaningful without a time offset setting.

Seeded around **2026-04-17**. To recreate on a future date, recalculate `planted_at` so that `(today - planted_at).days` is between `seeding_days` and `seeding_days + growing_days` for each crop (see `backend/app/core/crop_phases.py` for phase day constants).

| Field | Crop | planted_at | Phase on seed date |
|-------|------|------------|-------------------|
| Corn Field | Field Corn | 2026-04-02 | Growing (day 15 of 120) |
| Soybean Field | Soybeans Group III | 2026-04-07 | Growing (day 10 of 112) |
| Morristown GH1 — Bay A | Tennessee Britches Tomato | 2026-01-20 | Growing (day 58 of 80) |
| Morristown GH1 — Bay B | Tennessee Britches Tomato | 2026-02-20 | Growing (day 27 of 80) |
| Morristown GH2 — Bay A | Tennessee Britches Tomato | 2026-01-15 | Growing (day 63 of 80) |
| Morristown GH2 — Bay B | Tennessee Britches Tomato | 2026-03-01 | Growing (day 18 of 80) |
| Morristown GH2 — Bay C | Arugula Lettuce | 2026-04-01 | Growing (day 3 of 11) |

## Data Retention

Sensor data is managed by two background jobs that start automatically with the server — no manual trigger required.

| Job | Schedule | What it does |
|-----|----------|--------------|
| Nightly purge | Every 24h | Hard-deletes `sensor_readings` older than `DATA_RETENTION_DAYS` (default 3 years) |
| Quarterly summarization | End of each quarter (Mar 31, Jun 30, Sep 30, Dec 31) | Aggregates daily readings older than `DAILY_RETENTION_DAYS` (default 90 days) into `weekly_sensor_summaries`, then deletes the source rows |

Weekly summaries store per-area averages for temperature, humidity, pH, wind speed, and wind direction (circular mean). All retention windows are configurable in `.env`. Year-end purge of weekly summaries is planned for v1.1.

## Future Features

### v1.1
- **NOAA CDO historical backfill (trigger)** — `nws_service.backfill()` is fully implemented but has no automatic trigger. Requires a free `NOAA_CDO_TOKEN` from [ncei.noaa.gov/cdo-web/token](https://www.ncei.noaa.gov/cdo-web/token) added to `.env`, plus a scheduler or one-time admin endpoint to invoke it per station. MVP gap is covered by synthetic sensor data (`seed_sensor_backfill.py`) — real CDO history is not loaded until this is wired up.
- **Local MCP server** — Expose the Yearly Yields database as MCP tools (`get_crop_ranges`, `get_phase_context`, `get_recent_readings`, `get_active_alert`) so the anomaly check and dashboard chat agents fetch data on demand rather than receiving full context in every API payload. Reduces token cost as fIoT reading volume grows.
- **Prompt caching** — Add `cache_control` to stable system prompt sections in `agent/loop.py` and `agent/chat.py` using the Anthropic SDK's native caching support. Independent of MCP — quick win that can land first.
- **Chat session memory** — Persist dashboard chat history between sessions via MCP file-based memory rather than re-sending the full sliding-window message history on each request.
- **Dashboard spinner race (bug fix)** — On initial load, the navigation redirect occasionally cancels the HTTP chain before data arrives; a click on any nav item or the chat input clears it. Fix requires a route-stable guard or defer-until-stable initialization pattern.
- **Material chips palette** — Swap the Material 3 tertiary palette from `mat.$azure-palette` to `mat.$amber-palette` so chips, FABs, and secondary action components render in Harvest Gold, completing the brand token system.
- **Data gap approval modal** — When the NWS backfill detects a gap larger than 7 days, surface a modal asking the farmer to approve or reject a historical fill. Currently the system fills silently up to 7 days and logs a warning beyond that.
- **Year-end weekly yield summary purge** — Aggregate `weekly_sensor_summaries` older than one year into annual summaries, then delete the weekly source rows. Completes the data retention pipeline (nightly purge → quarterly summarization → annual roll-up).
- **GrowingArea unique name constraint** — Enforce unique names per owner at the database and API layer (unique index + 422 on conflict). Currently handled by name-match deduplication in `seed_demo_farms.py`.
- **Coordinate input format** — Add Field currently requires decimal lat/long. Add support for degrees, minutes, and seconds (DMS) input with auto-conversion, as most farm GPS equipment outputs DMS format.
- **Backfill anomaly averaging** — When the NWS polling service catches up after downtime, average the backfilled observations over the gap window and run anomaly detection on the result. A confirmed anomaly in the average is a stronger signal than any single reading.

### v1.2
- **pgvector embedding purge** — Remove voyage-3 embeddings from `pgvector` for sensor readings that have been deleted or rolled into weekly summaries, preventing the vector store from growing unboundedly.
- **User-to-growing-area assignment model** — Allows farmer-scoped user list views (currently farmers see all users; scoping requires a join table linking users to specific growing areas they are assigned to work).
- **Configurable crop phase day admin UI** — Seeding/growing/harvest day breakdowns and crop-specific sub-phase definitions are currently product-owned constants; future feature allows per-farm overrides via settings.
- **IoT reading source** — `sensor` covers real device POSTs today. When a pilot client deploys hardware, add a named `IoT` source tied to device identity and registration for audit and traceability.
- **SMS alert notifications** — Send a text message with a deep link to the alert detail when an anomaly is first detected, supplementing the existing SendGrid email fan-out.

