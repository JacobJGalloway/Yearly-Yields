# Yearly Yields

Agricultural monitoring and yield prediction system for Mid-West farmers.

## What it does
- Ingests air temperature + humidity readings from IoT sensors (fields and greenhouses)
- Compares readings against 3-year rolling weekly historical data to detect anomalies
- Fires email alerts on first anomaly; daily until 3 consecutive clear readings
- Recommends fallow fields at year-start based on sensor history
- Predicts planting quantities needed to hit target yield given weather and risk factors

## Crops (initial)
| Type | Crops |
|---|---|
| Field (acres) | Corn, Soybeans |
| Greenhouse (sq ft) | Tomatoes, Peppers |

## Stack
| Layer | Technology |
|---|---|
| Backend | Python 3.12 + FastAPI |
| Database | PostgreSQL + pgvector |
| AI | Claude SDK (`claude-sonnet-4-6`), ReAct agentic loop |
| Auth | JWT + RBAC |
| Alerts | SendGrid (email) |
| Weather | NOAA API |
| Frontend | Angular v21 + Angular Material + NgRx |

## Structure
```
backend/    Python/FastAPI API
frontend/   Angular UI (run `ng new` — see frontend/README.md)
```

## Getting started

### Backend
```bash
cd backend
cp .env.example .env          # fill in your keys
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

### Frontend
See `frontend/README.md` for Angular setup instructions.
