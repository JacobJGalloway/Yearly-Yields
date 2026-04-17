<p align="center">
  <img src="frontend/src/assets/brand/Logo Work Name One Line Default Mode.png" alt="Yearly Yields" width="480"/>
</p>

# Yearly Yields

An agricultural monitoring and yield prediction system built for Mid-West farmers. Ingests IoT sensor readings from open fields and greenhouses, detects anomalies against rolling historical data using a ReAct agentic loop powered by Claude, fires email alerts, and supports yield planning and invoice tracking across crop cycles.

## What it does

- Ingests air temperature and humidity readings from IoT sensors across fields and greenhouses
- Runs a ReAct agentic loop (Reason + Act) on every reading — pulling historical context via pgvector similarity search, querying live weather from NOAA, and deciding whether to raise, update, or resolve alerts
- Fires email alerts on the first anomaly and every 24 hours until 3 consecutive normal readings resolve the alert
- Tracks crop cycles with greenhouse compatibility enforcement and auto-generates draft invoices on harvest
- Supports yield planning and fallow field recommendations based on sensor history
- Full JWT authentication with role-based access control (owner, farmer, hired hand)

## Crops (initial scope)

| Type | Crops |
|------|-------|
| Open field (acres) | Corn, Soybeans |
| DWC greenhouse (sq ft) | Tomatoes, Arugula |

## Tech stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.12 + FastAPI + SQLAlchemy 2.0 async |
| Database | PostgreSQL 16 + pgvector |
| AI | Anthropic Claude (`claude-sonnet-4-6`) + voyage-3 embeddings, ReAct loop |
| Auth | JWT (python-jose) + bcrypt + RBAC |
| Alerts | SendGrid |
| Weather | NOAA API |
| Frontend | Angular + Angular Material + NgRx |

## Project structure

```
backend/    FastAPI API, ORM models, agent loop, services
frontend/   Angular UI (scaffold in progress)
docker/     PostgreSQL + pgvector container config
```

## Backend — getting started

```bash
cd backend
cp .env.example .env          # fill in SECRET_KEY, ANTHROPIC_API_KEY, SENDGRID_API_KEY
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

API: http://127.0.0.1:8000  
Swagger UI: http://127.0.0.1:8000/docs

## Running tests

```bash
cd backend
python -m pytest tests/ -v --cov=app --cov-report=term-missing
```

53 tests across auth, sensor readings, fields, customers, crop cycles, yield plans, and alert services.

## Frontend

Angular 21 + Angular Material 3 (green palette) + NgRx. Login page, JWT auth flow, and dashboard shell with left-side navigation are live. See `frontend/README.md`.

## First-time setup

After running migrations, create the first owner account (no auth required — locked out once an owner exists):

```bash
POST /api/v1/admin/bootstrap
{ "email": "you@example.com", "password": "...", "full_name": "Your Name", "role": "owner" }
```

Then seed reference data (crops, customers, permissions) via `POST /api/v1/admin/seed` using your owner token.

## Future features

### Crop cycle phase timeline chart
Each crop stores `seeding_days`, `growing_days`, and `harvest_days` breakdowns (summing to `typical_cycle_days`). The current UI uses these to label the active phase of a cycle (Seeding / Growing / Harvesting). A future enhancement would render a visual Gantt-style timeline per cycle showing all three phases proportionally, derived from `planted_at` + the per-phase day counts. Could be extended to overlay actual sensor anomaly events on the timeline for at-a-glance season health.
