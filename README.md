<p align="center">
  <img src="frontend/src/assets/brand/Logo Work Default Mode.png" alt="Yearly Yields" width="480"/>
</p>

An agricultural monitoring and yield prediction system built for Mid-West farmers. Ingests IoT sensor readings from open fields and greenhouses, detects anomalies against rolling historical data using a ReAct agentic loop powered by Claude, fires email alerts, and supports yield planning and invoice tracking across crop cycles.

## What it does

- Ingests air temperature and humidity readings from IoT sensors across fields and greenhouses
  > *Note: Real IoT sensor data is not yet available. NOAA weather station observations currently substitute for open field readings in development. Greenhouse readings require a sensor data generator service — NOAA ambient data is not a valid substitute for controlled growing environments (hydroponic/aeroponic). This service is the first planned future feature.*
- Runs a ReAct agentic loop (Reason + Act) on every reading — pulling historical context via pgvector similarity search, querying live weather from NOAA, and deciding whether to raise, update, or resolve alerts
- Fires email alerts on the first anomaly and every 24 hours until 3 consecutive normal readings resolve the alert
- Tracks crop cycles with greenhouse compatibility enforcement and auto-generates draft invoices on harvest
- Supports yield planning and fallow field recommendations based on sensor history
- Full JWT authentication with role-based access control (owner, farmer, hired hand)

## Growing Areas / Crops (initial scope)

| Type | Crops |
|------|-------|
| Open field (acres) | Corn, Soybeans |
| DWC greenhouse (sq ft) | Tomatoes, Arugula |

### Crop cycle phase timeline chart
Each crop stores `seeding_days`, `growing_days`, and `harvest_days` breakdowns (summing to `typical_cycle_days`). The current UI uses these to label the active phase of a cycle (Seeding / Growing / Harvesting). A future enhancement would render a visual Gantt-style timeline per cycle showing all three phases proportionally, derived from `planted_at` + the per-phase day counts. Could be extended to overlay actual sensor anomaly events on the timeline for at-a-glance season health.

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

53 tests, 71% coverage across auth, sensor readings, fields, customers, crop cycles, yield plans, and alert services. Invoice service, yield service, and vector service are the primary coverage gaps — targeted for improvement as integration testing matures.

| Layer | Technology |
|-------|------------|
| Backend | Python 3.12 + FastAPI + SQLAlchemy 2.0 async |
| Database | PostgreSQL 16 + pgvector |
| AI | Anthropic Claude (`claude-sonnet-4-6`) + voyage-3 embeddings, ReAct loop |
| Auth  | JWT (python-jose) + bcrypt + RBAC |
| Alerts | SendGrid |
| Weather | NOAA API |
| Frontend | Angular 21 + Angular Material 3 (green palette) + NgRx |

## Project structure

```
backend/    FastAPI API, ORM models, agent loop, services
frontend/   Angular UI (scaffold in progress)
docker/     PostgreSQL + pgvector container config
```

API: http://127.0.0.1:8000  
Swagger UI: http://127.0.0.1:8000/docs

## Running tests

```bash
cd backend
python -m pytest tests/ -v --cov=app --cov-report=term-missing
```
## First-time setup

After running migrations, create the first owner account (no auth required — locked out once an owner exists):

```bash
POST /api/v1/admin/bootstrap
{ "email": "you@example.com", "password": "...", "full_name": "Your Name", "role": "owner" }
```
Then seed reference data (crops, customers, permissions) via `POST /api/v1/admin/seed` using your owner token.

## Needed features
- Sensor data generator service to trigger a sensor readings process on a field/greenhouse for analysis on a configurable schedule (NOAA would be 1 hour interval and skip hours if configuration if value is higher than 1 [look at "range" and "date=today" examples], source could change from "manual" to "NOAA"). can query NOAA query for current station data to get property values as a current substitute. Will need to be able to "fake" the greenhouse effect on temperature and humidity by end of product as part of the process (can change source to "fIoT" to play with the acronym). This is due to lack of pilot clients and actual growing areas with IoT sensors to currently use.
- Coordinate input format (v1.1) — Add Field currently requires decimal lat/long. Add support for degrees, minutes, and seconds (DMS) input with auto-conversion, as most farm GPS equipment outputs DMS format.
- User-to-growing-area assignment model — allows farmer-scoped user list views (currently farmers see all users; scoping requires a join table linking users to specific growing areas they are assigned to work).
- Configurable crop phase day admin UI — seeding/growing/harvest day breakdowns are currently product-owned constants; future feature allows per-farm overrides via settings.

