from dataclasses import dataclass


@dataclass(frozen=True)
class PhaseRange:
    temp_min_f: float
    temp_max_f: float
    humidity_min: float  # %
    humidity_max: float  # %


@dataclass(frozen=True)
class CropRanges:
    seeding: PhaseRange
    growing: PhaseRange
    harvest: PhaseRange


CROP_RANGES: dict[str, CropRanges] = {
    "corn": CropRanges(
        seeding=PhaseRange(temp_min_f=50.0, temp_max_f=86.0, humidity_min=40.0, humidity_max=70.0),
        growing=PhaseRange(temp_min_f=60.0, temp_max_f=95.0, humidity_min=40.0, humidity_max=75.0),
        harvest=PhaseRange(temp_min_f=40.0, temp_max_f=90.0, humidity_min=30.0, humidity_max=60.0),
    ),
    "soybeans": CropRanges(
        seeding=PhaseRange(temp_min_f=50.0, temp_max_f=86.0, humidity_min=40.0, humidity_max=70.0),
        growing=PhaseRange(temp_min_f=60.0, temp_max_f=90.0, humidity_min=45.0, humidity_max=75.0),
        harvest=PhaseRange(temp_min_f=40.0, temp_max_f=85.0, humidity_min=25.0, humidity_max=55.0),
    ),
    "tomatoes": CropRanges(
        seeding=PhaseRange(temp_min_f=65.0, temp_max_f=85.0, humidity_min=65.0, humidity_max=85.0),
        growing=PhaseRange(temp_min_f=65.0, temp_max_f=90.0, humidity_min=60.0, humidity_max=80.0),
        harvest=PhaseRange(temp_min_f=60.0, temp_max_f=85.0, humidity_min=55.0, humidity_max=75.0),
    ),
    "arugula_lettuce": CropRanges(
        seeding=PhaseRange(temp_min_f=45.0, temp_max_f=75.0, humidity_min=60.0, humidity_max=80.0),
        growing=PhaseRange(temp_min_f=45.0, temp_max_f=75.0, humidity_min=60.0, humidity_max=80.0),
        harvest=PhaseRange(temp_min_f=40.0, temp_max_f=70.0, humidity_min=55.0, humidity_max=75.0),
    ),
}


def get_crop_ranges(crop_name: str) -> CropRanges | None:
    return CROP_RANGES.get(crop_name)
