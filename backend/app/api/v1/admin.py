"""
Admin endpoints — seed data and system management.
All endpoints restricted to owner role.

Seed order (enforced by FK constraints):
  1. customers      (no dependencies)
  2. crops          (depends on customers for default_harvest/transplant_customer_id)
  3. permissions + role_permissions (no dependencies)
  4. invoice_configs (depends on customers + existing growing_areas)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.session import get_db
from app.dependencies import require_role
from app.models.crop import Crop, YieldUnit
from app.models.customer import Customer
from app.models.field import GrowingArea, GrowingAreaType
from app.models.invoice_config import InvoiceConfig
from app.models.user import Permission, RolePermission, User, UserRole
from app.schemas.user import UserCreate, UserRead

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
