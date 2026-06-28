"""
Tests for /api/v1/admin/ endpoints.

Covers:
  - POST /bootstrap creates first owner when none exists
  - POST /bootstrap returns 409 when an owner already exists
  - POST /seed idempotent seed: customers, crops, permissions, role_permissions
  - POST /seed returns empty seeded list when called a second time (already seeded)
  - POST /seed requires owner role
  - POST /demo-reset returns 403 in production environment
  - POST /demo-reset returns 422 when demo areas are missing
  - POST /demo-reset rebuilds cycles when demo areas exist
"""

from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.admin import _DEMO_AREA_NAMES, _GH_OFFSETS
from app.models.crop import Crop
from app.models.field import GrowingArea, GrowingAreaPlot, GrowingAreaType, PlotType
from app.models.user import User
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def test_bootstrap_creates_owner(client: AsyncClient, db: AsyncSession):
    response = await client.post(
        "/api/v1/admin/bootstrap",
        json={
            "email": "firstowner@test.com",
            "password": "password123",
            "full_name": "First Owner",
            "role": "owner",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "firstowner@test.com"
    assert data["role"] == "owner"


async def test_bootstrap_conflict_when_owner_exists(client: AsyncClient, owner_user: User):
    response = await client.post(
        "/api/v1/admin/bootstrap",
        json={
            "email": "another@test.com",
            "password": "password123",
            "full_name": "Another Owner",
            "role": "owner",
        },
    )
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"].lower()


async def test_seed_data_success(client: AsyncClient, owner_token: str):
    response = await client.post(
        "/api/v1/admin/seed",
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 200
    data = response.json()
    seeded = data["seeded"]
    # Should seed customers, crops, permissions, and role_permissions
    assert any("customer:" in s for s in seeded)
    assert any("crop:" in s for s in seeded)
    assert any("permission:" in s for s in seeded)
    assert any("role_permission:" in s for s in seeded)


async def test_seed_data_idempotent(client: AsyncClient, owner_token: str):
    await client.post("/api/v1/admin/seed", headers=auth_headers(owner_token))

    # Second call should seed nothing new
    response = await client.post(
        "/api/v1/admin/seed",
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["seeded"] == []
    assert "up to date" in data["message"].lower()


async def test_seed_requires_owner(client: AsyncClient, farmer_token: str):
    response = await client.post(
        "/api/v1/admin/seed",
        headers=auth_headers(farmer_token),
    )
    assert response.status_code == 403


# ── demo-reset ────────────────────────────────────────────────────────────────

async def test_demo_reset_blocked_in_production(client: AsyncClient, owner_token: str):
    with patch("app.api.v1.admin.settings") as mock_settings:
        mock_settings.APP_ENV = "production"
        response = await client.post(
            "/api/v1/admin/demo-reset",
            headers=auth_headers(owner_token),
        )
    assert response.status_code == 403
    assert "production" in response.json()["detail"].lower()


async def test_demo_reset_missing_areas_returns_422(client: AsyncClient, owner_token: str):
    """No demo areas seeded → 422 with missing area names."""
    response = await client.post(
        "/api/v1/admin/demo-reset",
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any(name in detail for name in _DEMO_AREA_NAMES)


async def test_demo_reset_rebuilds_cycles(
    client: AsyncClient,
    db: AsyncSession,
    owner_user: User,
    owner_token: str,
):
    """Happy path: creates demo areas + sentinel plots, calls reset, verifies response."""
    # Seed crops needed by the endpoint
    crops = [
        Crop(name="tomatoes",        greenhouse_compatible=True,  typical_cycle_days=90),
        Crop(name="arugula_lettuce", greenhouse_compatible=True,  typical_cycle_days=64),
        Crop(name="corn",            greenhouse_compatible=False, typical_cycle_days=120),
        Crop(name="soybeans",        greenhouse_compatible=False, typical_cycle_days=100),
    ]
    for c in crops:
        db.add(c)

    # Seed all 7 demo growing areas with sentinel plots
    area_type_map = {name: GrowingAreaType.dwc_greenhouse for name in _GH_OFFSETS}
    area_type_map["Jax IL — Corn Field"]    = GrowingAreaType.open_field
    area_type_map["Jax IL — Soybean Field"] = GrowingAreaType.open_field

    for area_name in _DEMO_AREA_NAMES:
        area = GrowingArea(
            owner_id=owner_user.id,
            name=area_name,
            area_type=area_type_map[area_name],
            latitude=36.2,
            longitude=-83.2,
            area_sqft=5000.0,
        )
        db.add(area)
        await db.flush()
        plot = GrowingAreaPlot(
            growing_area_id=area.id,
            owner_id=owner_user.id,
            plot_index=0,
            plot_type=PlotType.trial_strip,
            is_active=True,
        )
        db.add(plot)

    await db.flush()

    response = await client.post(
        "/api/v1/admin/demo-reset",
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Demo reset complete"
    assert isinstance(data["created_cycles"], list)
    assert len(data["created_cycles"]) == 7
    # Greenhouse cycles should all show planted_at and days_in_cycle
    gh_cycles = [c for c in data["created_cycles"] if "days_in_cycle" in c and c.get("crop") == "tomatoes"]
    assert len(gh_cycles) == 4

    # Idempotency: second call should also succeed with 7 deleted and 7 created
    response2 = await client.post(
        "/api/v1/admin/demo-reset",
        headers=auth_headers(owner_token),
    )
    assert response2.status_code == 200
    assert response2.json()["deleted_active_cycles"] == 7
