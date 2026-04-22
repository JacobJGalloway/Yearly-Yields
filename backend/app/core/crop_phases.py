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


CROP_PHASE_DEFAULTS: dict[str, PhaseDays] = {
    "corn": PhaseDays(
        seeding_days=10,
        growing_days=120,
        harvest_days=20,
        seeding_sub_phases=(SubPhase("germination", "Germination", 0, 10),),
        growing_sub_phases=(
            SubPhase("vegetative", "Vegetative", 10, 75),
            SubPhase("silking_pollination", "Silking & Pollination", 75, 85),
            SubPhase("grain_fill_drying", "Grain Fill & Drying", 85, 130),
        ),
        harvest_sub_phases=(SubPhase("field_harvest", "Field Harvest", 130, 150),),
    ),
    "tomatoes": PhaseDays(
        seeding_days=30,
        growing_days=80,
        harvest_days=0,  # sentinel — computed dynamically from forecasted_end_date
        seeding_sub_phases=(
            SubPhase("germination", "Germination", 0, 10),
            SubPhase("seedling", "Seedling", 10, 30),
        ),
        growing_sub_phases=(
            SubPhase("vegetative", "Vegetative", 30, 60),
            SubPhase("flowering_fruit_set", "Flowering & Fruit Set", 60, 75),
            SubPhase("fruiting_ripening", "Fruiting & Ripening", 75, 110),
        ),
        # harvest_sub_phases built at runtime from forecasted_end_date
    ),
}


def _arugula_phase_days(planted_at: date | None) -> PhaseDays:
    is_summer = planted_at is not None and planted_at.month in (6, 7, 8)
    harvest_days = 10 if is_summer else 20
    harvest_label = "Baby Leaf Harvest" if is_summer else "Full Leaf Harvest"
    return PhaseDays(
        seeding_days=14,
        growing_days=11,
        harvest_days=harvest_days,
        seeding_sub_phases=(
            SubPhase("germination", "Germination", 0, 7),
            SubPhase("seedling", "Seedling", 7, 14),
        ),
        growing_sub_phases=(SubPhase("rapid_growth", "Rapid Growth", 14, 25),),
        harvest_sub_phases=(SubPhase("harvest", harvest_label, 25, 25 + harvest_days),),
    )


def _soybean_phase_days(planted_at: date | None) -> PhaseDays:
    is_double = (
        planted_at is not None
        and (planted_at.month > 6 or (planted_at.month == 6 and planted_at.day >= 15))
    )
    if is_double:
        return PhaseDays(
            seeding_days=8,
            growing_days=72,
            harvest_days=15,
            seeding_sub_phases=(SubPhase("germination", "Germination", 0, 8),),
            growing_sub_phases=(
                SubPhase("vegetative", "Vegetative", 8, 30),
                SubPhase("flowering_pod_set", "Flowering & Pod Set", 30, 60),
                SubPhase("seed_fill_maturation", "Seed Fill & Maturation", 60, 80),
            ),
            harvest_sub_phases=(SubPhase("field_harvest", "Field Harvest", 80, 95),),
        )
    return PhaseDays(
        seeding_days=8,
        growing_days=112,
        harvest_days=15,
        seeding_sub_phases=(SubPhase("germination", "Germination", 0, 8),),
        growing_sub_phases=(
            SubPhase("vegetative", "Vegetative", 8, 45),
            SubPhase("flowering_pod_set", "Flowering & Pod Set", 45, 90),
            SubPhase("seed_fill_maturation", "Seed Fill & Maturation", 90, 120),
        ),
        harvest_sub_phases=(SubPhase("field_harvest", "Field Harvest", 120, 135),),
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
        harvest_days = max(0, (forecasted_end - planted_at).days - 110)
        harvest_end = 110 + harvest_days
        return PhaseDays(
            seeding_days=pd.seeding_days,
            growing_days=pd.growing_days,
            harvest_days=harvest_days,
            seeding_sub_phases=pd.seeding_sub_phases,
            growing_sub_phases=pd.growing_sub_phases,
            harvest_sub_phases=(SubPhase("harvest", "Harvest", 110, harvest_end),),
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
