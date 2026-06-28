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

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_refresh_token,
    generate_reset_token,
    hash_password,
    verify_password,
)
from app.models.password_reset_token import PasswordResetToken
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


# ── get_current_user dependency edge cases ────────────────────────────────────

@pytest.mark.asyncio
async def test_protected_endpoint_rejects_invalid_access_token(client: AsyncClient):
    """Malformed access token hits the credentials_exception at decode step."""
    response = await client.get(
        "/api/v1/fields/",
        headers={"Authorization": "Bearer this.is.not.a.real.token"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_rejects_access_token_for_nonexistent_user(
    client: AsyncClient,
):
    """Valid-format token for a user ID that doesn't exist in the DB → 401."""
    import uuid
    from app.core.security import create_access_token
    ghost_token = create_access_token(str(uuid.uuid4()))
    response = await client.get(
        "/api/v1/fields/",
        headers={"Authorization": f"Bearer {ghost_token}"},
    )
    assert response.status_code == 401


# ── forgot-password ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_forgot_password_unknown_email_returns_204(client: AsyncClient):
    """Unknown email returns 204 silently — no information leakage."""
    response = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "nobody@example.com"},
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_forgot_password_inactive_user_returns_204(client: AsyncClient, db: AsyncSession):
    """Inactive user returns 204 and no token is created."""
    inactive = User(
        email="inactive2@test.com",
        hashed_password=hash_password("testpassword"),
        full_name="Inactive",
        role=UserRole.farmer,
        is_active=False,
    )
    db.add(inactive)
    await db.flush()

    response = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "inactive2@test.com"},
    )
    assert response.status_code == 204

    result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.user_id == inactive.id)
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_forgot_password_known_user_creates_token(
    client: AsyncClient, db: AsyncSession, owner_user: User
):
    """Known active user gets a PasswordResetToken in the database."""
    with patch("app.services.email_service.send_password_reset_email", new=AsyncMock(return_value=None)):
        response = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "owner@test.com"},
        )
    assert response.status_code == 204

    result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.user_id == owner_user.id)
    )
    token = result.scalar_one_or_none()
    assert token is not None
    assert token.used_at is None


# ── reset-password ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reset_password_invalid_token_returns_400(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": "notarealtoken", "new_password": "newsecurepassword"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_reset_password_success(
    client: AsyncClient, db: AsyncSession, owner_user: User
):
    """Valid unexpired token updates the password and marks itself used."""
    raw_token, token_hash = generate_reset_token()
    reset_token = PasswordResetToken(
        user_id=owner_user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=60),
    )
    db.add(reset_token)
    await db.flush()

    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "brandnewpassword"},
    )
    assert response.status_code == 204

    await db.refresh(reset_token)
    assert reset_token.used_at is not None

    await db.refresh(owner_user)
    assert verify_password("brandnewpassword", owner_user.hashed_password)


@pytest.mark.asyncio
async def test_reset_password_expired_token_returns_400(
    client: AsyncClient, db: AsyncSession, owner_user: User
):
    """Token past its expiry is rejected."""
    raw_token, token_hash = generate_reset_token()
    expired = PasswordResetToken(
        user_id=owner_user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    db.add(expired)
    await db.flush()

    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "doesntmatter"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_reset_password_used_token_returns_400(
    client: AsyncClient, db: AsyncSession, owner_user: User
):
    """Already-used token is rejected."""
    raw_token, token_hash = generate_reset_token()
    used = PasswordResetToken(
        user_id=owner_user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=60),
        used_at=datetime.now(timezone.utc),
    )
    db.add(used)
    await db.flush()

    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "doesntmatter"},
    )
    assert response.status_code == 400
