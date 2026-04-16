# Yearly Yields — Backend

FastAPI backend for the Yearly Yields agricultural monitoring and yield prediction system.

## Requirements

- Python 3.12+
- Docker Desktop (for PostgreSQL + pgvector)

## First-time setup

### 1. Start the database

From the **project root** (`Yearly-Yields/`):

```powershell
docker compose up -d
```

Verify it is healthy:

```powershell
docker compose ps
```

`yearly_yields_db` should show status `(healthy)`.

### 2. Configure environment

From the `backend/` folder:

```powershell
cp .env.example .env
```

Fill in the required values in `.env`:
- `SECRET_KEY` — any long random string for dev
- `ANTHROPIC_API_KEY` — from platform.claude.com
- `SENDGRID_API_KEY` — use a placeholder for dev (`SG.placeholder`)

### 3. Create and activate the virtual environment

```powershell
python -m venv .venv
.venv\Scripts\activate
```

Your prompt should show `(.venv)` when active.

### 4. Install dependencies

```powershell
pip install -e ".[dev]"
```

### 5. Run database migrations

```powershell
python -m alembic upgrade head
```

## Starting the dev server

From `backend/` with the venv active:

```powershell
python -m uvicorn app.main:app --reload
```

API is available at: http://127.0.0.1:8000  
Swagger UI: http://127.0.0.1:8000/docs

## Stopping the dev server

Press **Ctrl+C** in the terminal running uvicorn.

## Subsequent startups

After first-time setup, you only need:

```powershell
# 1. Start the database (if not already running)
docker compose up -d       # run from project root

# 2. Activate venv and start the server (from backend/)
.venv\Scripts\activate
python -m uvicorn app.main:app --reload
```

## Running migrations after model changes

```powershell
python -m alembic revision --autogenerate -m "describe your change"
python -m alembic upgrade head
```
