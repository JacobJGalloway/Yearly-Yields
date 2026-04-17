from dataclasses import dataclass


@dataclass(frozen=True)
class PhaseDays:
    seeding_days: int
    growing_days: int
    harvest_days: int


CROP_PHASE_DEFAULTS: dict[str, PhaseDays] = {
    "corn":            PhaseDays(seeding_days=10, growing_days=95, harvest_days=15),
    "soybeans":        PhaseDays(seeding_days=8,  growing_days=82, harvest_days=10),
    "tomatoes":        PhaseDays(seeding_days=14, growing_days=56, harvest_days=20),
    "arugula_lettuce": PhaseDays(seeding_days=7,  growing_days=23, harvest_days=10),
}


def get_phase_days(crop_name: str) -> PhaseDays:
    return CROP_PHASE_DEFAULTS.get(crop_name, PhaseDays(0, 0, 0))
