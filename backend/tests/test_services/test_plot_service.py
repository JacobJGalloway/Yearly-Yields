"""
Tests for plot_service.py functions not covered by API tests.

Covers:
  - resolve_plot_id: non-None plot_id that belongs to a different area → 422
  - resolve_plot_id: None plot_id with no sentinel → 404
"""

import uuid

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.field import GrowingArea, GrowingAreaPlot, GrowingAreaType, PlotType
from app.models.user import User, UserRole
from app.services.plot_service import resolve_plot_id

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def owner_user(db: AsyncSession) -> User:
    from app.core.security import hash_password
    user = User(
        email="plotowner@test.com",
        hashed_password=hash_password("testpassword"),
        full_name="Plot Owner",
        role=UserRole.owner,
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def area_a(db: AsyncSession, owner_user: User) -> GrowingArea:
    area = GrowingArea(
        owner_id=owner_user.id,
        name="Area A",
        area_type=GrowingAreaType.dwc_greenhouse,
        latitude=36.0,
        longitude=-84.0,
        area_sqft=1000.0,
    )
    db.add(area)
    await db.flush()
    return area


@pytest_asyncio.fixture
async def area_b(db: AsyncSession, owner_user: User) -> GrowingArea:
    area = GrowingArea(
        owner_id=owner_user.id,
        name="Area B",
        area_type=GrowingAreaType.dwc_greenhouse,
        latitude=36.0,
        longitude=-84.0,
        area_sqft=1000.0,
    )
    db.add(area)
    await db.flush()
    return area


@pytest_asyncio.fixture
async def plot_in_area_a(db: AsyncSession, area_a: GrowingArea, owner_user: User) -> GrowingAreaPlot:
    plot = GrowingAreaPlot(
        growing_area_id=area_a.id,
        owner_id=owner_user.id,
        plot_index=1,
        plot_type=PlotType.dwc_row,
        is_active=True,
    )
    db.add(plot)
    await db.flush()
    return plot


async def test_resolve_plot_id_wrong_area_raises_422(
    db: AsyncSession,
    area_a: GrowingArea,
    area_b: GrowingArea,
    plot_in_area_a: GrowingAreaPlot,
):
    """Providing a plot_id that belongs to a different area raises 422."""
    with pytest.raises(HTTPException) as exc_info:
        await resolve_plot_id(area_b.id, plot_in_area_a.id, db)
    assert exc_info.value.status_code == 422
    assert str(area_b.id) in exc_info.value.detail


async def test_resolve_plot_id_no_sentinel_raises_404(
    db: AsyncSession,
    area_a: GrowingArea,
    plot_in_area_a: GrowingAreaPlot,
):
    """No sentinel (plot_index=0) in area raises 404."""
    with pytest.raises(HTTPException) as exc_info:
        await resolve_plot_id(area_a.id, None, db)
    assert exc_info.value.status_code == 404
    assert "sentinel" in exc_info.value.detail.lower()
