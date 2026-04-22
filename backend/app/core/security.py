"""
Security utilities — password hashing and JWT handling.

Uses:
  - passlib/bcrypt for password hashing
  - python-jose for JWT creation and verification

Two token types:
  - access_token:  short-lived (ACCESS_TOKEN_EXPIRE_MINUTES), used on every request
  - refresh_token: long-lived (REFRESH_TOKEN_EXPIRE_DAYS), used only to get a new access token
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


def _create_token(subject: str, token_type: str, expires_delta: timedelta, role: str | None = None) -> str:
    expire = datetime.now(timezone.utc) + expires_delta
    payload = {
        "sub": subject,       # user id (UUID as string)
        "type": token_type,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    if role is not None:
        payload["role"] = role
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(user_id: str, role: str | None = None) -> str:
    return _create_token(
        subject=user_id,
        token_type=ACCESS_TOKEN_TYPE,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        role=role,
    )


def create_refresh_token(user_id: str) -> str:
    return _create_token(
        subject=user_id,
        token_type=REFRESH_TOKEN_TYPE,
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str, expected_type: str) -> Optional[str]:
    """
    Decode and validate a JWT. Returns the user_id (sub) on success, None on failure.
    Validates token type to prevent access tokens being used as refresh tokens and vice versa.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != expected_type:
            return None
        return payload.get("sub")
    except JWTError:
        return None


def decode_access_payload(token: str) -> Optional[dict]:
    """Decode an access token and return its full payload, or None on failure."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != ACCESS_TOKEN_TYPE:
            return None
        return payload
    except JWTError:
        return None
