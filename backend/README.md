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
- `RESEND_API_KEY` — from resend.com (use a placeholder for dev)

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

### 6. Start the dev server

```powershell
python -m uvicorn app.main:app --reload
```

API is available at: http://127.0.0.1:8000
Swagger UI: http://127.0.0.1:8000/docs

## Restarting the dev server

Once first-time setup is done, subsequent restarts only need the database up and the venv active.

### 1. Check the database is running

From the **project root**:

```powershell
docker compose ps
```

If `yearly_yields_db` isn't listed as `(healthy)`:

```powershell
docker compose up -d
```

### 2. Confirm the venv is active

Your prompt should already show `(.venv)`. If it doesn't:

```powershell
cd backend
.venv\Scripts\activate
```

To double-check `python` is resolving to the project venv and not a global install:

```powershell
Get-Command python
```

The `Source` path should point into `...\Yearly-Yields\backend\.venv\Scripts\python.exe`. If it points anywhere else (e.g. a Microsoft Store or global Python path), the venv isn't active — activate it before continuing.

### 3. Start the server

```powershell
python -m uvicorn app.main:app --reload
```

## Stopping the dev server

Press **Ctrl+C** in the terminal running uvicorn. This may take multiple attempts, since you have to hit the keystroke between polling calls.

## Overall workflow

The seasonal workflow from planting to invoice — Readings and anomaly detection run continuously in the background throughout the entire season, not just at the beginning or end.

```
Planting ──────────────────── Growing Season ──────────────────── Harvest
    │                                 │                               │
    ├─ Create Field               Readings arrive constantly      Log actual_yield
    ├─ Start Crop Cycle           (manual, NOAA, IoT)             Mark cycle harvested
    └─ Generate Yield Plan        AI checks each one              Invoice auto-generated
       (recommended plant qty,    Alerts raised if anomalous      Farmer reviews & sends
        confidence, reasoning)    Alerts auto-resolve after
                                  3 consecutive normal readings
                                  Farmer can resolve manually
```

**Key distinction:** Yield Plan is a one-time planning snapshot at planting time (or mid-season if conditions change significantly). Readings → Alerts is an ongoing background heartbeat for the entire life of the cycle. Invoice is a one-time wrap-up at harvest.

## Seeding reference data

After running migrations, seed the required reference data (customers, crops, permissions, role permissions) by calling the admin endpoint as an owner user:

```
POST /api/v1/admin/seed
Authorization: Bearer <owner_token>
```

This is idempotent — safe to call multiple times. Crops and customers must be seeded before crop cycles or invoices can be created.

## Yield planning

Yield plans are generated on demand by a Claude-powered ReAct agent. To request one:

```
POST /api/v1/yield-plans/
Authorization: Bearer <farmer_or_owner_token>

{
  "crop_cycle_id": "<uuid>",
  "target_yield": 7000.0
}
```

**Prerequisites:**
- The crop cycle must have status `active`
- The crop cycle must have a `crop_id` assigned (not a fallow cycle)
- The growing area must belong to the authenticated user

**What the agent does:**
1. Pulls recent sensor readings for the growing area (temperature/humidity trends)
2. Pulls historical harvested cycle yield data for the same area and crop (actual vs target yield)
3. Fetches regional weather context from NOAA
4. Returns a `recommended_plant_quantity` (seeds or transplants), a `confidence_level` (low/medium/high), and farmer-readable `reasoning`

The response is synchronous — the plan is returned directly in the POST response. Plans are also readable via `GET /api/v1/yield-plans/` and `GET /api/v1/yield-plans/{plan_id}`.

## Sensor reading ingestion and anomaly detection

Sensor readings are the heartbeat of the system. Every POST to `/api/v1/readings/` triggers a background ReAct agent run:

```
POST /api/v1/readings/
Authorization: Bearer <token>

{
  "growing_area_id": "<uuid>",
  "crop_cycle_id": "<uuid>",       // optional
  "temperature": 95.5,             // °F
  "humidity": 22.0,                // % (0–100)
  "reading_source": "manual",      // manual | nws | fiot | sensor
  "read_at": "2026-04-16T08:00:00Z"
}
```

The reading is saved immediately with `assessment_status: pending` and the response is returned. The agent then runs in the background:

1. **Historical context** — vector similarity search over 3 years of weekly summaries to establish a baseline for this area and crop
2. **Weather context** — NOAA regional weather to determine if a deviation is field-isolated or regionally explained
3. **Alert check** — looks for an existing active alert before deciding whether to create a new one
4. **Assessment** — marks the reading `normal` or `anomalous` and writes a farmer-readable summary

**Alert firing rules:**
- A new alert is created on the first anomalous reading with no existing active alert
- A repeat email is sent only after `ALERT_EMAIL_INTERVAL_HOURS` have passed since the last email (default 24h, configurable 4–72h in `.env`)
- An active alert is resolved automatically after 3 consecutive normal readings (`ALERT_RESOLUTION_THRESHOLD`, configurable 1–10)

### Sensor data sources

NWS is a nearby proxy, not a field-level source of truth. For open fields the gap is microclimate (elevation, drainage, wind exposure). For greenhouses the gap is the building envelope — fIoT modeling replaces or adjusts the outdoor conditions.

| Area type | Mode | Source of data |
|---|---|---|
| Open field | NWS poll | Nearby NWS station — best available proxy, not ground truth |
| Greenhouse (no `target_temp_f`) | Passive fIoT | NWS ambient + building offsets (`temp_offset_f`, `humidity_offset_pct`) |
| Greenhouse (`target_temp_f` set) | Active fIoT | HVAC setpoint ± Gaussian noise — NWS conditions irrelevant |

This is why readings carry a `reading_source` field and why anomaly detection uses phase-specific ideal ranges rather than raw NWS comparison. Anomalous readings are always evaluated against what that area's conditions *should* be, not what the outdoor weather *is*.

## Crop cycle state machine

Crop cycles move through a defined set of states. Invalid transitions are rejected with `422`.

```
active ──► harvested     (triggers draft harvest invoice — routes to default_harvest_customer)
active ──► transplanted  (triggers draft transplant invoice — routes to default_transplant_customer; greenhouse crops only)
active ──► abandoned     (terminal)
fallow ──► active        (auto-promotes planned_crop_id → crop_id; clears planned_crop_id)

harvested    — terminal
transplanted — terminal
abandoned    — terminal
```

**Fallow invariant:** a fallow cycle has `crop_id = null` and optionally a `planned_crop_id`. Transitioning `fallow → active` requires `planned_crop_id` to be set — it becomes the `crop_id` automatically and greenhouse compatibility is re-validated.

**Transplanted:** greenhouse crops (tomatoes, arugula lettuce) can be sold as seedlings at any point during the active growing phase. Transitioning to `transplanted` fires a draft invoice to the crop's `default_transplant_customer` (Prairie Start Nursery). Open field crops (corn, soybeans) cannot be transplanted — the transition returns `422`. Like `harvested`, `actual_yield` must be set before the invoice will generate.

State changes are applied via `PATCH /api/v1/crops/cycles/{cycle_id}`.

## Invoice lifecycle

Invoices are auto-generated when a crop cycle is marked `harvested`. The workflow:

1. `PATCH /crops/cycles/{id}` with `status: harvested` and `actual_yield` set
2. Service creates a `draft` invoice — snapshots the active `CropRate` and defaults `quantity` to `actual_yield`
3. Farmer reviews and adjusts quantity or notes via `PATCH /invoices/{id}`
4. Farmer advances the invoice through its own state machine:

```
draft ──► sent    (issued to customer)
draft ──► voided  (cancelled before sending)
sent  ──► paid    (payment received)
sent  ──► voided  (cancelled after sending)

paid   — terminal
voided — terminal
```

**Note:** An invoice will not be auto-generated if the cycle has no `actual_yield`, no active `CropRate`, or no `default_harvest_customer` on the crop. Check all three if an expected invoice is missing after harvest.

## Data gaps

The system tracks when a growing area stops receiving readings. Any area that hasn't had a reading in more than `GAP_THRESHOLD_DAYS` (default 7, configurable in `.env`) is considered a data gap.

```
GET /api/v1/data-gaps/
Authorization: Bearer <token>
```

Returns a list of areas with stale or missing readings. Greenhouse areas and areas without an NWS station assigned are excluded — only areas where data should be flowing are included.

To suppress a gap (e.g., the field is fallow and monitoring is intentionally paused):

```
POST /api/v1/data-gaps/{area_id}/acknowledge
Authorization: Bearer <token>
```

Returns `204`. The area is excluded from future gap reports for another `GAP_THRESHOLD_DAYS` window.

## Alert lifecycle

Alerts are created and resolved automatically by the anomaly detection agent, but can also be manually resolved by any authenticated user who owns the growing area:

```
PATCH /api/v1/alerts/{alert_id}
Authorization: Bearer <token>

{ "status": "resolved" }
```

Only `active → resolved` is supported via manual update. Resolved alerts are terminal — they cannot be reopened. To track a new anomaly on the same area, a new alert will be created by the agent on the next anomalous reading.

Filter active alerts only via `GET /api/v1/alerts/?active_only=true`.

## Role-based access control

| Permission | owner | farmer | hired_hand |
|---|---|---|---|
| Create / manage growing areas | ✓ | ✓ | — |
| View growing areas | ✓ | ✓ | ✓ |
| Create / update crop cycles | ✓ | ✓ | ✓ |
| View crops and crop cycles | ✓ | ✓ | — |
| Submit sensor readings | ✓ | ✓ | — |
| View sensor readings | ✓ | ✓ | — |
| View and manage alerts | ✓ | ✓ | — |
| Create yield plans | ✓ | ✓ | — |
| View yield plans | ✓ | ✓ | — |
| Create and view invoices | ✓ | ✓ | — |
| Manage invoice status | ✓ | — | — |
| View and manage customers | ✓ | ✓ | — |
| Manage users | ✓ | — | — |
| Admin / seed | ✓ | — | — |

Roles are assigned at user creation and enforced via JWT claims on every request. The `owner` role has a wildcard permission that bypasses all individual permission checks.

## Data retention

Two background jobs run automatically as asyncio tasks in the FastAPI lifespan — no scheduler or external trigger needed.

**Nightly purge** — runs every 24 hours on startup. Hard-deletes rows from `sensor_readings` where `read_at` is older than `DATA_RETENTION_DAYS` (default 1095 / 3 years). Logs the deleted row count.

**Quarterly summarization** — fires after the nightly purge on dates listed in `SUMMARIZATION_DATES` (default: `03-31`, `06-30`, `09-30`, `12-31`). Aggregates daily readings older than `DAILY_RETENTION_DAYS` (default 90) into `weekly_sensor_summaries` per growing area per week (Sunday–Saturday), then deletes the source rows. Wind direction is averaged using a circular mean to handle the 0/359° wraparound. Rows already summarized are skipped via `ON CONFLICT DO NOTHING`.

Wind direction is stored as degrees (`0.0–359.99`) in both tables. Use `app/core/wind.py` for conversion:
```python
from app.core.wind import degrees_to_cardinal, cardinal_to_degrees
degrees_to_cardinal(247.5)   # → "WSW"
cardinal_to_degrees("WSW")   # → 247.5
```

All thresholds are configurable in `.env`:
```
DATA_RETENTION_DAYS=1095
DAILY_RETENTION_DAYS=90
SUMMARIZATION_DATES=["03-31","06-30","09-30","12-31"]
```

## Running migrations after model changes

```powershell
python -m alembic revision --autogenerate -m "describe your change"
python -m alembic upgrade head
```
