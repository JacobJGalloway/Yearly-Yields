"""
Tests for /api/v1/customers/ endpoints.

Covers:
  - Successful creation returns 201
  - List returns only current user's customers
  - Get by ID returns 404 for another user's customer
  - Update name, email, phone, is_active
  - hired_hand cannot create a customer
  - Unauthenticated returns 401
"""

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers

CUSTOMER_PAYLOAD = {
    "name": "Green Valley Co-op",
    "email": "orders@greenvalley.example.com",
    "phone": "555-0100",
}


@pytest.mark.asyncio
async def test_create_customer_success(client: AsyncClient, owner_token: str):
    response = await client.post(
        "/api/v1/customers/",
        json=CUSTOMER_PAYLOAD,
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Green Valley Co-op"
    assert data["email"] == "orders@greenvalley.example.com"
    assert data["phone"] == "555-0100"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_create_customer_without_phone(client: AsyncClient, owner_token: str):
    response = await client.post(
        "/api/v1/customers/",
        json={"name": "No Phone Buyer", "email": "nophone@example.com"},
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 201
    assert response.json()["phone"] is None


@pytest.mark.asyncio
async def test_hired_hand_cannot_create_customer(client: AsyncClient, hired_hand_token: str):
    response = await client.post(
        "/api/v1/customers/",
        json=CUSTOMER_PAYLOAD,
        headers=auth_headers(hired_hand_token),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_customers_unauthenticated(client: AsyncClient):
    response = await client.get("/api/v1/customers/")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_customers_returns_only_own(
    client: AsyncClient,
    owner_token: str,
    farmer_token: str,
):
    await client.post(
        "/api/v1/customers/",
        json=CUSTOMER_PAYLOAD,
        headers=auth_headers(owner_token),
    )
    response = await client.get("/api/v1/customers/", headers=auth_headers(farmer_token))
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_customer_not_found_for_other_user(
    client: AsyncClient,
    owner_token: str,
    farmer_token: str,
):
    create = await client.post(
        "/api/v1/customers/",
        json=CUSTOMER_PAYLOAD,
        headers=auth_headers(owner_token),
    )
    customer_id = create.json()["id"]

    response = await client.get(
        f"/api/v1/customers/{customer_id}",
        headers=auth_headers(farmer_token),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_customer(client: AsyncClient, owner_token: str):
    create = await client.post(
        "/api/v1/customers/",
        json=CUSTOMER_PAYLOAD,
        headers=auth_headers(owner_token),
    )
    customer_id = create.json()["id"]

    response = await client.patch(
        f"/api/v1/customers/{customer_id}",
        json={"name": "Green Valley Updated", "is_active": False},
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Green Valley Updated"
    assert data["is_active"] is False
