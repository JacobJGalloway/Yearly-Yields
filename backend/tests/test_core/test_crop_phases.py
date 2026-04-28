from datetime import date

import pytest

from app.core.crop_phases import PhaseDays, get_phase_days, get_sub_phase


# ---------------------------------------------------------------------------
# Arugula — season-dependent harvest window
# ---------------------------------------------------------------------------

class TestArugula:
    def test_non_summer_full_leaf(self):
        pd = get_phase_days("arugula_lettuce", planted_at=date(2026, 3, 1))
        assert pd.seeding_days == 24
        assert pd.growing_days == 25
        assert pd.harvest_days == 42

    def test_summer_baby_leaf(self):
        pd = get_phase_days("arugula_lettuce", planted_at=date(2026, 7, 1))
        assert pd.harvest_days == 15

    def test_none_planted_at_defaults_non_summer(self):
        pd = get_phase_days("arugula_lettuce", planted_at=None)
        assert pd.harvest_days == 42

    def test_sub_phase_germination(self):
        sp = get_sub_phase("arugula_lettuce", 3, planted_at=date(2026, 3, 1))
        assert sp is not None
        assert sp.name == "germination"

    def test_sub_phase_seedling(self):
        sp = get_sub_phase("arugula_lettuce", 10, planted_at=date(2026, 3, 1))
        assert sp is not None
        assert sp.name == "seedling"

    def test_sub_phase_vegetative(self):
        sp = get_sub_phase("arugula_lettuce", 30, planted_at=date(2026, 3, 1))
        assert sp is not None
        assert sp.name == "vegetative"

    def test_sub_phase_harvest_non_summer(self):
        sp = get_sub_phase("arugula_lettuce", 55, planted_at=date(2026, 3, 1))
        assert sp is not None
        assert sp.label == "Full Leaf Harvest"

    def test_sub_phase_harvest_summer(self):
        sp = get_sub_phase("arugula_lettuce", 55, planted_at=date(2026, 7, 1))
        assert sp is not None
        assert sp.label == "Baby Leaf Harvest"

    def test_sub_phase_beyond_cycle_returns_none(self):
        sp = get_sub_phase("arugula_lettuce", 200, planted_at=date(2026, 3, 1))
        assert sp is None


# ---------------------------------------------------------------------------
# Tomatoes — indeterminate; harvest_days sentinel computed from forecasted_end
# ---------------------------------------------------------------------------

class TestTomatoes:
    def test_base_phase_days_no_forecast(self):
        pd = get_phase_days("tomatoes")
        assert pd.seeding_days == 37
        assert pd.growing_days == 104
        assert pd.harvest_days == 0   # sentinel

    def test_harvest_days_computed_from_forecast(self):
        planted = date(2026, 1, 15)
        end = date(2027, 7, 15)
        pd = get_phase_days("tomatoes", planted_at=planted, forecasted_end=end)
        expected_harvest_days = (end - planted).days - 141
        assert pd.harvest_days == expected_harvest_days

    def test_harvest_days_never_negative(self):
        planted = date(2026, 1, 15)
        end = date(2026, 6, 1)   # before harvest threshold
        pd = get_phase_days("tomatoes", planted_at=planted, forecasted_end=end)
        assert pd.harvest_days == 0

    def test_sub_phase_germination(self):
        sp = get_sub_phase("tomatoes", 3)
        assert sp is not None and sp.name == "germination"

    def test_sub_phase_early_growth(self):
        sp = get_sub_phase("tomatoes", 20)
        assert sp is not None and sp.name == "early_growth"

    def test_sub_phase_vegetative(self):
        sp = get_sub_phase("tomatoes", 45)
        assert sp is not None and sp.name == "vegetative"

    def test_sub_phase_flowering(self):
        sp = get_sub_phase("tomatoes", 65)
        assert sp is not None and sp.name == "flowering"

    def test_sub_phase_pollination(self):
        sp = get_sub_phase("tomatoes", 85)
        assert sp is not None and sp.name == "pollination"

    def test_sub_phase_fruit_formation(self):
        sp = get_sub_phase("tomatoes", 110)
        assert sp is not None and sp.name == "fruit_formation"

    def test_sub_phase_ripening(self):
        sp = get_sub_phase("tomatoes", 130)
        assert sp is not None and sp.name == "ripening"

    def test_sub_phase_harvest_with_forecast(self):
        planted = date(2026, 1, 15)
        end = date(2027, 7, 15)
        sp = get_sub_phase("tomatoes", 150, planted_at=planted, forecasted_end=end)
        assert sp is not None and sp.name == "harvest"


# ---------------------------------------------------------------------------
# Corn
# ---------------------------------------------------------------------------

class TestCorn:
    def test_phase_days(self):
        pd = get_phase_days("corn")
        assert pd.seeding_days == 10
        assert pd.growing_days == 132
        assert pd.harvest_days == 25

    def test_total_cycle_days(self):
        pd = get_phase_days("corn")
        assert pd.seeding_days + pd.growing_days + pd.harvest_days == 167

    def test_sub_phase_germination(self):
        sp = get_sub_phase("corn", 5)
        assert sp is not None and sp.name == "germination"

    def test_sub_phase_vegetative(self):
        sp = get_sub_phase("corn", 50)
        assert sp is not None and sp.name == "vegetative"

    def test_sub_phase_reproductive(self):
        sp = get_sub_phase("corn", 100)
        assert sp is not None and sp.name == "reproductive"

    def test_sub_phase_harvest(self):
        sp = get_sub_phase("corn", 150)
        assert sp is not None and sp.name == "maturity_harvest"


# ---------------------------------------------------------------------------
# Soybeans — Group III vs double-crop
# ---------------------------------------------------------------------------

class TestSoybeans:
    def test_standard_group_iii(self):
        pd = get_phase_days("soybeans", planted_at=date(2026, 4, 7))
        assert pd.seeding_days == 8
        assert pd.growing_days == 56
        assert pd.harvest_days == 45

    def test_double_crop_june_15(self):
        pd = get_phase_days("soybeans", planted_at=date(2026, 6, 15))
        assert pd.growing_days == 72
        assert pd.harvest_days == 15

    def test_double_crop_after_june_15(self):
        pd = get_phase_days("soybeans", planted_at=date(2026, 7, 1))
        assert pd.harvest_days == 15

    def test_not_double_crop_june_14(self):
        pd = get_phase_days("soybeans", planted_at=date(2026, 6, 14))
        assert pd.harvest_days == 45   # standard

    def test_sub_phase_vegetative(self):
        sp = get_sub_phase("soybeans", 20, planted_at=date(2026, 4, 7))
        assert sp is not None and sp.name == "vegetative"

    def test_sub_phase_flowering(self):
        sp = get_sub_phase("soybeans", 50, planted_at=date(2026, 4, 7))
        assert sp is not None and sp.name == "flowering"

    def test_sub_phase_maturity_harvest(self):
        sp = get_sub_phase("soybeans", 80, planted_at=date(2026, 4, 7))
        assert sp is not None and sp.name == "maturity_harvest"


# ---------------------------------------------------------------------------
# Unknown crop
# ---------------------------------------------------------------------------

def test_unknown_crop_returns_zero_phase_days():
    pd = get_phase_days("unknown_crop")
    assert pd == PhaseDays(0, 0, 0)


def test_unknown_crop_sub_phase_returns_none():
    assert get_sub_phase("unknown_crop", 10) is None
