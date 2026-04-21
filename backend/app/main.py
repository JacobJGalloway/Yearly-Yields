import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    poll_task = asyncio.create_task(_poll_loop(settings.NWS_POLL_INTERVAL_HOURS))
    yield
    poll_task.cancel()
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
