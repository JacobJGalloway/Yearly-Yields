import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import delete, select

from app.api.v1.router import router as v1_router
from app.config import settings
from app.core.logging import configure_logging
from app.core.security import create_access_token, create_refresh_token, decode_access_payload
from app.db.session import AsyncSessionLocal, engine
from app.models.field import GrowingArea, GrowingAreaType
from app.models.sensor_reading import AssessmentStatus, ReadingSource, SensorReading

logger = logging.getLogger(__name__)

configure_logging()

_is_dev = settings.APP_ENV == "development"

async def _run_nws_poll() -> None:
    from app.agent.loop import run_anomaly_check
    from app.services import nws_service

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(GrowingArea).where(
                GrowingArea.is_active.is_(True),
                GrowingArea.nws_station_id.isnot(None),
            )
        )
        areas = result.scalars().all()

    for area in areas:
        try:
            if area.area_type == GrowingAreaType.dwc_greenhouse:
                raw = await nws_service.simulate_greenhouse_reading(area)
                source = ReadingSource.fiot
            else:
                raw = await nws_service.poll_latest(area.nws_station_id)
                source = ReadingSource.nws

            if raw is None:
                continue

            now = datetime.now(timezone.utc)
            reading_id = None

            async with AsyncSessionLocal() as db:
                existing = await db.execute(
                    select(SensorReading.id).where(
                        SensorReading.growing_area_id == area.id,
                        SensorReading.read_at == raw["observed_at"],
                    )
                )
                if existing.scalar_one_or_none() is not None:
                    continue

                reading = SensorReading(
                    growing_area_id=area.id,
                    temperature=raw.get("temp_f"),
                    humidity=raw.get("humidity"),
                    wind_speed=raw.get("wind_speed"),
                    wind_direction=raw.get("wind_direction"),
                    reading_source=source,
                    read_at=raw["observed_at"],
                    received_at=now,
                    assessment_status=AssessmentStatus.pending,
                )
                db.add(reading)
                await db.commit()
                await db.refresh(reading)
                reading_id = reading.id


            async with AsyncSessionLocal() as db:
                await run_anomaly_check(reading_id, db)

        except Exception:
            logger.exception("NWS poll failed for area %s (%s)", area.name, area.id)


async def _poll_loop(interval_hours: int) -> None:
    while True:
        await _run_nws_poll()
        await asyncio.sleep(interval_hours * 3600)


async def _run_fiot_poll() -> None:
    from app.agent.loop import run_anomaly_check
    from app.services import nws_service

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(GrowingArea).where(
                GrowingArea.is_active.is_(True),
                GrowingArea.area_type == GrowingAreaType.dwc_greenhouse,
            )
        )
        areas = result.scalars().all()

    for area in areas:
        try:
            raw = await nws_service.simulate_greenhouse_reading(area)
            if raw is None:
                continue

            now = datetime.now(timezone.utc)
            reading_id = None

            async with AsyncSessionLocal() as db:
                reading = SensorReading(
                    growing_area_id=area.id,
                    temperature=raw.get("temp_f"),
                    humidity=raw.get("humidity"),
                    reading_source=ReadingSource.fiot,
                    read_at=now,
                    received_at=now,
                    assessment_status=AssessmentStatus.pending,
                )
                db.add(reading)
                await db.commit()
                await db.refresh(reading)
                reading_id = reading.id

            async with AsyncSessionLocal() as db:
                await run_anomaly_check(reading_id, db)

        except Exception:
            logger.exception("fIoT poll failed for area %s (%s)", area.name, area.id)


async def _fiot_loop(interval_hours: float) -> None:
    while True:
        await _run_fiot_poll()
        await asyncio.sleep(interval_hours * 3600)


async def _purge_old_readings() -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.DATA_RETENTION_DAYS)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            delete(SensorReading).where(SensorReading.read_at < cutoff)
        )
        await db.commit()
    logger.info("Purged %d sensor readings older than %s", result.rowcount, cutoff.date())


def _should_summarize_today() -> bool:
    return datetime.now(timezone.utc).strftime("%m-%d") in settings.SUMMARIZATION_DATES


async def _summarize_old_readings() -> None:
    from sqlalchemy import text
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.models.weekly_sensor_summary import WeeklySensorSummary

    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.DAILY_RETENTION_DAYS)

    agg_sql = text("""
        SELECT
            growing_area_id,
            ((read_at AT TIME ZONE 'UTC')::date
                - EXTRACT(DOW FROM read_at AT TIME ZONE 'UTC')::int) AS week_start,
            ((read_at AT TIME ZONE 'UTC')::date
                - EXTRACT(DOW FROM read_at AT TIME ZONE 'UTC')::int + 6) AS week_end,
            AVG(temperature) AS avg_temperature,
            AVG(humidity)    AS avg_humidity,
            AVG(ph)          AS avg_ph,
            AVG(wind_speed)  AS avg_wind_speed,
            CASE
                WHEN COUNT(wind_direction) FILTER (WHERE wind_direction IS NOT NULL) = 0 THEN NULL
                ELSE MOD(
                    CAST(DEGREES(ATAN2(
                        AVG(SIN(RADIANS(wind_direction))),
                        AVG(COS(RADIANS(wind_direction)))
                    )) + 360 AS numeric),
                    360
                )
            END AS avg_wind_direction,
            COUNT(*) AS reading_count
        FROM sensor_readings
        WHERE read_at < :cutoff
        GROUP BY growing_area_id, week_start
        ORDER BY growing_area_id, week_start
    """)

    async with AsyncSessionLocal() as db:
        result = await db.execute(agg_sql, {"cutoff": cutoff})
        rows = result.fetchall()

        if not rows:
            logger.info("No sensor readings to summarize before %s", cutoff.date())
            return

        now = datetime.now(timezone.utc)
        stmt = (
            pg_insert(WeeklySensorSummary)
            .values([
                {
                    "growing_area_id": row.growing_area_id,
                    "week_start": row.week_start,
                    "week_end": row.week_end,
                    "avg_temperature": row.avg_temperature,
                    "avg_humidity": row.avg_humidity,
                    "avg_ph": row.avg_ph,
                    "avg_wind_speed": row.avg_wind_speed,
                    "avg_wind_direction": (
                        float(row.avg_wind_direction) if row.avg_wind_direction is not None else None
                    ),
                    "reading_count": row.reading_count,
                    "created_at": now,
                }
                for row in rows
            ])
            .on_conflict_do_nothing(constraint="uq_weekly_summary_area_week")
        )
        await db.execute(stmt)

        del_result = await db.execute(
            delete(SensorReading).where(SensorReading.read_at < cutoff)
        )
        await db.commit()

    logger.info(
        "Summarized %d weeks into weekly_sensor_summaries, deleted %d daily readings older than %s",
        len(rows), del_result.rowcount, cutoff.date(),
    )


async def _phase_check_loop(interval_hours: int) -> None:
    from app.services.phase_alert_service import run_phase_check
    await run_phase_check()
    while True:
        await asyncio.sleep(interval_hours * 3600)
        try:
            await run_phase_check()
        except Exception:
            logger.exception("Daily phase check failed")


async def _purge_loop() -> None:
    while True:
        try:
            await _purge_old_readings()
        except Exception:
            logger.exception("Nightly sensor reading purge failed")
        if _should_summarize_today():
            try:
                await _summarize_old_readings()
            except Exception:
                logger.exception("Quarterly sensor reading summarization failed")
        await asyncio.sleep(settings.PURGE_INTERVAL_HOURS * 3600)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services.catchup_service import run_system_backfill
    backfill_task = asyncio.create_task(run_system_backfill())
    poll_task = asyncio.create_task(_poll_loop(settings.NWS_POLL_INTERVAL_HOURS))
    purge_task = asyncio.create_task(_purge_loop())
    fiot_task = asyncio.create_task(_fiot_loop(settings.FIOT_POLL_INTERVAL_HOURS))
    phase_task = asyncio.create_task(_phase_check_loop(settings.PHASE_CHECK_INTERVAL_HOURS))
    yield
    backfill_task.cancel()
    poll_task.cancel()
    purge_task.cancel()
    fiot_task.cancel()
    phase_task.cancel()
    await engine.dispose()


app = FastAPI(
    title="Yearly Yields API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if _is_dev else None,
    redoc_url="/redoc" if _is_dev else None,
    openapi_url="/openapi.json" if _is_dev else None,
    swagger_ui_init_oauth={},
)

_TOKEN_ROTATION_HEADERS = ["X-New-Access-Token", "X-New-Refresh-Token"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=_TOKEN_ROTATION_HEADERS,
)


@app.middleware("http")
async def rotate_access_token(request: Request, call_next):
    response = await call_next(request)
    threshold = settings.TOKEN_ROTATION_THRESHOLD_SECONDS
    if threshold <= 0:
        return response
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return response
    try:
        payload = decode_access_payload(auth[7:])
        if payload is None:
            return response
        iat = payload.get("iat", 0)
        iat_ts = iat.timestamp() if hasattr(iat, "timestamp") else float(iat)
        if time.time() - iat_ts > threshold:
            user_id: str = payload["sub"]
            response.headers["X-New-Access-Token"] = create_access_token(user_id)
            response.headers["X-New-Refresh-Token"] = create_refresh_token(user_id)
    except Exception:
        pass
    return response


app.include_router(v1_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
