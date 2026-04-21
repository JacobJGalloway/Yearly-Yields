"""
Seed historical quarterly harvested crop cycles for Morristown TN greenhouses.

GH1 (seasonal): Q2/Q3/Q4 only — winter months are off-season.
GH2 (year-round): all four quarters per year.

Yields are scaled from the annual targets set in patch_target_yields.py:
  GH1 Bay A: 33,000 lbs / 3 active quarters ≈ 11,000 lbs/Q
  GH1 Bay B: 26,000 lbs / 3 active quarters ≈  8,700 lbs/Q
  GH2 Bay A: 46,300 lbs / 4 quarters          ≈ 11,600 lbs/Q
  GH2 Bay B: 75,100 lbs / 4 quarters          ≈ 18,800 lbs/Q
  GH2 Bay C: 1,000 lbs (arugula) / 4 quarters ≈    250 lbs/Q

Run from backend/ with the dev server running:
    python seed_morristown_harvests.py

Safe to re-run — existing (area, season_year, cycle_number) combos are skipped.
"""

import os
import sys

import httpx

BASE_URL = "http://127.0.0.1:8000/api/v1"

# (cycle_number, planted_at_template, harvested_at_template, label)
GH1_QUARTERS = [
    (1, "{y}-04-01", "{y}-06-30", "Q2"),
    (2, "{y}-07-01", "{y}-09-30", "Q3"),
    (3, "{y}-10-01", "{y}-10-31", "Q4"),  # first frost ~Nov 1
]

GH2_QUARTERS = [
    (1, "{y}-01-01", "{y}-03-31", "Q1"),
    (2, "{y}-04-01", "{y}-06-30", "Q2"),
    (3, "{y}-07-01", "{y}-09-30", "Q3"),
    (4, "{y}-10-01", "{y}-12-31", "Q4"),
]

# area name fragment → (quarters_spec, crop_name, lbs_per_quarter, target_multiplier)
AREA_SPECS = {
    "GH1 — Bay A": (GH1_QUARTERS, "tomatoes", 11000.0, 1.05),
    "GH1 — Bay B": (GH1_QUARTERS, "tomatoes",  8700.0, 1.05),
    "GH2 — Bay A": (GH2_QUARTERS, "tomatoes", 11600.0, 1.05),
    "GH2 — Bay B": (GH2_QUARTERS, "tomatoes", 18800.0, 1.05),
    "GH2 — Bay C": (GH2_QUARTERS, "arugula_lettuce", 250.0, 1.05),
}

SEED_YEARS = [2023, 2024]


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
    quarter_label: str,
) -> None:
    existing = _list_cycles(token, area_id)
    dupe = next(
        (c for c in existing
         if c["season_year"] == season_year and c["cycle_number"] == cycle_number),
        None,
    )
    if dupe:
        print(f"      Skipped (exists): {season_year} {quarter_label} → {dupe['id']}")
        return

    resp = httpx.post(
        f"{BASE_URL}/crops/cycles",
        json={
            "growing_area_id": area_id,
            "crop_id": crop_id,
            "season_year": season_year,
            "cycle_number": cycle_number,
            "planted_at": planted_at,
            "harvested_at": harvested_at,
            "yield_unit": "lbs",
            "target_yield": round(target_yield, 1),
        },
        headers=_headers(token),
    )
    resp.raise_for_status()
    cycle_id = resp.json()["id"]

    resp = httpx.patch(
        f"{BASE_URL}/crops/cycles/{cycle_id}",
        json={
            "status": "harvested",
            "actual_yield": round(actual_yield, 1),
            "harvested_at": harvested_at,
        },
        headers=_headers(token),
    )
    resp.raise_for_status()
    print(f"      {season_year} {quarter_label}: {actual_yield} lbs → {cycle_id}")


def main() -> None:
    email = os.environ.get("OWNER_EMAIL") or input("Owner email: ")
    password = os.environ.get("OWNER_PASSWORD") or input("Owner password: ")

    print("Logging in...")
    token = _login(email, password)

    print("Resolving crop IDs...")
    crop_ids: dict[str, str] = {}
    for crop_name in {"tomatoes", "arugula_lettuce"}:
        crop_ids[crop_name] = _find_crop_id(token, crop_name)

    print("Fetching growing areas...")
    resp = httpx.get(f"{BASE_URL}/fields/", headers=_headers(token))
    resp.raise_for_status()
    areas = resp.json()

    greenhouse_areas = [a for a in areas if a["area_type"] == "dwc_greenhouse"]
    if not greenhouse_areas:
        print("No greenhouse areas found — run seed_demo_farms.py first.")
        sys.exit(1)

    for area in greenhouse_areas:
        spec_key = next((k for k in AREA_SPECS if k in area["name"]), None)
        if spec_key is None:
            print(f"\n  Skipping unrecognised area: {area['name']}")
            continue

        quarters, crop_name, lbs_per_q, target_mult = AREA_SPECS[spec_key]
        crop_id = crop_ids[crop_name]
        print(f"\n  {area['name']} — {crop_name}, {lbs_per_q} lbs/quarter:")

        for year in SEED_YEARS:
            for cycle_num, plant_tmpl, harvest_tmpl, q_label in quarters:
                _create_and_harvest(
                    token=token,
                    area_id=area["id"],
                    crop_id=crop_id,
                    season_year=year,
                    cycle_number=cycle_num,
                    planted_at=plant_tmpl.format(y=year),
                    harvested_at=harvest_tmpl.format(y=year),
                    actual_yield=lbs_per_q,
                    target_yield=lbs_per_q * target_mult,
                    quarter_label=f"{year} {q_label}",
                )

    print("\nMorristown historical harvest seed complete.")


if __name__ == "__main__":
    try:
        main()
    except httpx.HTTPStatusError as exc:
        print(f"\nHTTP error: {exc.response.status_code} — {exc.response.text}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(0)
