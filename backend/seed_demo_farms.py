"""
Seed script: demo farm growing areas and starter crop cycles.

Covers:
  - Jacksonville, IL open fields (KMTO) — corn and soybeans
  - Morristown, TN greenhouses GH1 + GH2 (KMOR) — tomatoes and arugula

Run from backend/ with the dev server already running:
    python seed_demo_farms.py

Reads OWNER_EMAIL and OWNER_PASSWORD from environment or prompts if absent.
Requires NOAA_CDO_TOKEN in .env for historical backfill (optional — skipped if missing).
Safe to re-run — areas and cycles are skipped if they already exist.
"""

import os
import sys

import httpx

BASE_URL = "http://127.0.0.1:8000/api/v1"


def _login(email: str, password: str) -> str:
    resp = httpx.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password})
    resp.raise_for_status()
    return resp.json()["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _list_areas(token: str) -> list[dict]:
    resp = httpx.get(f"{BASE_URL}/fields/", headers=_headers(token))
    resp.raise_for_status()
    return resp.json()


def _list_cycles(token: str, growing_area_id: str) -> list[dict]:
    resp = httpx.get(
        f"{BASE_URL}/crops/cycles",
        params={"growing_area_id": growing_area_id},
        headers=_headers(token),
    )
    resp.raise_for_status()
    return resp.json()


def _create_area(token: str, payload: dict, existing: list[dict]) -> dict:
    match = next((a for a in existing if a["name"] == payload["name"]), None)
    if match:
        print(f"  Skipped (already exists): {match['name']} ({match['id']})")
        return match
    resp = httpx.post(f"{BASE_URL}/fields/", json=payload, headers=_headers(token))
    resp.raise_for_status()
    area = resp.json()
    print(f"  Created: {area['name']} ({area['id']})")
    return area


def _create_cycle(token: str, payload: dict) -> None:
    area_id = payload["growing_area_id"]
    existing = _list_cycles(token, area_id)
    dupe = next(
        (c for c in existing
         if c["season_year"] == payload["season_year"]
         and c["cycle_number"] == payload["cycle_number"]),
        None,
    )
    if dupe:
        print(f"    Skipped cycle (already exists): {dupe['id']}")
        return
    resp = httpx.post(f"{BASE_URL}/crops/cycles", json=payload, headers=_headers(token))
    resp.raise_for_status()
    print(f"    Cycle: {resp.json()['id']}")


def _find_crop_id(token: str, name: str) -> str:
    resp = httpx.get(f"{BASE_URL}/crops/", headers=_headers(token))
    resp.raise_for_status()
    crops = resp.json()
    match = next((c for c in crops if c["name"] == name), None)
    if match is None:
        raise ValueError(f"Crop '{name}' not found. Ensure crop seed data is loaded.")
    return match["id"]


def main() -> None:
    email = os.environ.get("OWNER_EMAIL") or input("Owner email: ")
    password = os.environ.get("OWNER_PASSWORD") or input("Owner password: ")

    print("Logging in...")
    token = _login(email, password)

    print("Resolving crop IDs...")
    tomato_id = _find_crop_id(token, "tomatoes")
    arugula_id = _find_crop_id(token, "arugula_lettuce")
    corn_id = _find_crop_id(token, "corn")
    soybean_id = _find_crop_id(token, "soybeans")

    print("Fetching existing growing areas...")
    existing_areas = _list_areas(token)

    # ── GH1: 2 bays, 5,000 sqft each ────────────────────────────────────────
    # Seasonal: spring → first frost. Minimal insulation, portable equipment.
    # target_temp_f set while equipment is deployed; clear at season end.
    print("\nCreating GH1 (36.2771, -83.2289) — seasonal, pro-hobbyist:")
    gh1_bays = [
        {
            "name": "Morristown GH1 — Bay A",
            "area_type": "dwc_greenhouse",
            "latitude": 36.2771,
            "longitude": -83.2289,
            "area_sqft": 5000.0,
            "nws_station_id": "KMOR",
            "temp_offset_f": 8.0,
            "humidity_offset_pct": 15.0,
            "target_temp_f": 72.0,
            "target_humidity_pct": 70.0,
        },
        {
            "name": "Morristown GH1 — Bay B",
            "area_type": "dwc_greenhouse",
            "latitude": 36.2771,
            "longitude": -83.2289,
            "area_sqft": 5000.0,
            "nws_station_id": "KMOR",
            "temp_offset_f": 8.0,
            "humidity_offset_pct": 15.0,
            "target_temp_f": 72.0,
            "target_humidity_pct": 70.0,
        },
    ]
    gh1_areas = [_create_area(token, b, existing_areas) for b in gh1_bays]

    print("  Adding tomato cycles for GH1:")
    for area, planted, end in zip(
        gh1_areas,
        ["2026-01-20", "2026-02-20"],
        ["2026-11-01", "2026-11-01"],
    ):
        _create_cycle(token, {
            "growing_area_id": area["id"], "crop_id": tomato_id,
            "season_year": 2026, "cycle_number": 1, "yield_unit": "lbs",
            "planted_at": planted, "forecasted_end_date": end,
        })

    # ── GH2: 3 bays, 7,000 sqft each ────────────────────────────────────────
    # Year-round commercial. Proper insulation, real HVAC.
    # Even split: 2 tomato bays + 1 arugula bay.
    print("\nCreating GH2 (36.2629, -83.2268) — year-round, commercial:")
    gh2_bays = [
        {
            "name": "Morristown GH2 — Bay A",
            "area_type": "dwc_greenhouse",
            "latitude": 36.2629,
            "longitude": -83.2268,
            "area_sqft": 7000.0,
            "nws_station_id": "KMOR",
            "temp_offset_f": 12.0,
            "humidity_offset_pct": 20.0,
            "target_temp_f": 74.0,
            "target_humidity_pct": 72.0,
        },
        {
            "name": "Morristown GH2 — Bay B",
            "area_type": "dwc_greenhouse",
            "latitude": 36.2629,
            "longitude": -83.2268,
            "area_sqft": 7000.0,
            "nws_station_id": "KMOR",
            "temp_offset_f": 12.0,
            "humidity_offset_pct": 20.0,
            "target_temp_f": 74.0,
            "target_humidity_pct": 72.0,
        },
        {
            "name": "Morristown GH2 — Bay C",
            "area_type": "dwc_greenhouse",
            "latitude": 36.2629,
            "longitude": -83.2268,
            "area_sqft": 7000.0,
            "nws_station_id": "KMOR",
            "temp_offset_f": 12.0,
            "humidity_offset_pct": 20.0,
            "target_temp_f": 68.0,
            "target_humidity_pct": 75.0,
        },
    ]
    gh2_areas = [_create_area(token, b, existing_areas) for b in gh2_bays]

    print("  Adding cycles for GH2:")
    gh2_cycle_specs = [
        (gh2_areas[0], tomato_id,  "2026-01-15", "2027-07-15"),
        (gh2_areas[1], tomato_id,  "2026-03-01", "2027-09-01"),
        (gh2_areas[2], arugula_id, "2026-04-01", None),
    ]
    for area, crop_id, planted, end in gh2_cycle_specs:
        payload = {
            "growing_area_id": area["id"], "crop_id": crop_id,
            "season_year": 2026, "cycle_number": 1, "yield_unit": "lbs",
            "planted_at": planted,
        }
        if end:
            payload["forecasted_end_date"] = end
        _create_cycle(token, payload)

    # ── Jacksonville IL open fields (KMTO) ───────────────────────────────────
    # Patch any open_field areas without an NWS station.
    # Jacksonville IL is the only open field site, so KMTO is unambiguous.
    print("\nPatching Jacksonville IL open fields with KMTO station:")
    unassigned_fields = [
        a for a in existing_areas
        if a["area_type"] == "open_field" and not a.get("nws_station_id")
    ]
    if not unassigned_fields:
        print("  All open fields already have a station assigned — nothing to patch.")
    for area in unassigned_fields:
        resp = httpx.patch(
            f"{BASE_URL}/fields/{area['id']}",
            json={"nws_station_id": "KMTO"},
            headers=_headers(token),
        )
        resp.raise_for_status()
        print(f"  Patched: {area['name']} ({area['id']}) → KMTO")

    print("\nAll done. Growing areas and crop cycles are ready.")
    print("NWS polling starts automatically with the dev server.")
    print("For CDO historical backfill: set NOAA_CDO_TOKEN in .env,")
    print("then call nws_service.backfill('KMOR'/'KMTO', start, end) directly.")


if __name__ == "__main__":
    try:
        main()
    except httpx.HTTPStatusError as exc:
        print(f"\nHTTP error: {exc.response.status_code} — {exc.response.text}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(0)
