"""
Vector service for semantic similarity search over historical summaries.

Responsibilities:
  1. Generate embeddings from sensor reading data via the Anthropic API.
  2. Query historical_summaries using pgvector cosine distance for the
     most similar weeks from the past 3 years.

Embedding strategy:
  Input text encodes temperature, humidity, crop, and growing area type so
  the vector captures agronomic context — not just raw numbers. This makes
  "hot + dry week for corn in an open field" meaningfully different from
  "hot + dry week for tomatoes in a greenhouse."

Dimension: 1536 — matches Anthropic's voyage-3 embedding model output.
The Vector(1536) column in historical_summaries.embedding is sized to match.
"""

import uuid
from typing import Optional

import anthropic
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.field import GrowingAreaType
from app.models.historical_summary import HistoricalSummary

_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

EMBEDDING_MODEL = "voyage-3"
EMBEDDING_DIMENSION = 1536
SIMILARITY_LIMIT = 5  # number of similar weeks to return per query


def _build_embedding_text(
    temperature: float,
    humidity: float,
    crop_name: str,
    area_type: GrowingAreaType,
) -> str:
    """
    Construct a natural-language description of the sensor conditions.
    Richer text produces more meaningful embeddings than raw numbers alone.
    """
    return (
        f"Crop: {crop_name}. "
        f"Growing area type: {area_type.value.replace('_', ' ')}. "
        f"Temperature: {temperature:.1f}°F. "
        f"Humidity: {humidity:.1f}%. "
    )


async def generate_embedding(
    temperature: float,
    humidity: float,
    crop_name: str,
    area_type: GrowingAreaType,
) -> list[float]:
    """Generate a 1536-dim embedding vector for a sensor reading."""
    text = _build_embedding_text(temperature, humidity, crop_name, area_type)

    response = await _client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text,
    )
    return response.data[0].embedding


async def find_similar_weeks(
    growing_area_id: uuid.UUID,
    crop_id: uuid.UUID,
    embedding: list[float],
    db: AsyncSession,
    growing_area_plot_id: uuid.UUID | None = None,
    limit: int = SIMILARITY_LIMIT,
) -> list[dict]:
    # growing_area_plot_id is accepted for API consistency but not applied to the SQL
    # filter — historical_summaries rolls up at the area level. Plot-scoped vector
    # search is a v1.3 item once per-plot summary rows exist.
    """
    Find the most similar historical weeks for a given growing area and crop
    using pgvector cosine distance (<=>).

    Returns up to `limit` results ordered by similarity (closest first).
    Only returns rows that have an embedding — rows without one are skipped.
    """
    # pgvector cosine distance: 0.0 = identical, 2.0 = opposite
    query = text("""
        SELECT
            id,
            week_number,
            year,
            avg_temperature,
            min_temperature,
            max_temperature,
            avg_humidity,
            min_humidity,
            max_humidity,
            reading_count,
            embedding <=> CAST(:embedding AS vector) AS distance
        FROM historical_summaries
        WHERE
            growing_area_id = :growing_area_id
            AND crop_id = :crop_id
            AND embedding IS NOT NULL
        ORDER BY distance ASC
        LIMIT :limit
    """)

    result = await db.execute(
        query,
        {
            "embedding": str(embedding),
            "growing_area_id": str(growing_area_id),
            "crop_id": str(crop_id),
            "limit": limit,
        },
    )
    rows = result.mappings().all()

    return [
        {
            "id": str(row["id"]),
            "week_number": row["week_number"],
            "year": row["year"],
            "avg_temperature": row["avg_temperature"],
            "min_temperature": row["min_temperature"],
            "max_temperature": row["max_temperature"],
            "avg_humidity": row["avg_humidity"],
            "min_humidity": row["min_humidity"],
            "max_humidity": row["max_humidity"],
            "reading_count": row["reading_count"],
            "similarity_distance": round(row["distance"], 4),
        }
        for row in rows
    ]


async def upsert_historical_summary(
    growing_area_id: uuid.UUID,
    crop_id: uuid.UUID,
    week_number: int,
    year: int,
    avg_temperature: float,
    min_temperature: float,
    max_temperature: float,
    avg_humidity: float,
    min_humidity: float,
    max_humidity: float,
    reading_count: int,
    crop_name: str,
    area_type: GrowingAreaType,
    db: AsyncSession,
) -> HistoricalSummary:
    """
    Insert or update a weekly historical summary and regenerate its embedding.

    Called by the reading aggregation job after each week closes.
    The unique constraint on (growing_area_id, crop_id, week_number, year)
    ensures only one summary row exists per week.
    """
    result = await db.execute(
        select(HistoricalSummary).where(
            HistoricalSummary.growing_area_id == growing_area_id,
            HistoricalSummary.crop_id == crop_id,
            HistoricalSummary.week_number == week_number,
            HistoricalSummary.year == year,
        )
    )
    summary = result.scalar_one_or_none()

    embedding = await generate_embedding(
        avg_temperature, avg_humidity, crop_name, area_type
    )

    if summary is None:
        summary = HistoricalSummary(
            growing_area_id=growing_area_id,
            crop_id=crop_id,
            week_number=week_number,
            year=year,
            avg_temperature=avg_temperature,
            min_temperature=min_temperature,
            max_temperature=max_temperature,
            avg_humidity=avg_humidity,
            min_humidity=min_humidity,
            max_humidity=max_humidity,
            reading_count=reading_count,
            embedding=embedding,
        )
        db.add(summary)
    else:
        summary.avg_temperature = avg_temperature
        summary.min_temperature = min_temperature
        summary.max_temperature = max_temperature
        summary.avg_humidity = avg_humidity
        summary.min_humidity = min_humidity
        summary.max_humidity = max_humidity
        summary.reading_count = reading_count
        summary.embedding = embedding

    await db.commit()
    await db.refresh(summary)
    return summary
