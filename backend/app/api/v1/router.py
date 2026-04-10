from fastapi import APIRouter

from app.api.v1 import auth, users, fields, sensor_readings, alerts, yield_plans, admin

router = APIRouter()

router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(users.router, prefix="/users", tags=["users"])
router.include_router(fields.router, prefix="/fields", tags=["fields"])
router.include_router(sensor_readings.router, prefix="/readings", tags=["readings"])
router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
router.include_router(yield_plans.router, prefix="/yield-plans", tags=["yield-plans"])
router.include_router(admin.router, prefix="/admin", tags=["admin"])
