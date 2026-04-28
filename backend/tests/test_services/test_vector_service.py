"""
Tests for vector_service — generate_embedding, find_similar_weeks, upsert_historical_summary.

The Anthropic embeddings API is mocked so tests run without an API key.
pgvector is available in the test DB (yearly_yields_test has the extension installed).
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crop import Crop
from app.models.field import GrowingArea, GrowingAreaType
from app.models.historical_summary import HistoricalSummary
from app.models.user import User
from app.services.vector_service import (
    _build_embedding_text,
    find_similar_weeks,
    generate_embedding,
    upsert_historical_summary,
)

pytestmark = pytest.mark.asyncio

FAKE_EMBEDDING = [0.01] * 1536


def _make_mock_embedding_response(embedding: list[float]) -> MagicMock:
    resp = MagicMock()
    resp.data = [MagicMock(embedding=embedding)]
    return resp


@pytest_asyncio.fixture
async def area(db: AsyncSession, owner_user: User) -> GrowingArea:
    a = GrowingArea(
        owner_id=owner_user.id,
        name="Vector Test Field",
        area_type=GrowingAreaType.open_field,
        latitude=41.0,
        longitude=-90.0,
        area_acres=10.0,
    )
    db.add(a)
    await db.flush()
    return a


@pytest_asyncio.fixture
async def corn(db: AsyncSession) -> Crop:
    crop = Crop(name="vector_corn", greenhouse_compatible=False, typical_cycle_days=167)
    db.add(crop)
    await db.flush()
    return crop


# ── _build_embedding_text ─────────────────────────────────────────────────────

def test_build_embedding_text_contains_crop_and_type():
    text = _build_embedding_text(72.0, 65.0, "corn", GrowingAreaType.open_field)
    assert "corn" in text
    assert "open field" in text
    assert "72.0" in text
    assert "65.0" in text


# ── generate_embedding ────────────────────────────────────────────────────────

async def test_generate_embedding_returns_vector():
    mock_resp = _make_mock_embedding_response(FAKE_EMBEDDING)
    mock_client = MagicMock()
    mock_client.embeddings = MagicMock()
    mock_client.embeddings.create = AsyncMock(return_value=mock_resp)

    with patch("app.services.vector_service._client", mock_client):
        result = await generate_embedding(72.0, 65.0, "corn", GrowingAreaType.open_field)
    assert len(result) == 1536
    assert result[0] == 0.01


# ── find_similar_weeks ────────────────────────────────────────────────────────

async def test_find_similar_weeks_empty_db(
    db: AsyncSession, area: GrowingArea, corn: Crop
):
    result = await find_similar_weeks(area.id, corn.id, FAKE_EMBEDDING, db)
    assert result == []


async def test_find_similar_weeks_returns_data(
    db: AsyncSession, area: GrowingArea, corn: Crop
):
    summary = HistoricalSummary(
        growing_area_id=area.id,
        crop_id=corn.id,
        week_number=15,
        year=2025,
        avg_temperature=72.0,
        min_temperature=65.0,
        max_temperature=80.0,
        avg_humidity=60.0,
        min_humidity=50.0,
        max_humidity=70.0,
        reading_count=42,
        embedding=FAKE_EMBEDDING,
    )
    db.add(summary)
    await db.flush()

    result = await find_similar_weeks(area.id, corn.id, FAKE_EMBEDDING, db)
    assert len(result) == 1
    assert result[0]["week_number"] == 15
    assert result[0]["avg_temperature"] == 72.0
    assert "similarity_distance" in result[0]


# ── upsert_historical_summary ─────────────────────────────────────────────────

async def test_upsert_creates_new_summary(
    db: AsyncSession, area: GrowingArea, corn: Crop
):
    with patch(
        "app.services.vector_service.generate_embedding",
        new=AsyncMock(return_value=FAKE_EMBEDDING),
    ):
        summary = await upsert_historical_summary(
            growing_area_id=area.id,
            crop_id=corn.id,
            week_number=20,
            year=2026,
            avg_temperature=74.0,
            min_temperature=68.0,
            max_temperature=82.0,
            avg_humidity=62.0,
            min_humidity=55.0,
            max_humidity=70.0,
            reading_count=35,
            crop_name="vector_corn",
            area_type=GrowingAreaType.open_field,
            db=db,
        )
    assert summary.id is not None
    assert summary.week_number == 20
    assert summary.avg_temperature == 74.0


async def test_upsert_updates_existing_summary(
    db: AsyncSession, area: GrowingArea, corn: Crop
):
    existing = HistoricalSummary(
        growing_area_id=area.id,
        crop_id=corn.id,
        week_number=21,
        year=2026,
        avg_temperature=70.0,
        min_temperature=60.0,
        max_temperature=80.0,
        avg_humidity=58.0,
        min_humidity=48.0,
        max_humidity=68.0,
        reading_count=30,
        embedding=FAKE_EMBEDDING,
    )
    db.add(existing)
    await db.flush()

    with patch(
        "app.services.vector_service.generate_embedding",
        new=AsyncMock(return_value=FAKE_EMBEDDING),
    ):
        updated = await upsert_historical_summary(
            growing_area_id=area.id,
            crop_id=corn.id,
            week_number=21,
            year=2026,
            avg_temperature=78.0,
            min_temperature=65.0,
            max_temperature=88.0,
            avg_humidity=62.0,
            min_humidity=52.0,
            max_humidity=72.0,
            reading_count=40,
            crop_name="vector_corn",
            area_type=GrowingAreaType.open_field,
            db=db,
        )
    assert updated.id == existing.id
    assert updated.avg_temperature == 78.0
    assert updated.reading_count == 40
