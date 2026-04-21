"""
Patch target_yield on all Morristown greenhouse crop cycles.

Calculated values:
  GH1 Bay A  — Tomato  —  33,000 lbs  (seasonal, 24 harvest weeks to first frost)
  GH1 Bay B  — Tomato  —  26,000 lbs  (seasonal, 19 harvest weeks to first frost)
  GH2 Bay A  — Tomato  —  46,300 lbs  (seasonal, 1 of 3 bays down in winter, 24 harvest weeks)
  GH2 Bay B  — Tomato  —  75,100 lbs  (year-round, 9-month harvest config, 39 weeks)
  GH2 Bay C  — Arugula —   1,000 lbs  (9 months staggered bi-weekly DWC)

Math basis:
  Tomatoes: 3 rows × (area_sqft × 0.70 / 40 ft) vine-feet × 5.25 lbs/vine-foot/week
  Arugula:  (area_sqft × 0.70) / 16 sq ft boxes × 0.34 lbs/head, harvested ~19 picks

Run from backend/ with the dev server running:
    python patch_target_yields.py
"""

import os
import sys
import httpx

BASE_URL = "http://127.0.0.1:8000/api/v1"

TARGET_YIELDS = {
    "Morristown GH1 — Bay A": 33000.0,   # seasonal, 24 harvest weeks
    "Morristown GH1 — Bay B": 26000.0,   # seasonal, 19 harvest weeks
    "Morristown GH2 — Bay A": 46300.0,   # seasonal (1 bay down in winter), 24 harvest weeks
    "Morristown GH2 — Bay B": 75100.0,   # year-round, 9-month harvest config (39 weeks)
    "Morristown GH2 — Bay C": 1000.0,    # arugula, 9 months staggered bi-weekly DWC
}


def main() -> None:
    email = os.environ.get("OWNER_EMAIL") or input("Owner email: ")
    password = os.environ.get("OWNER_PASSWORD") or input("Owner password: ")

    resp = httpx.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password})
    resp.raise_for_status()
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    areas = httpx.get(f"{BASE_URL}/fields/", headers=headers)
    areas.raise_for_status()

    for area in areas.json():
        if area["name"] not in TARGET_YIELDS:
            continue
        target = TARGET_YIELDS[area["name"]]

        cycles = httpx.get(
            f"{BASE_URL}/crops/cycles",
            params={"growing_area_id": area["id"]},
            headers=headers,
        )
        cycles.raise_for_status()
        cycle_list = cycles.json()

        if not cycle_list:
            print(f"  No cycles found for {area['name']} — skipping")
            continue

        cycle = cycle_list[0]
        patch = httpx.patch(
            f"{BASE_URL}/crops/cycles/{cycle['id']}",
            json={"target_yield": target},
            headers=headers,
        )
        patch.raise_for_status()
        print(f"  {area['name']}: target_yield set to {target:,.0f} lbs")

    print("\nDone.")


if __name__ == "__main__":
    try:
        main()
    except httpx.HTTPStatusError as exc:
        print(f"\nHTTP error: {exc.response.status_code} — {exc.response.text}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(0)
