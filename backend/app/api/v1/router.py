from fastapi import APIRouter

from app.api.v1 import (
    admin,
    alerts,
    auth,
    crops,
    customers,
    fields,
    invoices,
    sensor_readings,
    users,
    yield_plans,
)

router = APIRouter()

router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(users.router, prefix="/users", tags=["users"])
router.include_router(fields.router, prefix="/fields", tags=["fields"])
router.include_router(crops.router, prefix="/crops", tags=["crops"])
router.include_router(customers.router, prefix="/customers", tags=["customers"])
router.include_router(sensor_readings.router, prefix="/readings", tags=["readings"])
router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
router.include_router(yield_plans.router, prefix="/yield-plans", tags=["yield-plans"])
router.include_router(invoices.router, prefix="/invoices", tags=["invoices"])
router.include_router(admin.router, prefix="/admin", tags=["admin"])
