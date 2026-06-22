from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class SubPhase:
    name: str       # machine key e.g. "germination"
    label: str      # display label e.g. "Germination"
    day_start: int  # cumulative from planted_at (inclusive)
    day_end: int    # cumulative from planted_at (exclusive)


@dataclass(frozen=True)
class PhaseDays:
    seeding_days: int
    growing_days: int
    harvest_days: int
    seeding_sub_phases: tuple[SubPhase, ...] = ()
    growing_sub_phases: tuple[SubPhase, ...] = ()
    harvest_sub_phases: tuple[SubPhase, ...] = ()
    min_pick_interval_days: int | None = None  # None = single terminal harvest; set for continuous-pick crops


# All day counts use midpoint averages of observed ranges.
# Source: Jacob's crop reference bookmarks, captured 2026-04-28.
CROP_PHASE_DEFAULTS: dict[str, PhaseDays] = {
    "corn": PhaseDays(
        seeding_days=10,
        growing_days=132,   # vegetative(72) + reproductive(60)
        harvest_days=25,
        seeding_sub_phases=(SubPhase("germination", "Germination", 0, 10),),
        growing_sub_phases=(
            SubPhase("vegetative", "Vegetative Growth", 10, 82),
            SubPhase("reproductive", "Reproductive", 82, 142),
        ),
        harvest_sub_phases=(SubPhase("maturity_harvest", "Maturity & Harvest", 142, 167),),
    ),
    "tomatoes": PhaseDays(
        seeding_days=37,    # germination(7) + early growth(30)
        growing_days=104,   # vegetative(22) + flowering(20) + pollination(20) + fruit formation(25) + ripening(17)
        harvest_days=0,     # sentinel — computed dynamically from forecasted_end_date
        min_pick_interval_days=6,  # 6-day rotation between picks on the same row
        seeding_sub_phases=(
            SubPhase("germination", "Germination", 0, 7),
            SubPhase("early_growth", "Early Growth", 7, 37),
        ),
        growing_sub_phases=(
            SubPhase("vegetative", "Vegetative Growth", 37, 59),
            SubPhase("flowering", "Flowering", 59, 79),
            SubPhase("pollination", "Pollination", 79, 99),
            SubPhase("fruit_formation", "Fruit Formation", 99, 124),
            SubPhase("ripening", "Ripening", 124, 141),
        ),
        # harvest_sub_phases built at runtime from forecasted_end_date
    ),
}


def _arugula_phase_days(planted_at: date | None) -> PhaseDays:
    # Summer planting: harvest baby leaf early in the maturity window before heat stress bolts the plant.
    # Non-summer: let mature through the full window for full-size heads.
    is_summer = planted_at is not None and planted_at.month in (6, 7, 8)
    harvest_days = 15 if is_summer else 42
    harvest_label = "Baby Leaf Harvest" if is_summer else "Full Leaf Harvest"
    return PhaseDays(
        seeding_days=24,    # germination(7) + seedling(17)
        growing_days=25,    # vegetative growth
        harvest_days=harvest_days,
        seeding_sub_phases=(
            SubPhase("germination", "Germination", 0, 7),
            SubPhase("seedling", "Seedling", 7, 24),
        ),
        growing_sub_phases=(SubPhase("vegetative", "Vegetative Growth", 24, 49),),
        harvest_sub_phases=(SubPhase("harvest", harvest_label, 49, 49 + harvest_days),),
    )


def _soybean_phase_days(planted_at: date | None) -> PhaseDays:
    is_double = (
        planted_at is not None
        and (planted_at.month > 6 or (planted_at.month == 6 and planted_at.day >= 15))
    )
    if is_double:
        # Double-crop durations TBD from reference data — unchanged from initial estimates.
        return PhaseDays(
            seeding_days=8,
            growing_days=72,
            harvest_days=15,
            seeding_sub_phases=(SubPhase("germination", "Germination", 0, 8),),
            growing_sub_phases=(
                SubPhase("vegetative", "Vegetative Growth", 8, 30),
                SubPhase("flowering_pod_set", "Flowering & Pod Set", 30, 60),
                SubPhase("seed_fill_maturation", "Seed Fill & Maturation", 60, 80),
            ),
            harvest_sub_phases=(SubPhase("field_harvest", "Field Harvest", 80, 95),),
        )
    # Group III standard-season — midpoint averages from reference data.
    return PhaseDays(
        seeding_days=8,
        growing_days=56,    # vegetative(36) + flowering(20)
        harvest_days=45,    # maturity to harvest
        seeding_sub_phases=(SubPhase("germination", "Germination", 0, 8),),
        growing_sub_phases=(
            SubPhase("vegetative", "Vegetative Growth", 8, 44),
            SubPhase("flowering", "Flowering", 44, 64),
        ),
        harvest_sub_phases=(SubPhase("maturity_harvest", "Maturity & Harvest", 64, 109),),
    )


def get_phase_days(
    crop_name: str,
    planted_at: date | None = None,
    forecasted_end: date | None = None,
) -> PhaseDays:
    if crop_name == "arugula_lettuce":
        return _arugula_phase_days(planted_at)
    if crop_name == "soybeans":
        return _soybean_phase_days(planted_at)
    pd = CROP_PHASE_DEFAULTS.get(crop_name, PhaseDays(0, 0, 0))
    if crop_name == "tomatoes" and planted_at and forecasted_end:
        # Harvest phase begins at day 141 (seeding 37 + growing 104).
        harvest_days = max(0, (forecasted_end - planted_at).days - 141)
        harvest_end = 141 + harvest_days
        return PhaseDays(
            seeding_days=pd.seeding_days,
            growing_days=pd.growing_days,
            harvest_days=harvest_days,
            seeding_sub_phases=pd.seeding_sub_phases,
            growing_sub_phases=pd.growing_sub_phases,
            harvest_sub_phases=(SubPhase("harvest", "Harvest", 141, harvest_end),),
        )
    return pd


def get_sub_phase(
    crop_name: str,
    days_in: int,
    planted_at: date | None = None,
    forecasted_end: date | None = None,
) -> SubPhase | None:
    pd = get_phase_days(crop_name, planted_at, forecasted_end)
    for sp in pd.seeding_sub_phases + pd.growing_sub_phases + pd.harvest_sub_phases:
        if sp.day_start <= days_in < sp.day_end:
            return sp
    return None
