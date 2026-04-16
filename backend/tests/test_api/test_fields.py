"""
Tests for /api/v1/fields/ endpoints.

Covers:
  - Create open_field requires area_acres
  - Create dwc_greenhouse requires area_sqft
  - Successful creation returns 201
  - List returns only current user's areas
  - hired_hand cannot create a growing area
  - Unauthenticated returns 403
"""

import pytest
from httpx import AsyncClient

from app.models.user import User
from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_create_open_field_success(client: AsyncClient, owner_token: str):
    response = await client.post(
        "/api/v1/fields/",
        json={
            "name": "North Field",
            "area_type": "open_field",
            "latitude": 41.8781,
            "longitude": -93.0977,
            "area_acres": 25.0,
        },
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "North Field"
    assert data["area_type"] == "open_field"
    assert data["area_acres"] == 25.0


@pytest.mark.asyncio
async def test_create_open_field_missing_acres(client: AsyncClient, owner_token: str):
    response = await client.post(
        "/api/v1/fields/",
        json={
            "name": "North Field",
            "area_type": "open_field",
            "latitude": 41.8781,
            "longitude": -93.0977,
        },
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_greenhouse_success(client: AsyncClient, owner_token: str):
    response = await client.post(
        "/api/v1/fields/",
        json={
            "name": "Greenhouse 1",
            "area_type": "dwc_greenhouse",
            "latitude": 41.8781,
            "longitude": -93.0977,
            "area_sqft": 1200.0,
        },
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["area_type"] == "dwc_greenhouse"
    assert data["area_sqft"] == 1200.0


@pytest.mark.asyncio
async def test_create_greenhouse_missing_sqft(client: AsyncClient, owner_token: str):
    response = await client.post(
        "/api/v1/fields/",
        json={
            "name": "Greenhouse 1",
            "area_type": "dwc_greenhouse",
            "latitude": 41.8781,
            "longitude": -93.0977,
        },
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_hired_hand_cannot_create_field(client: AsyncClient, hired_hand_token: str):
    response = await client.post(
        "/api/v1/fields/",
        json={
            "name": "Sneaky Field",
            "area_type": "open_field",
            "latitude": 41.8781,
            "longitude": -93.0977,
            "area_acres": 5.0,
        },
        headers=auth_headers(hired_hand_token),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_fields_unauthenticated(client: AsyncClient):
    response = await client.get("/api/v1/fields/")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_fields_returns_only_own_areas(
    client: AsyncClient,
    owner_token: str,
    farmer_token: str,
):
    # Create a field as owner
    await client.post(
        "/api/v1/fields/",
        json={
            "name": "Owner Field",
            "area_type": "open_field",
            "latitude": 41.8781,
            "longitude": -93.0977,
            "area_acres": 10.0,
        },
        headers=auth_headers(owner_token),
    )

    # Farmer should see 0 fields (owns none)
    response = await client.get("/api/v1/fields/", headers=auth_headers(farmer_token))
    assert response.status_code == 200
    assert response.json() == []
