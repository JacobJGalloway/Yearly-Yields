# Yearly Yields — v1.2 Architecture

> **Release goal:** Demo-stable by end of month (3-week window).
> Two parallel tracks: **Invoicing** (complete the backend, wire to UI) and **GrowingAreaPlot** (schema migration + agent awareness). All other v1.2 items are lower priority and slotted only if time permits.

---

## Table of Contents

1. [Release Scope & Week Plan](#1-release-scope--week-plan)
2. [Track A — Invoicing](#2-track-a--invoicing)
3. [Track B — GrowingAreaPlot](#3-track-b--growingareatplot)
4. [Shared Infrastructure Changes](#4-shared-infrastructure-changes)
5. [Demo Reset](#5-demo-reset)
6. [Deferred v1.2 Items](#6-deferred-v12-items)
7. [Definition of Demo-Stable](#7-definition-of-demo-stable)

---

## 1. Release Scope & Week Plan

### Tracks

| Track | Owner focus | Goal |
|---|---|---|
| **A — Invoicing** | Backend wiring | Draft auto-generation on harvest, configurable default customer, PDF on-demand, status lifecycle |
| **B — GrowingAreaPlot** | Schema migration | Plot layer between `GrowingArea` and `CropCycle`, greenhouse row scheduling, NWS reading scope, agent tool updates |

### Three-Week Schedule

**Week 1 — Foundation**

- [ ] Design and migrate `growing_area_plots` table (Track B)
- [ ] Backfill `plot_id = 0` on all existing open-field `CropCycle` rows
- [ ] Introduce `InvoiceConfig` model and seed default harvest customer per growing area (Track A)
- [ ] Backend: `POST /api/v1/invoices` — auto-generate draft on crop cycle harvest event
- [ ] Backend: invoice status machine (`draft → sent → paid | voided`)

**Week 2 — Agent Awareness & Invoice Completion**

- [ ] Make all ReAct agent tools plot-aware (`plot_id` in tool signatures and vector search)
- [ ] NWS readings remain at `GrowingArea` level — propagate to plot readings via join (no re-ingestion)
- [ ] Greenhouse row scheduling logic (stagger rules, weekday pairs)
- [ ] Backend: `GET /api/v1/invoices/{id}/pdf` — on-demand PDF generation from invoice data
- [ ] Wire invoice UI to real backend endpoints (replace mock/static display)

**Week 3 — Stabilization & Demo Prep**

- [ ] pgvector embedding purge for deleted/summarized sensor readings
- [ ] End-to-end demo walkthrough: harvest a crop cycle → draft invoice → generate PDF → mark sent
- [ ] End-to-end demo walkthrough: greenhouse row stagger → anomaly on plot → alert fires
- [ ] Seed data refresh (recalculate `planted_at` for current date if needed)
- [ ] Fix any regressions in existing 338-test suite; maintain ≥85% coverage

---

## 2. Track A — Invoicing

### Current State

The invoice UI pages exist (list, detail, status display). The backend has **no** invoice records, no auto-generation trigger, no default customer assignment, and no PDF endpoint.

### 2.1 New Models

#### `InvoiceConfig`

Stores the configurable default customer assignments per growing area. One row per `GrowingArea`. Avoids hardcoding customer IDs in business logic.

```sql
CREATE TABLE invoice_configs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    growing_area_id UUID NOT NULL REFERENCES growing_areas(id) ON DELETE CASCADE,
    harvest_customer_id   UUID REFERENCES customers(id),  -- default for normal harvests
    transplant_customer_id UUID REFERENCES customers(id), -- default for transplant sales
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (growing_area_id)
);
```

**Notes:**
- Both customer fields are nullable. If no default is configured, invoice is created without a customer and flagged `needs_customer_assignment`.
- Seeded via `POST /api/v1/admin/seed` alongside existing reference data.
- Owners and farmers can update via `PATCH /api/v1/invoice-configs/{growing_area_id}`.

#### `Invoice` (new table)

```sql
CREATE TABLE invoices (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    crop_cycle_id   UUID NOT NULL REFERENCES crop_cycles(id),
    customer_id     UUID REFERENCES customers(id),
    invoice_type    VARCHAR(20) NOT NULL CHECK (invoice_type IN ('harvest', 'transplant')),
    status          VARCHAR(20) NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft', 'sent', 'paid', 'voided')),
    line_items      JSONB NOT NULL DEFAULT '[]',
    total_amount    NUMERIC(12, 2),
    notes           TEXT,
    sent_at         TIMESTAMPTZ,
    paid_at         TIMESTAMPTZ,
    voided_at       TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_invoices_crop_cycle ON invoices(crop_cycle_id);
CREATE INDEX idx_invoices_status ON invoices(status);
CREATE INDEX idx_invoices_customer ON invoices(customer_id);
```

**`line_items` JSONB shape (per item):**

```json
{
  "description": "Tennessee Britches Tomato — GH1 Bay A harvest",
  "quantity": 142.5,
  "unit": "lbs",
  "unit_price": null,
  "amount": null
}
```

Unit price and amount are nullable at draft time — owner fills in before sending.

### 2.2 Status Machine

```
draft ──► sent ──► paid
  │         │
  └─────────┴──► voided
```

Allowed transitions (enforced in service layer, not just API):

| From | To | Who |
|---|---|---|
| `draft` | `sent` | owner, farmer |
| `draft` | `voided` | owner, farmer |
| `sent` | `paid` | owner, farmer |
| `sent` | `voided` | owner |
| `paid` | — | no transitions (terminal) |
| `voided` | — | no transitions (terminal) |

Invalid transitions raise `HTTP 409 Conflict` with a descriptive message.

### 2.3 Auto-Generation Trigger

When a `CropCycle` status transitions to `harvested` (existing harvest endpoint), the service layer calls `InvoiceService.generate_draft()`:

```python
async def generate_draft(crop_cycle: CropCycle, db: AsyncSession) -> Invoice:
    config = await get_invoice_config(crop_cycle.growing_area_id, db)

    invoice_type = "transplant" if crop_cycle.is_transplant else "harvest"
    customer_id = (
        config.transplant_customer_id if invoice_type == "transplant"
        else config.harvest_customer_id
    ) if config else None

    line_items = build_line_items(crop_cycle)  # derives from crop type + yield data

    invoice = Invoice(
        crop_cycle_id=crop_cycle.id,
        customer_id=customer_id,
        invoice_type=invoice_type,
        status="draft",
        line_items=line_items,
    )
    db.add(invoice)
    await db.commit()
    return invoice
```

The harvest endpoint returns the created invoice ID in its response so the UI can immediately navigate to the draft.

### 2.4 PDF Generation

PDF is generated on-demand from the invoice record — no stored PDF file.

**Endpoint:** `GET /api/v1/invoices/{id}/pdf`
**Auth:** owner, farmer (same RBAC as invoice read)
**Response:** `Content-Type: application/pdf`, `Content-Disposition: attachment; filename="invoice-{id}.pdf"`

**Library:** `weasyprint` (pure Python, no headless browser dependency).

**Template approach:** Jinja2 HTML template rendered to PDF. Template lives at `backend/app/templates/invoice.html`. Fields:

- Farm name, growing area, crop cycle date range
- Customer name and address (from `customers` record)
- Line items table (description, quantity, unit, unit price, total)
- Invoice status, sent date, notes
- Yearly Yields branding (teal/cyan palette, consistent with Material 3 theme)

The Angular UI calls this endpoint and triggers a browser download — no iframe preview needed for demo-stable.

### 2.5 New API Endpoints

| Method | Path | Description | Auth |
|---|---|---|---|
| `GET` | `/api/v1/invoices` | List invoices (filterable by status, customer, growing area) | owner, farmer |
| `GET` | `/api/v1/invoices/{id}` | Invoice detail | owner, farmer |
| `PATCH` | `/api/v1/invoices/{id}` | Update draft (customer, line items, notes) | owner, farmer |
| `POST` | `/api/v1/invoices/{id}/send` | Transition draft → sent | owner, farmer |
| `POST` | `/api/v1/invoices/{id}/pay` | Transition sent → paid | owner, farmer |
| `POST` | `/api/v1/invoices/{id}/void` | Void invoice | owner (sent), owner/farmer (draft) |
| `GET` | `/api/v1/invoices/{id}/pdf` | On-demand PDF download | owner, farmer |
| `GET` | `/api/v1/invoice-configs/{growing_area_id}` | Get default customer config | owner, farmer |
| `PATCH` | `/api/v1/invoice-configs/{growing_area_id}` | Update default customers | owner, farmer |

Auto-generation is **not** a direct API endpoint — it fires internally on harvest. Hired hands have read-only access to invoices (no create, send, or void).

---

## 3. Track B — GrowingAreaPlot

### 3.1 Overview

`GrowingAreaPlot` sits between `GrowingArea` and `CropCycle`. It models a named subdivision of a growing area — a greenhouse bay row or an open-field trial plot.

```
GrowingArea (1)
    └── GrowingAreaPlot (many)
            └── CropCycle (many)
            └── SensorReading (many)   ← moves from GrowingArea level
            └── Alert (many)           ← moves from GrowingArea level
```

NWS weather readings remain at the `GrowingArea` level (one station per area). Everything agronomic moves to plot level.

### 3.2 Schema

#### `growing_area_plots`

```sql
CREATE TABLE growing_area_plots (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    growing_area_id UUID NOT NULL REFERENCES growing_areas(id) ON DELETE CASCADE,
    plot_index      INTEGER NOT NULL,      -- 0 for open field (singleton); 1-N for greenhouse rows
    name            VARCHAR(100),          -- e.g. "Row 1", "Bay A - Row 2", null for open field
    area_sqft       NUMERIC(10, 2),        -- for greenhouse rows; null for open field
    harvest_weekdays INTEGER[],            -- e.g. [1,2] = Mon/Tue; null for open field
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (growing_area_id, plot_index)
);

CREATE INDEX idx_plots_growing_area ON growing_area_plots(growing_area_id);
```

**`harvest_weekdays`:** ISO weekday integers (1=Monday … 7=Sunday). A row with `[1, 2]` is scheduled for Monday/Tuesday harvests. Null means no weekday constraint (open field or non-staggered greenhouse).

#### Migration of existing tables

`crop_cycles`, `sensor_readings`, and `alerts` each get a `plot_id` column added via Alembic migration:

```sql
-- crop_cycles
ALTER TABLE crop_cycles ADD COLUMN plot_id UUID REFERENCES growing_area_plots(id);

-- sensor_readings
ALTER TABLE sensor_readings ADD COLUMN plot_id UUID REFERENCES growing_area_plots(id);

-- alerts
ALTER TABLE alerts ADD COLUMN plot_id UUID REFERENCES growing_area_plots(id);
```

**Backfill strategy (run in migration, not application code):**

1. For every existing `GrowingArea`, insert one `GrowingAreaPlot` row with `plot_index = 0`, `name = null`, `harvest_weekdays = null`.
2. Update all `crop_cycles`, `sensor_readings`, and `alerts` for that area to point to the new `plot_id`.
3. After backfill, add `NOT NULL` constraint to `plot_id` on all three tables (single migration, run in one transaction).

```sql
-- Step 1: create singleton plots
INSERT INTO growing_area_plots (growing_area_id, plot_index)
SELECT id, 0 FROM growing_areas;

-- Step 2: backfill crop_cycles
UPDATE crop_cycles cc
SET plot_id = gap.id
FROM growing_area_plots gap
WHERE gap.growing_area_id = cc.growing_area_id
  AND gap.plot_index = 0;

-- Step 3: backfill sensor_readings
UPDATE sensor_readings sr
SET plot_id = gap.id
FROM growing_area_plots gap
WHERE gap.growing_area_id = sr.growing_area_id
  AND gap.plot_index = 0;

-- Step 4: backfill alerts
UPDATE alerts al
SET plot_id = gap.id
FROM growing_area_plots gap
WHERE gap.growing_area_id = al.growing_area_id
  AND gap.plot_index = 0;

-- Step 5: enforce NOT NULL
ALTER TABLE crop_cycles ALTER COLUMN plot_id SET NOT NULL;
ALTER TABLE sensor_readings ALTER COLUMN plot_id SET NOT NULL;
ALTER TABLE alerts ALTER COLUMN plot_id SET NOT NULL;
```

After migration, `growing_area_id` on `crop_cycles`, `sensor_readings`, and `alerts` becomes redundant (reachable via `plot → growing_area`). Leave it in place for v1.2 to avoid cascading API changes — mark as deprecated in schema comments and remove in v1.3.

### 3.3 Greenhouse Row Scheduling

#### Stagger model

Each DWC greenhouse bay is divided into rows. Rows are harvested on a fixed weekday pair so labor and logistics can be planned. The stagger is configured at the `GrowingAreaPlot` level via `harvest_weekdays`.

**Example — GH1 with 3 rows:**

| Row | `plot_index` | `harvest_weekdays` | Schedule |
|---|---|---|---|
| Row 1 | 1 | `[1, 2]` | Mon / Tue |
| Row 2 | 2 | `[3, 4]` | Wed / Thu |
| Row 3 | 3 | `[5]` | Fri |

Stagger is purely metadata for planning — it does not auto-create or close crop cycles. The farmer or owner acts on it. A future enhancement could surface "rows due for harvest this week" on the Overview dashboard.

#### Simultaneous crop cycles per greenhouse

Tennessee Britches Tomato uses a quarter-seeding strategy: up to 4 active cycles across rows at any time, offset by approximately the growing phase duration divided by 4. The `GrowingAreaPlot` layer makes this explicit — each row has its own `CropCycle` records with independent `planted_at` values.

Arugula rotates fully (one cycle per row, then replant). Row `harvest_weekdays` guides when within a week the farmer checks for harvest readiness.

**Greenhouse compatibility enforcement** (existing logic, now applied at plot level): when creating a new `CropCycle`, validate that the crop is compatible with the `GrowingArea.area_type` of the plot's parent area. The plot adds no new compatibility rules — enforcement stays at area type.

#### Crop cycle assignment rules

| Area type | Plots | How crop cycles are assigned |
|---|---|---|
| Open field | 1 plot (`plot_index = 0`) | One active cycle at a time per area (existing behavior unchanged) |
| DWC greenhouse | N plots (1 per row) | One active cycle per plot at a time; multiple rows = multiple simultaneous cycles |

When a farmer starts a new crop cycle via the UI, they now select both the growing area and the plot (row). For open-field areas, the plot selector is hidden and `plot_index = 0` is used automatically.

### 3.4 NWS Readings — Area vs. Plot Level

NWS CO-OP station data is ingested at the `GrowingArea` level. This does not change in v1.2.

**Why:** NWS stations map to a geographic location, not a row or sub-plot. All plots within a greenhouse share the same ambient outdoor readings; the per-building offsets (fIoT simulation) also apply at the area level.

**How plot-level sensor readings work:**

- NWS ingestion writes a `sensor_reading` row with `plot_id` set to the area's sentinel plot (`plot_index = 0`) for open fields.
- For greenhouses, the ingestion service fans out: one NWS-derived `sensor_reading` per active plot in the greenhouse, applying the greenhouse's temperature and humidity offsets uniformly across all rows.
- Real IoT device readings (future) will post directly to a specific `plot_id`.

```
NWS ingest job
    │
    ├── open field area ──► write 1 reading (plot_index=0)
    │
    └── greenhouse area ──► for each active plot:
                                write 1 reading with greenhouse offsets applied
```

This fan-out means the anomaly detection ReAct loop runs per-plot, which is the correct granularity — a humidity anomaly in Row 2 should not suppress alerts in Row 1.

### 3.5 Agent Tool Updates

All ReAct loop tools that currently accept `growing_area_id` get a `plot_id` parameter added. `growing_area_id` is retained and becomes **required** on every tool that accepts `plot_id` — the resolver always needs it to validate ownership and fall back to `plot_index = 0` when `plot_id` is omitted.

**`plot_id` is optional in all tool signatures. `growing_area_id` is required in all tool signatures.** Claude Code must implement both parameters on every affected tool — omitting `growing_area_id` from any tool signature will break the resolver at call sites where `plot_id` is not provided.

**Affected tools:**

| Tool | `growing_area_id` | `plot_id` | Notes |
|---|---|---|---|
| `get_sensor_history` | required | optional | Filter readings by resolved plot |
| `get_active_alerts` | required | optional | Filter alerts by resolved plot |
| `create_alert` | required | optional | Store resolved `plot_id` on alert record |
| `resolve_alert` | — | — | No new params; alert already carries `plot_id` |
| `get_yield_plan` | required | optional | Yield plans scoped to resolved plot cycle |
| `get_crop_cycle` | required | optional | Return cycle for resolved plot |

**pgvector similarity search:** The vector store query for historical context currently filters by `growing_area_id`. Update the metadata filter to include `plot_id` when provided so retrieved embeddings are plot-scoped. This prevents GH1 Row 1 history from polluting GH1 Row 2 anomaly reasoning.

### 3.6 `plot_id` Resolution & Error Handling Contract

`plot_id` is **NOT NULL** in the database on all three migrated tables. Null is never a valid stored value. The convention that "no plot specified means plot_index 0" is enforced exclusively at the API and service layer boundary — it must never leak into query logic or the agent loop.

#### Resolution rule

Any service or API endpoint that accepts an optional `plot_id` (or no `plot_id` at all) must resolve it to a concrete UUID before performing any DB write or read. The canonical resolver:

```python
async def resolve_plot_id(
    growing_area_id: UUID,
    plot_id: UUID | None,
    db: AsyncSession,
) -> UUID:
    """
    If plot_id is provided, validate it belongs to the growing area and return it.
    If plot_id is None, resolve to the plot_index=0 row for the area.
    Raises HTTP 404 if the area has no plots (should never happen post-migration).
    Raises HTTP 422 if the provided plot_id does not belong to the given area.
    """
    if plot_id is not None:
        plot = await db.get(GrowingAreaPlot, plot_id)
        if plot is None or plot.growing_area_id != growing_area_id:
            raise HTTPException(
                status_code=422,
                detail=f"plot_id {plot_id} does not belong to growing_area {growing_area_id}."
            )
        return plot.id

    # Default: resolve to plot_index=0
    result = await db.execute(
        select(GrowingAreaPlot.id)
        .where(GrowingAreaPlot.growing_area_id == growing_area_id)
        .where(GrowingAreaPlot.plot_index == 0)
    )
    default_plot_id = result.scalar_one_or_none()
    if default_plot_id is None:
        raise HTTPException(
            status_code=404,
            detail=f"No default plot (plot_index=0) found for growing_area {growing_area_id}. "
                   "This indicates a migration integrity failure."
        )
    return default_plot_id
```

#### Where this must be called

Every entry point that writes or queries plot-scoped data must call `resolve_plot_id` before proceeding:

| Entry point | Notes |
|---|---|
| `POST /api/v1/crop-cycles` | Resolve before creating cycle |
| `POST /api/v1/sensor-readings` (ingest) | Resolve per-plot during NWS fan-out |
| `POST /api/v1/alerts` | Resolve before creating alert |
| All ReAct agent tools with `plot_id` param | Resolve at tool entry, not inside query |
| `InvoiceService.generate_draft()` | Resolves via the crop cycle's `plot_id` (already set) |

#### What must never happen

- A `None` check on `plot_id` inside a SQLAlchemy query (`WHERE plot_id IS NULL`) — this would silently return no rows rather than raising an error.
- Defaulting to `plot_index=0` inside a query filter instead of the resolver — splits the convention across multiple code paths.
- Passing `plot_id=None` to the agent loop — the loop must always receive a resolved UUID; resolution happens in the ingest/dispatch layer before the loop is invoked.

#### Test requirement

Each new endpoint and agent tool must include a test case for the unresolved (no `plot_id` provided) path asserting it returns data scoped to `plot_index=0`, not an error and not unscoped data. Add these to the existing pytest suite alongside the happy-path tests.

---

## 4. Shared Infrastructure Changes

### pgvector Embedding Purge

Sensor readings deleted by the nightly purge job or rolled into weekly summaries leave orphaned embeddings in pgvector. Add a cleanup step to the existing background jobs:

**Nightly purge job addition:**

```python
async def purge_orphaned_embeddings(db: AsyncSession):
    """Delete embeddings whose source sensor_reading no longer exists."""
    await db.execute(text("""
        DELETE FROM sensor_embeddings se
        WHERE NOT EXISTS (
            SELECT 1 FROM sensor_readings sr WHERE sr.id = se.reading_id
        )
    """))
    await db.commit()
```

Run after the existing hard-delete step. No new table — assumes embeddings table has a `reading_id` FK column (add if not present via migration).

### Alembic Migration Order

Migrations must run in this order for v1.2:

1. `add_growing_area_plots_table` — creates the plot table
2. `add_plot_id_to_crop_cycles_sensor_readings_alerts` — adds nullable `plot_id` columns
3. `backfill_plot_id_all_tables` — inserts singleton `plot_index=0` rows for every `GrowingArea`, then backfills `plot_id` on **all three** tables: `crop_cycles`, `sensor_readings`, and `alerts`. Must not be scoped to open field only.
4. `enforce_plot_id_not_null` — adds NOT NULL constraint after backfill
5. `add_invoice_configs_table` — creates `InvoiceConfig`
6. `add_invoices_table` — creates `Invoice`
7. `add_reading_id_to_sensor_embeddings` — adds FK if not present (for purge job)

Run all in sequence: `python -m alembic upgrade head`

---

## 5. Demo Reset

### Overview

A date-aware demo reset endpoint that wipes all crop cycle data and rebuilds it so that open field cycles always land in the growing phase relative to today, and greenhouse rows are distributed across all crop phases to tell a complete story in every demo. Eliminates manual seed data recalculation between demos.

**Phase calculation logic** is drawn from Claude Code's existing memory of `backend/app/core/crop_phases.py` constants — do not redefine phase day values in this section.

### Endpoint

```
POST /api/v1/admin/demo-reset
Authorization: owner token required
```

Returns a summary of what was created (area name, crop, phase, `planted_at`) so the caller can verify the reset landed correctly before a demo.

### Behavior

**Wipe scope — the following are deleted before rebuild (in dependency order):**

1. `sensor_embeddings` (pgvector)
2. `sensor_readings`
3. `alerts`
4. `invoices`
5. `crop_cycles`
6. `growing_area_plots` (non-singleton rows only — singleton `plot_index=0` rows are retained to preserve area structure)

Farm, growing area, customer, user, and `InvoiceConfig` records are **not** touched.

**Rebuild — open fields:**

For each open field growing area, back-calculate `planted_at` so that `(today - planted_at).days` falls in the middle of the growing phase:

```python
planted_at = today - timedelta(days=seeding_days + (growing_days // 2))
```

This guarantees the cycle is visibly mid-season on demo day regardless of when the reset runs.

**Rebuild — greenhouses:**

Greenhouse rows are distributed across phases so the demo shows the full crop lifecycle simultaneously. For a 4-row Tennessee Britches Tomato setup the target distribution is:

| Row | Target phase | `planted_at` offset from today |
|---|---|---|
| Row 1 | Harvest (early) | `seeding_days + growing_days + 2` days ago |
| Row 2 | Growing (late) | `seeding_days + (growing_days * 3 // 4)` days ago |
| Row 3 | Growing (early) | `seeding_days + (growing_days // 4)` days ago |
| Row 4 | Seeding | `seeding_days // 2` days ago |

Arugula (single-row, fast cycle) is placed in late growing phase so harvest readiness is imminent but not yet triggered.

At least one greenhouse row must resolve to harvest phase — the endpoint must validate this after calculating offsets and raise `HTTP 500` with a descriptive error if the distribution logic produces no harvest row (indicates a phase constant change that broke the offset math).

**pgvector index reset:**

Deleting rows from `sensor_embeddings` removes the source data but does not reset the pgvector index state. Stale index entries will cause dashboard charts and the agent similarity search to query against ghost embeddings, producing garbage results. The wipe step must therefore explicitly reset the index before the table delete:

```python
await db.execute(text("SELECT truncate_tsvector_cache()"))  # if applicable
await db.execute(text("DROP INDEX IF EXISTS sensor_embeddings_embedding_idx"))
await db.execute(text("DELETE FROM sensor_embeddings"))
await db.execute(text("""
    CREATE INDEX sensor_embeddings_embedding_idx
    ON sensor_embeddings
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100)
"""))
```

This sequence — drop index, delete rows, recreate index — guarantees the index is clean before the backfill writes new embeddings into it. Claude Code must implement the wipe in this order, not as a simple `DELETE FROM sensor_embeddings`.

**pgvector backfill:**

After the index reset and crop cycle / sensor reading rebuild, run the embedding backfill inline before returning the response. The backfill uses the same voyage-3 embedding pipeline as the existing `seed_sensor_backfill.py` script. Sparse historical context is not acceptable for demo — the agent yield plan, anomaly reasoning, and dashboard charts all depend on populated embeddings to function correctly.

### Auth & Safety

- Requires `owner` role JWT — same guard as `POST /api/v1/admin/seed`.
- Must be disabled (returns `HTTP 403`) when `ENVIRONMENT=production` is set in `.env`. Demo reset must never run against a production database. This guard applies to the entire endpoint — the pgvector index drop/recreate, the table wipes, and the backfill must all be unreachable in production, not just individually gated.
- The router registration for `POST /api/v1/admin/demo-reset` must itself be conditional on `ENVIRONMENT != production` — do not register the route at all in production. A 403 from live code is a fallback; the route should not exist in a production process.
- Log a warning-level entry on every invocation: `DEMO RESET executed by {user.email} at {utcnow}`.
- This endpoint is development/demo environment only and must never be promoted to production as active code. Document this constraint in the endpoint's docstring so it survives a future refactor.

## 6. Deferred v1.2 Items

The following items from the v1.2 feature list are **not** in scope for this release window. They are documented here to avoid ambiguity.

| Item | Reason deferred |
|---|---|
| AI-guided yield plan wizard | Nice-to-have UX; current static form sufficient for demo |
| User-to-growing-area assignment model | No demo scenario requires farmer scoping |
| Configurable crop phase day admin UI | Constants are stable; no farmer override needed for demo |
| IoT reading source (named device identity) | No pilot hardware until post-Telara |
| SMS alert notifications | SendGrid email covers demo needs |
| Alert/notification separation (`harvest_ready` removal) | Minor enum cleanup; not demo-blocking |

All deferred items carry forward to v1.3.

---

## 7. Definition of Demo-Stable

The release is considered demo-stable when all of the following pass end-to-end without manual intervention:

**Invoicing**
- [ ] Marking a crop cycle as harvested auto-creates a draft invoice with the correct customer (or a clear `needs_customer_assignment` state if no default is configured)
- [ ] Draft invoice is editable (line items, notes, customer reassignment)
- [ ] Status transitions (send, pay, void) work and are role-enforced
- [ ] PDF downloads cleanly from the invoice detail page with correct data

**GrowingAreaPlot**
- [ ] Existing open-field crop cycles, readings, and alerts are unaffected after migration (transparent `plot_index = 0` behavior)
- [ ] A new greenhouse crop cycle can be created for a specific row
- [ ] A sensor anomaly on Row 2 fires an alert scoped to Row 2 only
- [ ] Agent yield plan reasoning references plot-scoped history, not the full area

**Regression**
- [ ] All 338 existing tests pass
- [ ] Test coverage remains ≥ 85%
- [ ] Seed data loads cleanly on a wiped database (`planted_at` recalculated if needed for current date)
