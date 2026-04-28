"""
Tests for /api/v1/admin/ endpoints.

Covers:
  - POST /bootstrap creates first owner when none exists
  - POST /bootstrap returns 409 when an owner already exists
  - POST /seed idempotent seed: customers, crops, permissions, role_permissions
  - POST /seed returns empty seeded list when called a second time (already seeded)
  - POST /seed requires owner role
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

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
