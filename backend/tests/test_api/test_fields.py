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


@pytest.mark.asyncio
async def test_get_field_by_id(client: AsyncClient, owner_token: str):
    create_resp = await client.post(
        "/api/v1/fields/",
        json={
            "name": "Get Test Field",
            "area_type": "open_field",
            "latitude": 41.0,
            "longitude": -90.0,
            "area_acres": 15.0,
        },
        headers=auth_headers(owner_token),
    )
    assert create_resp.status_code == 201
    area_id = create_resp.json()["id"]

    response = await client.get(f"/api/v1/fields/{area_id}", headers=auth_headers(owner_token))
    assert response.status_code == 200
    assert response.json()["name"] == "Get Test Field"


@pytest.mark.asyncio
async def test_get_field_not_found(client: AsyncClient, owner_token: str):
    import uuid
    response = await client.get(
        f"/api/v1/fields/{uuid.uuid4()}",
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_field_name(client: AsyncClient, owner_token: str):
    create_resp = await client.post(
        "/api/v1/fields/",
        json={
            "name": "Old Name",
            "area_type": "open_field",
            "latitude": 41.0,
            "longitude": -90.0,
            "area_acres": 10.0,
        },
        headers=auth_headers(owner_token),
    )
    area_id = create_resp.json()["id"]

    response = await client.patch(
        f"/api/v1/fields/{area_id}",
        json={"name": "New Name"},
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"


@pytest.mark.asyncio
async def test_deactivate_field(client: AsyncClient, owner_token: str):
    create_resp = await client.post(
        "/api/v1/fields/",
        json={
            "name": "Active Field",
            "area_type": "dwc_greenhouse",
            "latitude": 41.0,
            "longitude": -90.0,
            "area_sqft": 800.0,
        },
        headers=auth_headers(owner_token),
    )
    area_id = create_resp.json()["id"]

    response = await client.patch(
        f"/api/v1/fields/{area_id}",
        json={"is_active": False},
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False


@pytest.mark.asyncio
async def test_update_field_not_found(client: AsyncClient, owner_token: str):
    import uuid
    response = await client.patch(
        f"/api/v1/fields/{uuid.uuid4()}",
        json={"name": "Ghost"},
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_field_sensor_config(client: AsyncClient, owner_token: str):
    """PATCH endpoint covers all optional sensor/area columns."""
    create_resp = await client.post(
        "/api/v1/fields/",
        json={
            "name": "Sensor Config Field",
            "area_type": "dwc_greenhouse",
            "latitude": 36.2,
            "longitude": -83.3,
            "area_sqft": 5000.0,
        },
        headers=auth_headers(owner_token),
    )
    assert create_resp.status_code == 201
    area_id = create_resp.json()["id"]

    response = await client.patch(
        f"/api/v1/fields/{area_id}",
        json={
            "area_acres": 22.0,
            "area_sqft": 6000.0,
            "nws_station_id": "KMOR",
            "temp_offset_f": 2.5,
            "humidity_offset_pct": -5.0,
            "target_temp_f": 72.0,
            "target_humidity_pct": 65.0,
        },
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["area_sqft"] == 6000.0
    assert data["nws_station_id"] == "KMOR"
    assert data["temp_offset_f"] == 2.5
    assert data["humidity_offset_pct"] == -5.0
    assert data["target_temp_f"] == 72.0
    assert data["target_humidity_pct"] == 65.0
