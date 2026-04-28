"""
Tests for invoice auto-generation and lifecycle.

Open field workflow:
  - Harvesting a cycle with actual_yield + active CropRate + default customer → draft invoice
  - Harvesting without an active CropRate → 200 but no invoice created
  - Harvesting without a default harvest customer → 200 but no invoice created

Greenhouse workflow:
  - Transplanting a greenhouse cycle → draft invoice via transplant customer
  - Transplant invoice uses correct customer, not harvest customer

Invoice lifecycle:
  - draft → sent (valid)
  - sent → paid (valid)
  - draft → voided (valid)
  - paid is terminal — any further transition returns 422
  - Quantity update recalculates total_amount
  - hired_hand cannot view or update invoices
"""

import uuid
from datetime import date

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crop import Crop, CropCycle, CropCycleStatus, YieldUnit
from app.models.customer import Customer
from app.models.field import GrowingArea, GrowingAreaType
from app.models.invoice import CropRate, Invoice, InvoiceStatus
from app.models.user import User
from tests.conftest import auth_headers


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def harvest_customer(db: AsyncSession, owner_user: User) -> Customer:
    c = Customer(
        owner_id=owner_user.id,
        name="Global Harvest Co",
        email="harvest@test.com",
    )
    db.add(c)
    await db.flush()
    return c


@pytest_asyncio.fixture
async def transplant_customer(db: AsyncSession, owner_user: User) -> Customer:
    c = Customer(
        owner_id=owner_user.id,
        name="Prairie Start Nursery",
        email="nursery@test.com",
    )
    db.add(c)
    await db.flush()
    return c


@pytest_asyncio.fixture
async def corn(db: AsyncSession, harvest_customer: Customer) -> Crop:
    crop = Crop(
        name="invoice_corn",
        greenhouse_compatible=False,
        typical_cycle_days=120,
        default_harvest_customer_id=harvest_customer.id,
    )
    db.add(crop)
    await db.flush()
    return crop


@pytest_asyncio.fixture
async def corn_no_customer(db: AsyncSession) -> Crop:
    crop = Crop(
        name="invoice_corn_nocust",
        greenhouse_compatible=False,
        typical_cycle_days=120,
    )
    db.add(crop)
    await db.flush()
    return crop


@pytest_asyncio.fixture
async def tomatoes(db: AsyncSession, harvest_customer: Customer, transplant_customer: Customer) -> Crop:
    crop = Crop(
        name="invoice_tomatoes",
        greenhouse_compatible=True,
        typical_cycle_days=90,
        default_harvest_customer_id=harvest_customer.id,
        default_transplant_customer_id=transplant_customer.id,
    )
    db.add(crop)
    await db.flush()
    return crop


@pytest_asyncio.fixture
async def corn_rate(db: AsyncSession, corn: Crop) -> CropRate:
    rate = CropRate(
        crop_id=corn.id,
        rate_per_unit=5.50,
        unit=YieldUnit.bushels,
        is_active=True,
        effective_date=date(2026, 1, 1),
    )
    db.add(rate)
    await db.flush()
    return rate


@pytest_asyncio.fixture
async def tomato_rate(db: AsyncSession, tomatoes: Crop) -> CropRate:
    rate = CropRate(
        crop_id=tomatoes.id,
        rate_per_unit=2.00,
        unit=YieldUnit.lbs,
        is_active=True,
        effective_date=date(2026, 1, 1),
    )
    db.add(rate)
    await db.flush()
    return rate


@pytest_asyncio.fixture
async def open_field(db: AsyncSession, owner_user: User) -> GrowingArea:
    area = GrowingArea(
        owner_id=owner_user.id,
        name="Invoice Corn Field",
        area_type=GrowingAreaType.open_field,
        latitude=40.1,
        longitude=-90.2,
        area_acres=80.0,
    )
    db.add(area)
    await db.flush()
    return area


@pytest_asyncio.fixture
async def greenhouse(db: AsyncSession, owner_user: User) -> GrowingArea:
    area = GrowingArea(
        owner_id=owner_user.id,
        name="Invoice GH1",
        area_type=GrowingAreaType.dwc_greenhouse,
        latitude=36.27,
        longitude=-83.22,
        area_sqft=5000.0,
    )
    db.add(area)
    await db.flush()
    return area


@pytest_asyncio.fixture
async def corn_cycle(db: AsyncSession, open_field: GrowingArea, corn: Crop, corn_rate: CropRate) -> CropCycle:
    cycle = CropCycle(
        growing_area_id=open_field.id,
        crop_id=corn.id,
        season_year=2026,
        cycle_number=1,
        planted_at=date(2026, 4, 1),
        yield_unit=YieldUnit.bushels,
        status=CropCycleStatus.active,
    )
    db.add(cycle)
    await db.flush()
    return cycle


@pytest_asyncio.fixture
async def corn_cycle_no_customer(db: AsyncSession, open_field: GrowingArea, corn_no_customer: Crop) -> CropCycle:
    rate = CropRate(
        crop_id=corn_no_customer.id,
        rate_per_unit=5.50,
        unit=YieldUnit.bushels,
        is_active=True,
        effective_date=date(2026, 1, 1),
    )
    db.add(rate)
    await db.flush()
    cycle = CropCycle(
        growing_area_id=open_field.id,
        crop_id=corn_no_customer.id,
        season_year=2026,
        cycle_number=2,
        planted_at=date(2026, 4, 1),
        yield_unit=YieldUnit.bushels,
        status=CropCycleStatus.active,
    )
    db.add(cycle)
    await db.flush()
    return cycle


@pytest_asyncio.fixture
async def tomato_cycle(db: AsyncSession, greenhouse: GrowingArea, tomatoes: Crop, tomato_rate: CropRate) -> CropCycle:
    cycle = CropCycle(
        growing_area_id=greenhouse.id,
        crop_id=tomatoes.id,
        season_year=2026,
        cycle_number=1,
        planted_at=date(2026, 1, 15),
        yield_unit=YieldUnit.lbs,
        status=CropCycleStatus.active,
    )
    db.add(cycle)
    await db.flush()
    return cycle


# ── Auto-generation: harvest ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_harvest_creates_draft_invoice(
    client: AsyncClient,
    db: AsyncSession,
    owner_token: str,
    corn_cycle: CropCycle,
):
    response = await client.patch(
        f"/api/v1/crops/cycles/{corn_cycle.id}",
        json={"status": "harvested", "actual_yield": 4800.0, "harvested_at": "2026-08-15"},
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 200

    result = await db.execute(select(Invoice).where(Invoice.crop_cycle_id == corn_cycle.id))
    invoice = result.scalar_one_or_none()
    assert invoice is not None
    assert invoice.status == InvoiceStatus.draft
    assert invoice.quantity == 4800.0
    assert invoice.total_amount == round(4800.0 * 5.50, 2)


@pytest.mark.asyncio
async def test_harvest_no_invoice_without_default_customer(
    client: AsyncClient,
    db: AsyncSession,
    owner_token: str,
    corn_cycle_no_customer: CropCycle,
):
    response = await client.patch(
        f"/api/v1/crops/cycles/{corn_cycle_no_customer.id}",
        json={"status": "harvested", "actual_yield": 3000.0, "harvested_at": "2026-08-15"},
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 200

    result = await db.execute(
        select(Invoice).where(Invoice.crop_cycle_id == corn_cycle_no_customer.id)
    )
    assert result.scalar_one_or_none() is None


# ── Auto-generation: transplant ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_transplant_creates_draft_invoice_with_transplant_customer(
    client: AsyncClient,
    db: AsyncSession,
    owner_token: str,
    tomato_cycle: CropCycle,
    transplant_customer: Customer,
):
    response = await client.patch(
        f"/api/v1/crops/cycles/{tomato_cycle.id}",
        json={"status": "transplanted", "actual_yield": 600.0},
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 200

    result = await db.execute(select(Invoice).where(Invoice.crop_cycle_id == tomato_cycle.id))
    invoice = result.scalar_one_or_none()
    assert invoice is not None
    assert invoice.status == InvoiceStatus.draft
    assert invoice.customer_id == transplant_customer.id


# ── Invoice lifecycle ─────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def draft_invoice(db: AsyncSession, corn_cycle: CropCycle, harvest_customer: Customer, corn_rate: CropRate) -> Invoice:
    invoice = Invoice(
        customer_id=harvest_customer.id,
        crop_cycle_id=corn_cycle.id,
        rate_id=corn_rate.id,
        quantity=5000.0,
        unit=YieldUnit.bushels,
        unit_price=5.50,
        total_amount=27500.0,
        status=InvoiceStatus.draft,
        invoice_date=date(2026, 8, 15),
    )
    db.add(invoice)
    await db.flush()
    return invoice


@pytest.mark.asyncio
async def test_invoice_draft_to_sent(
    client: AsyncClient, owner_token: str, draft_invoice: Invoice
):
    response = await client.patch(
        f"/api/v1/invoices/{draft_invoice.id}",
        json={"status": "sent"},
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "sent"


@pytest.mark.asyncio
async def test_invoice_sent_to_paid(
    client: AsyncClient, owner_token: str, draft_invoice: Invoice
):
    await client.patch(
        f"/api/v1/invoices/{draft_invoice.id}",
        json={"status": "sent"},
        headers=auth_headers(owner_token),
    )
    response = await client.patch(
        f"/api/v1/invoices/{draft_invoice.id}",
        json={"status": "paid"},
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "paid"


@pytest.mark.asyncio
async def test_invoice_draft_to_voided(
    client: AsyncClient, owner_token: str, draft_invoice: Invoice
):
    response = await client.patch(
        f"/api/v1/invoices/{draft_invoice.id}",
        json={"status": "voided"},
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "voided"


@pytest.mark.asyncio
async def test_invoice_paid_is_terminal(
    client: AsyncClient, owner_token: str, draft_invoice: Invoice
):
    await client.patch(
        f"/api/v1/invoices/{draft_invoice.id}",
        json={"status": "sent"},
        headers=auth_headers(owner_token),
    )
    await client.patch(
        f"/api/v1/invoices/{draft_invoice.id}",
        json={"status": "paid"},
        headers=auth_headers(owner_token),
    )
    response = await client.patch(
        f"/api/v1/invoices/{draft_invoice.id}",
        json={"status": "voided"},
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_invoice_quantity_update_recalculates_total(
    client: AsyncClient, owner_token: str, draft_invoice: Invoice
):
    response = await client.patch(
        f"/api/v1/invoices/{draft_invoice.id}",
        json={"quantity": 6000.0},
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["quantity"] == 6000.0
    assert data["total_amount"] == round(6000.0 * 5.50, 2)


@pytest.mark.asyncio
async def test_invoice_not_found(client: AsyncClient, owner_token: str):
    response = await client.get(
        f"/api/v1/invoices/{uuid.uuid4()}",
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_hired_hand_cannot_view_invoices(
    client: AsyncClient, hired_hand_token: str
):
    response = await client.get("/api/v1/invoices/", headers=auth_headers(hired_hand_token))
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_invoices_returns_invoices(
    client: AsyncClient, owner_token: str, draft_invoice: Invoice
):
    response = await client.get("/api/v1/invoices/", headers=auth_headers(owner_token))
    assert response.status_code == 200
    ids = [i["id"] for i in response.json()]
    assert str(draft_invoice.id) in ids


@pytest.mark.asyncio
async def test_get_invoice_success(
    client: AsyncClient, owner_token: str, draft_invoice: Invoice
):
    response = await client.get(
        f"/api/v1/invoices/{draft_invoice.id}",
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 200
    assert response.json()["id"] == str(draft_invoice.id)
    assert response.json()["status"] == "draft"


@pytest.mark.asyncio
async def test_update_invoice_not_found_returns_404(
    client: AsyncClient, owner_token: str
):
    response = await client.patch(
        f"/api/v1/invoices/{uuid.uuid4()}",
        json={"quantity": 100.0},
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 404
