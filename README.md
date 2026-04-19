<p align="center">
  <img src="frontend/src/assets/brand/Logo Work Default Mode.png" alt="Yearly Yields" width="480"/>
</p>

An agricultural monitoring and yield prediction system built for Mid-West farmers. Ingests IoT sensor readings from open fields and greenhouses, detects anomalies against rolling historical data using a ReAct agentic loop powered by Claude, fires email alerts, and supports yield planning and invoice tracking across crop cycles.

## What it does

- Ingests air temperature, humidity, and pH readings from IoT sensors across fields and greenhouses
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
| Frontend | Angular 21 + Angular Material 3 (green palette) + NgRx |

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

## Needed features
- NOAA CDO historical backfill — one-time seed of 3 years of weather history per NWS station. Requires `NOAA_CDO_TOKEN` in `.env` (free at ncei.noaa.gov/cdo-web/token); call `nws_service.backfill('KMOR'/'KMTO', start, end)` directly once the token is set.
- GrowingArea unique name constraint (v1.1) — enforce unique names per owner at the database and API layer. Currently handled by name-match deduplication in `seed_demo_farms.py`.

## Future Features
- Backfill anomaly averaging — when the NWS polling service catches up after downtime, average the backfilled observations over the gap window and run anomaly detection on the result. A confirmed anomaly in the average is a stronger signal than any single reading.
- Coordinate input format (v1.1) — Add Field currently requires decimal lat/long. Add support for degrees, minutes, and seconds (DMS) input with auto-conversion, as most farm GPS equipment outputs DMS format.
- User-to-growing-area assignment model — allows farmer-scoped user list views (currently farmers see all users; scoping requires a join table linking users to specific growing areas they are assigned to work).
- Configurable crop phase day admin UI — seeding/growing/harvest day breakdowns and crop-specific sub-phase definitions are currently product-owned constants; future feature allows per-farm overrides via settings.
- IoT reading source — `sensor` covers real device POSTs today. When a pilot client deploys hardware, add a named `IoT` source tied to device identity and registration for audit and traceability.
- SMS alert notifications — send a text message with a deep link to the alert detail when an anomaly is first detected, supplementing the existing SendGrid email fan-out.

