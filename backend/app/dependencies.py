"""
Shared FastAPI dependencies.

Usage in endpoints:
  current_user: User = Depends(get_current_user)
  _: User = Depends(require_role(UserRole.farmer, UserRole.owner))
"""

import uuid
from typing import Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import credentials_exception, forbidden_exception
from app.core.security import ACCESS_TOKEN_TYPE, decode_token
from app.db.session import get_db
from app.models.user import User, UserRole

_bearer = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Validate the Bearer token and return the authenticated user.
    Raises 401 if the token is missing, expired, or invalid.
    Raises 401 if the user no longer exists or is inactive.
    """
    user_id = decode_token(credentials.credentials, expected_type=ACCESS_TOKEN_TYPE)
    if user_id is None:
        raise credentials_exception

    result = await db.execute(
        select(User).where(User.id == uuid.UUID(user_id), User.is_active == True)  # noqa: E712
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception

    return user


def require_role(*roles: UserRole) -> Callable:
    """
    Dependency factory — restricts an endpoint to specific roles.
    Owner always passes (wildcard bypass).

    Usage:
      @router.post("/invoices")
      async def create_invoice(
          _: User = Depends(require_role(UserRole.farmer, UserRole.owner)),
          ...
      ):
    """
    async def _check(user: User = Depends(get_current_user)) -> User:
        if user.role == UserRole.owner:
            return user
        if user.role not in roles:
            raise forbidden_exception
        return user

    return _check
