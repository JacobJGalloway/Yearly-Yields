"""
Synthetic sensor backfill — Q2 2026 (Apr 1 → today) for all active growing areas.

Generates realistic temperature/humidity readings at 4-hour intervals based on:
  - Area type (open_field vs dwc_greenhouse)
  - NWS station location (KMTO = Jacksonville IL, KMOR = Morristown TN)
  - Time of day (sine curve: cool morning, warm afternoon, cool night)
  - Day-to-day weather variation (seeded random walk)

All readings inserted with:
  - reading_source = fiot  (synthetic / pre-assessed)
  - assessment_status = normal  (no agent loop triggered)
  - ph / wind_speed: null (not simulated)

Safe to re-run — skips any area+timestamp that already exists in sensor_readings.

Run from backend/ with Docker running (dev server can be up or down):
    python seed_sensor_backfill.py
"""

import asyncio
import math
import random
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select, and_

from app.db.session import AsyncSessionLocal
from app.models.field import GrowingArea, GrowingAreaType
from app.models.sensor_reading import AssessmentStatus, ReadingSource, SensorReading

START_DATE = date(2026, 4, 1)
READINGS_PER_DAY = 6          # every 4 hours: 0, 4, 8, 12, 16, 20 UTC

# Baseline April climate per NWS station (avg daily high / avg daily low °F, avg humidity %)
STATION_CLIMATE = {
    "KMTO": {"high": 62.0, "low": 42.0, "humidity": 62.0},   # Jacksonville IL — cool spring
    "KMOR": {"high": 70.0, "low": 50.0, "humidity": 68.0},   # Morristown TN — warmer spring
}

# Greenhouse overrides — climate-controlled regardless of station
GREENHOUSE_CLIMATE = {"high": 78.0, "low": 65.0, "humidity": 74.0}

# How much day-to-day temp can drift (random walk ±degrees)
DAILY_DRIFT_SCALE = 4.0
# Random noise on each individual reading (±degrees)
READING_NOISE = 1.2


def _sine_fraction(hour_utc: int) -> float:
    """Returns 0.0 (coolest, ~5am local) → 1.0 (warmest, ~2pm local), sine-shaped."""
    # Approximate local solar noon at ~17 UTC for central US, ~16 UTC for eastern TN
    peak_utc = 17
    radians = math.pi * (hour_utc - (peak_utc - 12)) / 12
    return max(0.0, math.sin(radians))


def _generate_readings(
    area_id,
    station_id: str | None,
    area_type: GrowingAreaType,
    existing_timestamps: set[datetime],
    rng: random.Random,
) -> list[SensorReading]:
    is_greenhouse = area_type == GrowingAreaType.dwc_greenhouse

    if is_greenhouse:
        climate = GREENHOUSE_CLIMATE
    else:
        climate = STATION_CLIMATE.get(station_id or "", STATION_CLIMATE["KMTO"])

    high = climate["high"]
    low = climate["low"]
    base_humidity = climate["humidity"]

    readings: list[SensorReading] = []
    now = datetime.now(timezone.utc)
    daily_drift = 0.0

    current_date = START_DATE
    while current_date <= date.today():
        # Day-to-day random walk — greenhouses drift less
        drift_scale = DAILY_DRIFT_SCALE * (0.3 if is_greenhouse else 1.0)
        daily_drift = max(-12.0, min(12.0, daily_drift + rng.gauss(0, drift_scale)))

        for slot in range(READINGS_PER_DAY):
            hour_utc = (slot * 24) // READINGS_PER_DAY  # 0, 4, 8, 12, 16, 20
            dt = datetime(
                current_date.year, current_date.month, current_date.day,
                hour_utc, rng.randint(0, 59), 0, tzinfo=timezone.utc
            )

            if dt >= now:
                break
            if dt in existing_timestamps:
                continue

            frac = _sine_fraction(hour_utc)
            temp = low + (high - low) * frac + daily_drift + rng.gauss(0, READING_NOISE)
            temp = round(max(low - 15, min(high + 15, temp)), 1)

            # Humidity inversely correlated with temperature (higher at night)
            hum = base_humidity - 10.0 * frac + rng.gauss(0, 4.0)
            hum = round(max(20.0, min(98.0, hum)), 1)

            readings.append(SensorReading(
                growing_area_id=area_id,
                temperature=temp,
                humidity=hum,
                reading_source=ReadingSource.fiot,
                read_at=dt,
                received_at=dt,
                assessment_status=AssessmentStatus.normal,
                assessment_summary="Synthetic backfill — pre-assessed normal.",
            ))

        current_date += timedelta(days=1)

    return readings


async def main() -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(GrowingArea).where(GrowingArea.is_active.is_(True))
        )
        areas = result.scalars().all()

        if not areas:
            print("No active growing areas found.")
            return

        total_inserted = 0

        for area in areas:
            # Load existing timestamps for this area to avoid duplicates
            existing_result = await session.execute(
                select(SensorReading.read_at).where(
                    SensorReading.growing_area_id == area.id
                )
            )
            existing_timestamps = {row[0].replace(tzinfo=timezone.utc) if row[0].tzinfo is None else row[0]
                                    for row in existing_result.all()}

            rng = random.Random(str(area.id))  # deterministic per area — re-runnable
            readings = _generate_readings(
                area.id, area.nws_station_id, area.area_type, existing_timestamps, rng
            )

            for r in readings:
                session.add(r)

            await session.flush()
            print(f"  {area.name} ({area.area_type.value}): {len(readings)} readings inserted")
            total_inserted += len(readings)

        await session.commit()
        print(f"\nDone. {total_inserted} total readings inserted across {len(areas)} areas.")


if __name__ == "__main__":
    asyncio.run(main())
