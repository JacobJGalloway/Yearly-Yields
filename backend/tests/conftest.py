"""
Shared test fixtures for the Yearly Yields test suite.

Database strategy:
  - Uses a separate test database (yearly_yields_test) to avoid polluting dev data.
  - Each test runs inside a transaction that is rolled back after the test completes.
  - This keeps tests isolated and fast without recreating the schema on every run.

Setup required (one-time):
  docker exec -it yearly_yields_db psql -U user -c "CREATE DATABASE yearly_yields_test;"
"""

import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import create_access_token, hash_password
from app.db.session import get_db
from app.main import app
from app.models.base import Base
from app.models.user import User, UserRole

TEST_DATABASE_URL = "postgresql+asyncpg://user:password@localhost:5432/yearly_yields_test"

_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
_TestSessionLocal = async_sessionmaker(
    bind=_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


@pytest.fixture(scope="session")
def event_loop():
    """Single event loop shared across the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables():
    """Create all tables once per test session, drop them at the end."""
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide a test database session that rolls back after each test.
    Ensures complete isolation between tests.
    """
    async with _TestSessionLocal() as session:
        async with session.begin():
            yield session
            await session.rollback()


@pytest_asyncio.fixture
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Provide an AsyncClient wired to the FastAPI app with the test DB session injected.
    """
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def owner_user(db: AsyncSession) -> User:
    """A seeded owner user for tests that require authentication."""
    user = User(
        email="owner@test.com",
        hashed_password=hash_password("testpassword"),
        full_name="Test Owner",
        role=UserRole.owner,
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def farmer_user(db: AsyncSession) -> User:
    """A seeded farmer user for RBAC tests."""
    user = User(
        email="farmer@test.com",
        hashed_password=hash_password("testpassword"),
        full_name="Test Farmer",
        role=UserRole.farmer,
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def hired_hand_user(db: AsyncSession) -> User:
    """A seeded hired_hand user for RBAC tests."""
    user = User(
        email="hiredhand@test.com",
        hashed_password=hash_password("testpassword"),
        full_name="Test Hired Hand",
        role=UserRole.hired_hand,
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
def owner_token(owner_user: User) -> str:
    return create_access_token(str(owner_user.id))


@pytest_asyncio.fixture
def farmer_token(farmer_user: User) -> str:
    return create_access_token(str(farmer_user.id))


@pytest_asyncio.fixture
def hired_hand_token(hired_hand_user: User) -> str:
    return create_access_token(str(hired_hand_user.id))


def auth_headers(token: str) -> dict:
    """Helper to build Authorization header dict."""
    return {"Authorization": f"Bearer {token}"}
