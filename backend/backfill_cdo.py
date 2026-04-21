"""
One-time CDO historical backfill script.

Fetches NOAA CDO daily summaries for KMOR (Morristown TN) and KMTO (Jacksonville IL)
from 2023-04-19 to today, then inserts them as sensor_readings for all growing areas
assigned to each NWS station.

Run from backend/ with Docker running (dev server can be up or down):
    python backfill_cdo.py

Requires NOAA_CDO_TOKEN in .env. Safe to re-run — skips dates already in sensor_readings.
CDO returns one record per day; each is inserted with read_at = noon UTC on that date,
source = nws, assessment_status = normal (no agent loop for historical data).
Humidity uses RHAV when available; 50.0 placeholder otherwise (pending task #20 to make nullable).
"""

import asyncio
import sys
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select, and_

from app.config import settings
from app.db.session import AsyncSessionLocal
from app.models.field import GrowingArea
from app.models.sensor_reading import AssessmentStatus, ReadingSource, SensorReading
from app.services import nws_service

START_DATE = date(2023, 4, 19)
END_DATE = date.today()

# Maps NWS station IDs to GHCND station IDs (looked up via CDO stations API)
GHCND_STATION_MAP = {
    "KMOR": "USC00406271",  # Morristown Radio WCRK, TN — datacoverage=1, 1982–present
    "KMTO": "USC00114442",  # Jacksonville 2 E, IL — datacoverage=1, 1895–present
}


def _year_chunks(start: date, end: date):
    """Yield (chunk_start, chunk_end) pairs spanning at most 1 year each."""
    current = start
    while current < end:
        chunk_end = min(date(current.year + 1, current.month, current.day) - timedelta(days=1), end)
        yield current, chunk_end
        current = chunk_end + timedelta(days=1)


async def existing_dates(session, growing_area_id: str) -> set[str]:
    result = await session.execute(
        select(SensorReading.read_at).where(
            and_(
                SensorReading.growing_area_id == growing_area_id,
                SensorReading.reading_source == ReadingSource.nws,
            )
        )
    )
    return {row[0].strftime("%Y-%m-%d") for row in result.all()}


async def backfill_station(session, nws_id: str, ghcnd_id: str, areas: list) -> None:
    all_records: list[dict] = []

    for chunk_start, chunk_end in _year_chunks(START_DATE, END_DATE):
        print(f"    Fetching {chunk_start} → {chunk_end}...")
        records = await nws_service.backfill(ghcnd_id, chunk_start, chunk_end)
        all_records.extend(records)

    if not all_records:
        print(f"  No data returned for {nws_id} ({ghcnd_id}) — check token and station ID.")
        return

    print(f"  Got {len(all_records)} daily records total.")

    for area in areas:
        area_id = str(area.id)
        existing = await existing_dates(session, area_id)
        inserted = 0
        skipped = 0

        for rec in all_records:
            dt: datetime = rec["observed_at"]
            date_key = dt.strftime("%Y-%m-%d")

            if date_key in existing:
                skipped += 1
                continue

            humidity_note = " Humidity is estimated (RHAV unavailable)." if rec.get("humidity_estimated") else ""
            session.add(SensorReading(
                growing_area_id=area.id,
                temperature=rec["temp_f"],
                humidity=rec["humidity"],
                wind_speed=rec.get("wind_speed"),
                wind_direction=rec.get("wind_direction"),
                reading_source=ReadingSource.nws,
                read_at=dt,
                received_at=datetime.now(timezone.utc),
                assessment_status=AssessmentStatus.normal,
                assessment_summary=f"CDO historical backfill — pre-assessed normal.{humidity_note}",
            ))
            inserted += 1

        await session.flush()
        print(f"    {area.name}: {inserted} inserted, {skipped} skipped.")

    await session.commit()


async def main() -> None:
    if not settings.NOAA_CDO_TOKEN:
        print("ERROR: NOAA_CDO_TOKEN is not set in .env", file=sys.stderr)
        sys.exit(1)

    async with AsyncSessionLocal() as session:
        for nws_id, ghcnd_id in GHCND_STATION_MAP.items():
            result = await session.execute(
                select(GrowingArea).where(GrowingArea.nws_station_id == nws_id)
            )
            areas = result.scalars().all()

            if not areas:
                print(f"\nNo growing areas found for station {nws_id} — skipping.")
                continue

            print(f"\nStation {nws_id} ({ghcnd_id}) — {len(areas)} area(s): {[a.name for a in areas]}")
            await backfill_station(session, nws_id, ghcnd_id, areas)

    print("\nBackfill complete.")


if __name__ == "__main__":
    asyncio.run(main())
