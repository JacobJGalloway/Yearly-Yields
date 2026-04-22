"""
Seed historical harvested crop cycles for Jacksonville IL open fields.

Creates 2022, 2023, and 2024 corn and soybean cycles with realistic
USDA-aligned yields for Morgan County, IL. All cycles are seeded directly
as harvested — no anomaly detection is triggered (sensor readings are not
created; only CropCycle records).

Run from backend/ with the dev server running:
    python seed_historical_harvests.py

Safe to re-run — existing cycles are skipped by (area, season_year, cycle_number).
"""

import os
import sys

import httpx

BASE_URL = "http://127.0.0.1:8000/api/v1"

# Realistic Morgan County, IL yield estimates (USDA NASS aligned)
# corn bu/acre, soybeans bu/acre
CORN_YIELDS = {2022: 185.0, 2023: 172.0, 2024: 198.0}
SOYBEAN_YIELDS = {2022: 51.0, 2023: 53.0, 2024: 57.0}

# Typical Illinois planting / harvest windows
CORN_PLANT_MONTH = "05-01"
CORN_HARVEST_MONTH = "10-15"
SOYBEAN_PLANT_MONTH = "05-10"
SOYBEAN_HARVEST_MONTH = "10-22"


def _login(email: str, password: str) -> str:
    resp = httpx.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password})
    resp.raise_for_status()
    return resp.json()["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _find_crop_id(token: str, name: str) -> str:
    resp = httpx.get(f"{BASE_URL}/crops/", headers=_headers(token))
    resp.raise_for_status()
    match = next((c for c in resp.json() if c["name"] == name), None)
    if match is None:
        raise ValueError(f"Crop '{name}' not found.")
    return match["id"]


def _list_cycles(token: str, area_id: str) -> list[dict]:
    resp = httpx.get(
        f"{BASE_URL}/crops/cycles",
        params={"growing_area_id": area_id},
        headers=_headers(token),
    )
    resp.raise_for_status()
    return resp.json()


def _create_and_harvest(
    token: str,
    area_id: str,
    crop_id: str,
    season_year: int,
    cycle_number: int,
    planted_at: str,
    harvested_at: str,
    actual_yield: float,
    target_yield: float,
    yield_unit: str,
) -> None:
    existing = _list_cycles(token, area_id)
    dupe = next(
        (c for c in existing
         if c["season_year"] == season_year and c["cycle_number"] == cycle_number),
        None,
    )
    if dupe:
        print(f"      Skipped (exists): {season_year} cycle {cycle_number} → {dupe['id']}")
        return

    # Create as active
    resp = httpx.post(
        f"{BASE_URL}/crops/cycles",
        json={
            "growing_area_id": area_id,
            "crop_id": crop_id,
            "season_year": season_year,
            "cycle_number": cycle_number,
            "planted_at": planted_at,
            "harvested_at": harvested_at,
            "yield_unit": yield_unit,
            "target_yield": target_yield,
        },
        headers=_headers(token),
    )
    resp.raise_for_status()
    cycle_id = resp.json()["id"]

    # Transition to harvested with actual yield
    resp = httpx.patch(
        f"{BASE_URL}/crops/cycles/{cycle_id}",
        json={
            "status": "harvested",
            "actual_yield": actual_yield,
            "harvested_at": harvested_at,
        },
        headers=_headers(token),
    )
    resp.raise_for_status()
    print(f"      Created + harvested: {season_year} cycle {cycle_number} → {actual_yield} {yield_unit} ({cycle_id})")


def main() -> None:
    email = os.environ.get("OWNER_EMAIL") or input("Owner email: ")
    password = os.environ.get("OWNER_PASSWORD") or input("Owner password: ")

    print("Logging in...")
    token = _login(email, password)

    print("Resolving crop IDs...")
    corn_id = _find_crop_id(token, "corn")
    soybean_id = _find_crop_id(token, "soybeans")

    print("Fetching growing areas...")
    resp = httpx.get(f"{BASE_URL}/fields/", headers=_headers(token))
    resp.raise_for_status()
    areas = resp.json()

    open_fields = [a for a in areas if a["area_type"] == "open_field"]
    if not open_fields:
        print("No open field areas found — run seed_demo_farms.py first.")
        sys.exit(1)

    corn_fields = [a for a in open_fields if "corn" in a["name"].lower()]
    soybean_fields = [a for a in open_fields if "soybean" in a["name"].lower()]

    print(f"\nFound {len(corn_fields)} corn field(s), {len(soybean_fields)} soybean field(s).")

    for area in corn_fields:
        acres = area.get("area_acres") or 1.0
        print(f"\n  Corn cycles for: {area['name']} ({acres} acres)")
        for year in [2022, 2023, 2024]:
            actual = round(CORN_YIELDS[year] * acres, 1)
            target = round(CORN_YIELDS[year] * acres * 1.05, 1)  # 5% optimistic target
            _create_and_harvest(
                token=token,
                area_id=area["id"],
                crop_id=corn_id,
                season_year=year,
                cycle_number=1,
                planted_at=f"{year}-{CORN_PLANT_MONTH}",
                harvested_at=f"{year}-{CORN_HARVEST_MONTH}",
                actual_yield=actual,
                target_yield=target,
                yield_unit="bushels",
            )

    for area in soybean_fields:
        acres = area.get("area_acres") or 1.0
        print(f"\n  Soybean cycles for: {area['name']} ({acres} acres)")
        for year in [2022, 2023, 2024]:
            actual = round(SOYBEAN_YIELDS[year] * acres, 1)
            target = round(SOYBEAN_YIELDS[year] * acres * 1.05, 1)
            _create_and_harvest(
                token=token,
                area_id=area["id"],
                crop_id=soybean_id,
                season_year=year,
                cycle_number=1,
                planted_at=f"{year}-{SOYBEAN_PLANT_MONTH}",
                harvested_at=f"{year}-{SOYBEAN_HARVEST_MONTH}",
                actual_yield=actual,
                target_yield=target,
                yield_unit="bushels",
            )

    print("\nHistorical harvest seed complete.")


if __name__ == "__main__":
    try:
        main()
    except httpx.HTTPStatusError as exc:
        print(f"\nHTTP error: {exc.response.status_code} — {exc.response.text}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(0)
