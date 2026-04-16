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
| AI | Anthropic Claude (`claude-haiku-4-5`) + voyage-3 embeddings, ReAct loop |
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

28 tests, 71% coverage.

## Frontend

Angular scaffold in progress. See `frontend/README.md`.
