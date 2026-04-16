"""
Tests for POST /api/v1/auth/login and POST /api/v1/auth/refresh.

Covers:
  - Successful login returns access + refresh tokens
  - Wrong password returns 401
  - Unknown email returns 401
  - Inactive user returns 401
  - Valid refresh token returns new tokens
  - Invalid refresh token returns 401
  - Access token cannot be used as refresh token
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_refresh_token, hash_password
from app.models.user import User, UserRole


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, owner_user: User):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "owner@test.com", "password": "testpassword"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, owner_user: User):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "owner@test.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_email(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@test.com", "password": "testpassword"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_inactive_user(client: AsyncClient, db: AsyncSession):
    inactive = User(
        email="inactive@test.com",
        hashed_password=hash_password("testpassword"),
        full_name="Inactive User",
        role=UserRole.farmer,
        is_active=False,
    )
    db.add(inactive)
    await db.flush()

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "inactive@test.com", "password": "testpassword"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_does_not_reveal_account_existence(client: AsyncClient):
    """Wrong password and unknown email should return identical 401 responses."""
    wrong_pass = await client.post(
        "/api/v1/auth/login",
        json={"email": "owner@test.com", "password": "wrongpassword"},
    )
    unknown_email = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@test.com", "password": "wrongpassword"},
    )
    assert wrong_pass.status_code == unknown_email.status_code == 401
    assert wrong_pass.json()["detail"] == unknown_email.json()["detail"]


@pytest.mark.asyncio
async def test_refresh_success(client: AsyncClient, owner_user: User):
    refresh_token = create_refresh_token(str(owner_user.id))
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_refresh_invalid_token(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "not.a.valid.token"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_access_token_rejected_as_refresh(client: AsyncClient, owner_user: User):
    """Access tokens must not be accepted on the refresh endpoint."""
    from app.core.security import create_access_token
    access_token = create_access_token(str(owner_user.id))
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": access_token},
    )
    assert response.status_code == 401
