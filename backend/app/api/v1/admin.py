"""
Admin endpoints — seed data and system management.
All endpoints restricted to owner role.

Seed order (enforced by FK constraints):
  1. customers      (no dependencies)
  2. crops          (depends on customers for default_harvest/transplant_customer_id)
  3. permissions + role_permissions (no dependencies)
  4. invoice_configs (depends on customers + existing growing_areas)
"""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import hash_password
from app.db.session import get_db
from app.dependencies import require_role
from app.models.alert import Alert
from app.models.crop import Crop, CropCycle, CropCycleStatus, YieldUnit
from app.models.customer import Customer
from app.models.field import GrowingArea, GrowingAreaPlot, GrowingAreaType
from app.models.invoice import Invoice
from app.models.invoice_config import InvoiceConfig
from app.models.sensor_reading import SensorReading
from app.models.yield_plan import YieldPlan
from app.models.user import Permission, RolePermission, User, UserRole
from app.schemas.user import UserCreate, UserRead

# ---------------------------------------------------------------------------
# Demo reset — greenhouse plot offsets (days before today for planted_at).
# Open fields use calendar-realistic plant dates instead.
# ---------------------------------------------------------------------------

# Greenhouse: artificial offsets to always show active phases regardless of run date.
_GH_OFFSETS: dict[str, int] = {
    "Morristown GH1 — Bay A": 155,  # tomatoes  — harvest phase, day 14
    "Morristown GH1 — Bay B": 100,  # tomatoes  — growing phase
    "Morristown GH2 — Bay A": 165,  # tomatoes  — harvest phase, day 24
    "Morristown GH2 — Bay B": 75,   # tomatoes  — growing phase
    "Morristown GH2 — Bay C": 61,   # arugula   — harvest day 12/15, terminal harvest ready
}

# Open fields: (month, day) plant date — honest calendar; fallow if today < plant date.
_FIELD_PLANT_DATES: dict[str, tuple[int, int]] = {
    "Jax IL — Corn Field":    (5, 1),   # May 1  — IL corn planting window
    "Jax IL — Soybean Field": (5, 10),  # May 10 — IL soybean planting window
}

_DEMO_AREA_NAMES = list(_GH_OFFSETS.keys()) + list(_FIELD_PLANT_DATES.keys())

router = APIRouter()

PERMISSIONS = [
    ("areas:read", "Read growing areas"),
    ("areas:write", "Create and update growing areas"),
    ("crops:read", "Read crops and crop cycles"),
    ("crops:write", "Create and update crop cycles"),
    ("sensor_readings:read", "Read sensor readings"),
    ("sensor_readings:create", "Submit sensor readings"),
    ("alerts:read", "Read alerts"),
    ("alerts:manage", "Manage alert state"),
    ("yield_plans:read", "Read yield plans"),
    ("yield_plans:create", "Create yield plans"),
    ("invoices:read", "Read invoices"),
    ("invoices:create", "Create invoices"),
    ("invoices:manage", "Manage invoice status"),
    ("customers:read", "Read customers"),
    ("customers:manage", "Manage customers"),
    ("users:manage", "Manage users"),
    ("owner:all", "Wildcard — owner bypasses all permission checks"),
]

ROLE_PERMISSION_MAP = {
    UserRole.owner: ["owner:all"],
    UserRole.farmer: [
        "areas:read", "crops:read", "crops:write",
        "sensor_readings:read", "sensor_readings:create",
        "alerts:read", "yield_plans:read", "yield_plans:create",
        "invoices:read", "invoices:create", "customers:read",
    ],
    UserRole.hired_hand: ["areas:read", "crops:write"],
}


@router.post("/bootstrap", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def bootstrap_owner(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    """
    Create the first owner user. No auth required.
    Returns 409 if any owner already exists — use /users/ after that.
    """
    existing = await db.execute(select(User).where(User.role == UserRole.owner).limit(1))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Owner already exists")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=UserRole.owner,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserRead.model_validate(user)


@router.post("/seed", status_code=status.HTTP_200_OK)
async def seed_data(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.owner)),
) -> dict:
    """
    Idempotent seed endpoint — safe to call multiple times.
    Seeds customers, crops, permissions, and role_permissions.
    """
    seeded = []

    # 1. Customers
    customers = {
        "Global Harvest": "jacobjgalloway@gmail.com",
        "National Nourish": "jacobjgalloway@gmail.com",
        "Prairie Start Nursery": "jacobjgalloway@gmail.com",
    }
    customer_map = {}
    for name, email in customers.items():
        result = await db.execute(select(Customer).where(Customer.name == name))
        customer = result.scalar_one_or_none()
        if customer is None:
            # Seed customers under the first owner user found
            owner_result = await db.execute(
                select(User).where(User.role == UserRole.owner).limit(1)
            )
            owner = owner_result.scalar_one_or_none()
            if owner is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="No owner user found. Create an owner user before seeding.",
                )
            customer = Customer(owner_id=owner.id, name=name, email=email)
            db.add(customer)
            await db.flush()
            seeded.append(f"customer:{name}")
        customer_map[name] = customer.id

    # 2. Crops
    crops = [
        {
            "name": "corn",
            "greenhouse_compatible": False,
            "typical_cycle_days": 120,
            "harvest_customer": "Global Harvest",
            "transplant_customer": None,
            "yield_unit": YieldUnit.bushels,
        },
        {
            "name": "soybeans",
            "greenhouse_compatible": False,
            "typical_cycle_days": 100,
            "harvest_customer": "Global Harvest",
            "transplant_customer": None,
            "yield_unit": YieldUnit.bushels,
        },
        {
            "name": "tomatoes",
            "greenhouse_compatible": True,
            "typical_cycle_days": 90,
            "harvest_customer": "National Nourish",
            "transplant_customer": "Prairie Start Nursery",
            "yield_unit": YieldUnit.lbs,
        },
        {
            "name": "arugula_lettuce",
            "greenhouse_compatible": True,
            "typical_cycle_days": 40,
            "harvest_customer": "National Nourish",
            "transplant_customer": "Prairie Start Nursery",
            "yield_unit": YieldUnit.lbs,
        },
    ]
    for crop_data in crops:
        result = await db.execute(select(Crop).where(Crop.name == crop_data["name"]))
        if result.scalar_one_or_none() is None:
            crop = Crop(
                name=crop_data["name"],
                greenhouse_compatible=crop_data["greenhouse_compatible"],
                typical_cycle_days=crop_data["typical_cycle_days"],
                default_harvest_customer_id=customer_map.get(crop_data["harvest_customer"]),
                default_transplant_customer_id=customer_map.get(crop_data["transplant_customer"]),
            )
            db.add(crop)
            seeded.append(f"crop:{crop_data['name']}")

    # 3. Permissions
    perm_map = {}
    for name, description in PERMISSIONS:
        result = await db.execute(select(Permission).where(Permission.name == name))
        perm = result.scalar_one_or_none()
        if perm is None:
            perm = Permission(name=name, description=description)
            db.add(perm)
            await db.flush()
            seeded.append(f"permission:{name}")
        perm_map[name] = perm.id

    # 4. Role permissions
    for role, perm_names in ROLE_PERMISSION_MAP.items():
        for perm_name in perm_names:
            perm_id = perm_map.get(perm_name)
            if perm_id is None:
                continue
            result = await db.execute(
                select(RolePermission).where(
                    RolePermission.role == role,
                    RolePermission.permission_id == perm_id,
                )
            )
            if result.scalar_one_or_none() is None:
                db.add(RolePermission(role=role, permission_id=perm_id))
                seeded.append(f"role_permission:{role.value}:{perm_name}")

    # 5. InvoiceConfig — one per growing area, defaults by area type
    areas_result = await db.execute(select(GrowingArea))
    areas = areas_result.scalars().all()
    for area in areas:
        existing = await db.execute(
            select(InvoiceConfig).where(InvoiceConfig.growing_area_id == area.id)
        )
        if existing.scalar_one_or_none() is None:
            if area.area_type == GrowingAreaType.open_field:
                harvest_cid = customer_map.get("Global Harvest")
                transplant_cid = None
            else:
                harvest_cid = customer_map.get("National Nourish")
                transplant_cid = customer_map.get("Prairie Start Nursery")

            db.add(InvoiceConfig(
                growing_area_id=area.id,
                harvest_customer_id=harvest_cid,
                transplant_customer_id=transplant_cid,
            ))
            seeded.append(f"invoice_config:{area.name}")

    await db.commit()
    return {"seeded": seeded, "message": "Seed complete" if seeded else "Nothing to seed — already up to date"}


@router.post("/demo-reset", status_code=status.HTTP_200_OK)
async def demo_reset(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.owner)),
) -> dict:
    """
    Wipe and rebuild demo crop cycles with planted_at recalculated relative to today.

    Greenhouse plots carry artificial offsets so they always appear at varied
    active phases regardless of run date. Open fields use calendar-realistic
    plant dates and appear fallow if run before planting season.

    Only active cycles on the 7 demo areas are deleted. Historical (harvested)
    cycles, sensor readings, alerts, and all other data are untouched.

    # Production safety — disabled via APP_ENV, not auth alone.
    # To re-enable in production, change APP_ENV in the environment — never
    # remove this check from the code.
    """
    if settings.APP_ENV == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo reset is disabled in production.",
        )

    today = date.today()

    # --- Resolve demo growing areas ----------------------------------------
    area_result = await db.execute(
        select(GrowingArea).where(GrowingArea.name.in_(_DEMO_AREA_NAMES))
    )
    areas = {a.name: a for a in area_result.scalars().all()}
    missing = [n for n in _DEMO_AREA_NAMES if n not in areas]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Demo areas not found — run /seed first: {missing}",
        )

    # --- Resolve crops by name ----------------------------------------------
    crop_result = await db.execute(select(Crop))
    crops = {c.name: c for c in crop_result.scalars().all()}

    # --- Delete current-season cycles (all statuses) for demo areas ---------
    # Historical cycles (2022-2024) have a different season_year and are untouched.
    area_ids = [a.id for a in areas.values()]
    cycle_result = await db.execute(
        select(CropCycle).where(
            CropCycle.growing_area_id.in_(area_ids),
            CropCycle.season_year >= today.year,
        )
    )
    active_cycles = cycle_result.scalars().all()
    active_cycle_ids = [c.id for c in active_cycles]

    if active_cycle_ids:
        # NOT NULL FKs — must delete before cycle delete
        await db.execute(
            delete(Invoice).where(Invoice.crop_cycle_id.in_(active_cycle_ids))
        )
        await db.execute(
            delete(YieldPlan).where(YieldPlan.crop_cycle_id.in_(active_cycle_ids))
        )
        # Nullable FKs — null out to preserve the readings/alerts, then delete cycles
        await db.execute(
            update(SensorReading)
            .where(SensorReading.crop_cycle_id.in_(active_cycle_ids))
            .values(crop_cycle_id=None)
        )
        await db.execute(
            update(Alert)
            .where(Alert.crop_cycle_id.in_(active_cycle_ids))
            .values(crop_cycle_id=None)
        )
        await db.execute(
            delete(CropCycle).where(CropCycle.id.in_(active_cycle_ids))
        )

    # --- Resolve sentinel plots (plot_index=0) per area ---------------------
    plot_result = await db.execute(
        select(GrowingAreaPlot).where(
            GrowingAreaPlot.growing_area_id.in_(area_ids),
            GrowingAreaPlot.plot_index == 0,
        )
    )
    sentinel_plots = {p.growing_area_id: p for p in plot_result.scalars().all()}

    # --- Rebuild cycles ------------------------------------------------------
    created: list[dict] = []

    # Greenhouse plots — date-relative offsets
    gh_crop_map = {
        "Morristown GH1 — Bay A": "tomatoes",
        "Morristown GH1 — Bay B": "tomatoes",
        "Morristown GH2 — Bay A": "tomatoes",
        "Morristown GH2 — Bay B": "tomatoes",
        "Morristown GH2 — Bay C": "arugula_lettuce",
    }
    for area_name, offset_days in _GH_OFFSETS.items():
        area = areas[area_name]
        plot = sentinel_plots.get(area.id)
        if plot is None:
            continue
        crop_name = gh_crop_map[area_name]
        crop = crops.get(crop_name)
        if crop is None:
            continue

        planted_at = today - timedelta(days=offset_days)

        if crop_name == "arugula_lettuce":
            forecasted_end = planted_at + timedelta(days=64)
            yield_unit = YieldUnit.lbs
        else:
            # Tomatoes: seasonal GH1 ends Nov 1 current year; year-round GH2 ends 540 days out
            if "GH1" in area_name:
                forecasted_end = date(planted_at.year, 11, 1)
            else:
                forecasted_end = planted_at + timedelta(days=540)
            yield_unit = YieldUnit.lbs

        cycle = CropCycle(
            growing_area_id=area.id,
            growing_area_plot_id=plot.id,
            crop_id=crop.id,
            season_year=planted_at.year,
            cycle_number=1,
            planted_at=planted_at,
            forecasted_end_date=forecasted_end,
            yield_unit=yield_unit,
            status=CropCycleStatus.active,
        )
        db.add(cycle)
        created.append({
            "area": area_name,
            "crop": crop_name,
            "planted_at": str(planted_at),
            "forecasted_end": str(forecasted_end),
            "days_in_cycle": offset_days,
        })

    # Open fields — calendar-honest plant dates
    field_crop_map = {
        "Jax IL — Corn Field":    ("corn",     YieldUnit.bushels, (10, 15)),
        "Jax IL — Soybean Field": ("soybeans", YieldUnit.bushels, (10, 22)),
    }
    for area_name, (month, day) in _FIELD_PLANT_DATES.items():
        plant_date = date(today.year, month, day)
        if today < plant_date:
            # Before planting season — leave fallow, no active cycle
            created.append({"area": area_name, "status": "fallow — before planting season"})
            continue

        area = areas[area_name]
        plot = sentinel_plots.get(area.id)
        if plot is None:
            continue
        crop_name, yield_unit, (end_month, end_day) = field_crop_map[area_name]
        crop = crops.get(crop_name)
        if crop is None:
            continue

        forecasted_end = date(today.year, end_month, end_day)
        cycle = CropCycle(
            growing_area_id=area.id,
            growing_area_plot_id=plot.id,
            crop_id=crop.id,
            season_year=today.year,
            cycle_number=1,
            planted_at=plant_date,
            forecasted_end_date=forecasted_end,
            yield_unit=yield_unit,
            status=CropCycleStatus.active,
        )
        db.add(cycle)
        created.append({
            "area": area_name,
            "crop": crop_name,
            "planted_at": str(plant_date),
            "forecasted_end": str(forecasted_end),
            "days_in_cycle": (today - plant_date).days,
        })

    await db.commit()
    return {
        "message": "Demo reset complete",
        "deleted_active_cycles": len(active_cycle_ids),
        "created_cycles": created,
    }
