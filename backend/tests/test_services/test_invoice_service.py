"""
Tests for invoice_service direct functions.

Covers:
  - set_crop_rate creates a new rate
  - set_crop_rate deactivates the previous active rate
  - generate_draft returns None when cycle has no actual_yield
  - generate_draft returns None when no active CropRate exists
  - update_invoice updates notes
  - update_invoice returns None when invoice not found
"""

from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crop import Crop, CropCycle, CropCycleStatus, YieldUnit
from app.models.customer import Customer
from app.models.field import GrowingArea, GrowingAreaPlot, GrowingAreaType, PlotType
from app.models.invoice import CropRate, Invoice, InvoiceStatus
from app.models.user import User
from app.services.invoice_service import (
    generate_draft,
    set_crop_rate,
    update_invoice,
)

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def harvest_customer(db: AsyncSession, owner_user: User) -> Customer:
    c = Customer(owner_id=owner_user.id, name="Test Harvest Co", email="h@test.com")
    db.add(c)
    await db.flush()
    return c


@pytest_asyncio.fixture
async def corn(db: AsyncSession, harvest_customer: Customer) -> Crop:
    crop = Crop(
        name="svc_corn",
        greenhouse_compatible=False,
        typical_cycle_days=120,
        default_harvest_customer_id=harvest_customer.id,
    )
    db.add(crop)
    await db.flush()
    return crop


@pytest_asyncio.fixture
async def field(db: AsyncSession, owner_user: User) -> GrowingArea:
    area = GrowingArea(
        owner_id=owner_user.id,
        name="Svc Test Field",
        area_type=GrowingAreaType.open_field,
        latitude=41.0,
        longitude=-90.0,
        area_acres=40.0,
    )
    db.add(area)
    await db.flush()
    return area


@pytest_asyncio.fixture
async def field_plot(db: AsyncSession, field: GrowingArea) -> GrowingAreaPlot:
    p = GrowingAreaPlot(
        growing_area_id=field.id,
        owner_id=field.owner_id,
        plot_index=0,
        plot_type=PlotType.trial_strip,
        is_active=True,
    )
    db.add(p)
    await db.flush()
    return p


@pytest_asyncio.fixture
async def cycle_no_yield(db: AsyncSession, field: GrowingArea, field_plot: GrowingAreaPlot, corn: Crop) -> CropCycle:
    cycle = CropCycle(
        growing_area_id=field.id,
        growing_area_plot_id=field_plot.id,
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
async def cycle_with_yield(db: AsyncSession, field: GrowingArea, field_plot: GrowingAreaPlot, corn: Crop) -> CropCycle:
    cycle = CropCycle(
        growing_area_id=field.id,
        growing_area_plot_id=field_plot.id,
        crop_id=corn.id,
        season_year=2026,
        cycle_number=2,
        planted_at=date(2026, 4, 1),
        actual_yield=4000.0,
        yield_unit=YieldUnit.bushels,
        status=CropCycleStatus.harvested,
    )
    db.add(cycle)
    await db.flush()
    return cycle


async def test_set_crop_rate_creates_rate(db: AsyncSession, corn: Crop):
    rate = await set_crop_rate(
        crop_id=corn.id,
        rate_per_unit=6.00,
        unit="bushels",
        effective_date=date(2026, 1, 1),
        db=db,
    )
    assert rate.id is not None
    assert rate.rate_per_unit == 6.00
    assert rate.is_active is True


async def test_set_crop_rate_deactivates_previous(db: AsyncSession, corn: Crop):
    old_rate = await set_crop_rate(
        crop_id=corn.id,
        rate_per_unit=5.00,
        unit="bushels",
        effective_date=date(2026, 1, 1),
        db=db,
    )
    new_rate = await set_crop_rate(
        crop_id=corn.id,
        rate_per_unit=6.50,
        unit="bushels",
        effective_date=date(2026, 4, 1),
        db=db,
    )

    result = await db.execute(select(CropRate).where(CropRate.id == old_rate.id))
    refreshed_old = result.scalar_one()
    assert refreshed_old.is_active is False
    assert new_rate.is_active is True


async def test_generate_draft_returns_none_without_actual_yield(
    db: AsyncSession, cycle_no_yield: CropCycle
):
    result = await generate_draft(cycle_no_yield.id, db)
    assert result is None


async def test_generate_draft_creates_invoice_without_active_rate(
    db: AsyncSession, cycle_with_yield: CropCycle
):
    """v1.2: invoice still created with null unit_price/total_amount when no CropRate exists."""
    result = await generate_draft(cycle_with_yield.id, db)
    assert result is not None
    assert result.unit_price is None
    assert result.total_amount is None


async def test_update_invoice_notes(db: AsyncSession, harvest_customer: Customer, corn: Crop, field: GrowingArea, field_plot: GrowingAreaPlot):
    cycle = CropCycle(
        growing_area_id=field.id,
        growing_area_plot_id=field_plot.id,
        crop_id=corn.id,
        season_year=2026,
        cycle_number=10,
        planted_at=date(2026, 4, 1),
        yield_unit=YieldUnit.bushels,
        status=CropCycleStatus.active,
    )
    db.add(cycle)
    await db.flush()

    rate = CropRate(
        crop_id=corn.id,
        rate_per_unit=5.50,
        unit=YieldUnit.bushels,
        is_active=True,
        effective_date=date(2026, 1, 1),
    )
    db.add(rate)
    await db.flush()

    invoice = Invoice(
        customer_id=harvest_customer.id,
        crop_cycle_id=cycle.id,
        crop_rate_id=rate.id,
        quantity=1000.0,
        unit=YieldUnit.bushels,
        unit_price=5.50,
        total_amount=5500.0,
        status=InvoiceStatus.draft,
        invoice_date=date(2026, 8, 1),
    )
    db.add(invoice)
    await db.flush()

    updated = await update_invoice(invoice.id, db, notes="Special delivery instructions.")
    assert updated is not None
    assert updated.notes == "Special delivery instructions."


async def test_update_invoice_returns_none_when_not_found(db: AsyncSession):
    import uuid
    result = await update_invoice(uuid.uuid4(), db, notes="Ghost")
    assert result is None
