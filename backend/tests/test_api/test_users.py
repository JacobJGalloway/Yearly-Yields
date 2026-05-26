import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth_headers


pytestmark = pytest.mark.asyncio


async def test_get_me(client: AsyncClient, owner_token: str):
    r = await client.get("/api/v1/users/me", headers=auth_headers(owner_token))
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == "owner@test.com"
    assert data["role"] == "owner"


async def test_get_me_unauthenticated(client: AsyncClient):
    r = await client.get("/api/v1/users/me")
    assert r.status_code == 401


async def test_list_users_as_owner(client: AsyncClient, owner_token: str, farmer_user, hired_hand_user):
    r = await client.get("/api/v1/users/", headers=auth_headers(owner_token))
    assert r.status_code == 200
    emails = [u["email"] for u in r.json()]
    assert "farmer@test.com" in emails
    assert "hiredhand@test.com" in emails
    assert "owner@test.com" not in emails   # owners excluded from list


async def test_list_users_as_farmer(client: AsyncClient, farmer_token: str):
    r = await client.get("/api/v1/users/", headers=auth_headers(farmer_token))
    assert r.status_code == 200


async def test_list_users_hired_hand_forbidden(client: AsyncClient, hired_hand_token: str):
    r = await client.get("/api/v1/users/", headers=auth_headers(hired_hand_token))
    assert r.status_code == 403


async def test_create_user_success(client: AsyncClient, owner_token: str):
    r = await client.post(
        "/api/v1/users/",
        headers=auth_headers(owner_token),
        json={
            "email": "newfarmer@test.com",
            "password": "password123",
            "full_name": "New Farmer",
            "role": "farmer",
        },
    )
    assert r.status_code == 201
    assert r.json()["email"] == "newfarmer@test.com"


async def test_create_user_duplicate_email(client: AsyncClient, owner_token: str, farmer_user):
    r = await client.post(
        "/api/v1/users/",
        headers=auth_headers(owner_token),
        json={
            "email": "farmer@test.com",
            "password": "password123",
            "full_name": "Duplicate",
            "role": "farmer",
        },
    )
    assert r.status_code == 409


async def test_create_user_farmer_cannot(client: AsyncClient, farmer_token: str):
    r = await client.post(
        "/api/v1/users/",
        headers=auth_headers(farmer_token),
        json={
            "email": "another@test.com",
            "password": "password123",
            "full_name": "Another",
            "role": "hired_hand",
        },
    )
    assert r.status_code == 403


async def test_get_user_by_id(client: AsyncClient, owner_token: str, farmer_user):
    r = await client.get(f"/api/v1/users/{farmer_user.id}", headers=auth_headers(owner_token))
    assert r.status_code == 200
    assert r.json()["email"] == "farmer@test.com"


async def test_get_user_not_found(client: AsyncClient, owner_token: str):
    import uuid
    r = await client.get(f"/api/v1/users/{uuid.uuid4()}", headers=auth_headers(owner_token))
    assert r.status_code == 404


async def test_update_user_self(client: AsyncClient, farmer_token: str, farmer_user):
    r = await client.patch(
        f"/api/v1/users/{farmer_user.id}",
        headers=auth_headers(farmer_token),
        json={"full_name": "Updated Farmer"},
    )
    assert r.status_code == 200
    assert r.json()["full_name"] == "Updated Farmer"


async def test_update_user_other_forbidden_for_non_owner(
    client: AsyncClient, farmer_token: str, hired_hand_user
):
    r = await client.patch(
        f"/api/v1/users/{hired_hand_user.id}",
        headers=auth_headers(farmer_token),
        json={"full_name": "Hacked"},
    )
    assert r.status_code == 403


async def test_update_active_status_owner_only(
    client: AsyncClient, owner_token: str, farmer_token: str, farmer_user
):
    # farmer cannot deactivate another user
    r = await client.patch(
        f"/api/v1/users/{farmer_user.id}",
        headers=auth_headers(farmer_token),
        json={"is_active": False},
    )
    assert r.status_code == 403

    # owner can
    r = await client.patch(
        f"/api/v1/users/{farmer_user.id}",
        headers=auth_headers(owner_token),
        json={"is_active": False},
    )
    assert r.status_code == 200
    assert r.json()["is_active"] is False


async def test_update_user_not_found(client: AsyncClient, owner_token: str):
    import uuid
    r = await client.patch(
        f"/api/v1/users/{uuid.uuid4()}",
        headers=auth_headers(owner_token),
        json={"full_name": "Ghost"},
    )
    assert r.status_code == 404


async def test_update_user_phone_and_address(
    client: AsyncClient, farmer_token: str, farmer_user
):
    r = await client.patch(
        f"/api/v1/users/{farmer_user.id}",
        headers=auth_headers(farmer_token),
        json={"phone": "555-1234", "address": "123 Main St"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["phone"] == "555-1234"
    assert data["address"] == "123 Main St"
