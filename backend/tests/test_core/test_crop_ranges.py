"""
Tests for app.core.crop_ranges — phase ideal ranges per crop.
"""

from app.core.crop_ranges import CROP_RANGES, CropRanges, PhaseRange, get_crop_ranges


def test_get_crop_ranges_known_crop():
    result = get_crop_ranges("corn")
    assert isinstance(result, CropRanges)
    assert isinstance(result.seeding, PhaseRange)
    assert isinstance(result.growing, PhaseRange)
    assert isinstance(result.harvest, PhaseRange)


def test_get_crop_ranges_unknown_crop_returns_none():
    assert get_crop_ranges("wheat") is None


def test_all_four_crops_present():
    assert set(CROP_RANGES.keys()) == {"corn", "soybeans", "tomatoes", "arugula_lettuce"}


def test_tomatoes_have_ph_range():
    ranges = get_crop_ranges("tomatoes")
    assert ranges.seeding.ph_min == 5.5
    assert ranges.seeding.ph_max == 6.5


def test_corn_no_ph_range():
    ranges = get_crop_ranges("corn")
    assert ranges.seeding.ph_min is None
    assert ranges.seeding.ph_max is None


def test_phase_range_is_frozen():
    """PhaseRange dataclass must be immutable."""
    pr = PhaseRange(temp_min_f=50.0, temp_max_f=86.0, humidity_min=40.0, humidity_max=70.0)
    try:
        pr.temp_min_f = 99.0  # type: ignore[misc]
        assert False, "Should have raised FrozenInstanceError"
    except Exception:
        pass
