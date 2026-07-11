"""
Tests for /api/v1/invoice-configs/ endpoints.

Covers:
  - Get returns 404 when no config exists yet for the growing area
  - Get returns 404 for another user's growing area
  - Patch upserts (creates) a config when none exists
  - Patch updates an existing config
  - hired_hand cannot patch a config
  - Unauthenticated returns 401
"""

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers


async def _create_field(client: AsyncClient, token: str, name: str = "North Field") -> str:
    response = await client.post(
        "/api/v1/fields/",
        json={
            "name": name,
            "area_type": "open_field",
            "latitude": 41.8781,
            "longitude": -93.0977,
            "area_acres": 25.0,
        },
        headers=auth_headers(token),
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _create_customer(client: AsyncClient, token: str, name: str = "Green Valley Co-op") -> str:
    response = await client.post(
        "/api/v1/customers/",
        json={"name": name, "email": "orders@greenvalley.example.com"},
        headers=auth_headers(token),
    )
    assert response.status_code == 201
    return response.json()["id"]


@pytest.mark.asyncio
async def test_get_invoice_config_not_found(client: AsyncClient, owner_token: str):
    area_id = await _create_field(client, owner_token)
    response = await client.get(
        f"/api/v1/invoice-configs/{area_id}",
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_invoice_config_area_not_found_for_other_user(
    client: AsyncClient, owner_token: str, farmer_token: str
):
    area_id = await _create_field(client, owner_token)
    response = await client.get(
        f"/api/v1/invoice-configs/{area_id}",
        headers=auth_headers(farmer_token),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_patch_invoice_config_creates_when_missing(client: AsyncClient, owner_token: str):
    area_id = await _create_field(client, owner_token)
    customer_id = await _create_customer(client, owner_token)

    response = await client.patch(
        f"/api/v1/invoice-configs/{area_id}",
        json={"harvest_customer_id": customer_id},
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["growing_area_id"] == area_id
    assert data["harvest_customer_id"] == customer_id
    assert data["transplant_customer_id"] is None

    # Now retrievable via GET since the upsert created a row
    get_response = await client.get(
        f"/api/v1/invoice-configs/{area_id}",
        headers=auth_headers(owner_token),
    )
    assert get_response.status_code == 200
    assert get_response.json()["harvest_customer_id"] == customer_id


@pytest.mark.asyncio
async def test_patch_invoice_config_updates_existing(client: AsyncClient, owner_token: str):
    area_id = await _create_field(client, owner_token)
    first_customer_id = await _create_customer(client, owner_token, name="First Buyer")
    second_customer_id = await _create_customer(client, owner_token, name="Second Buyer")

    await client.patch(
        f"/api/v1/invoice-configs/{area_id}",
        json={"harvest_customer_id": first_customer_id},
        headers=auth_headers(owner_token),
    )

    response = await client.patch(
        f"/api/v1/invoice-configs/{area_id}",
        json={"harvest_customer_id": second_customer_id, "transplant_customer_id": second_customer_id},
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["harvest_customer_id"] == second_customer_id
    assert data["transplant_customer_id"] == second_customer_id


@pytest.mark.asyncio
async def test_patch_invoice_config_area_not_found(client: AsyncClient, owner_token: str):
    response = await client.patch(
        f"/api/v1/invoice-configs/{uuid.uuid4()}",
        json={"harvest_customer_id": None},
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_hired_hand_cannot_patch_invoice_config(
    client: AsyncClient, owner_token: str, hired_hand_token: str
):
    area_id = await _create_field(client, owner_token)
    response = await client.patch(
        f"/api/v1/invoice-configs/{area_id}",
        json={"harvest_customer_id": None},
        headers=auth_headers(hired_hand_token),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_invoice_config_unauthenticated(client: AsyncClient):
    response = await client.get(f"/api/v1/invoice-configs/{uuid.uuid4()}")
    assert response.status_code == 401
