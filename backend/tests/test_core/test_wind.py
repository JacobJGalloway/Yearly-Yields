import pytest
from app.core.wind import cardinal_to_degrees, degrees_to_cardinal


@pytest.mark.parametrize("degrees,expected", [
    (0.0,   "N"),
    (22.5,  "NNE"),
    (45.0,  "NE"),
    (90.0,  "E"),
    (135.0, "SE"),
    (180.0, "S"),
    (225.0, "SW"),
    (270.0, "W"),
    (315.0, "NW"),
    (337.5, "NNW"),
    (360.0, "N"),      # wraps to N
    (11.24, "N"),      # rounds down to N
    (11.26, "NNE"),    # rounds up to NNE
])
def test_degrees_to_cardinal(degrees, expected):
    assert degrees_to_cardinal(degrees) == expected


@pytest.mark.parametrize("cardinal,expected", [
    ("N",   0.0),
    ("NNE", 22.5),
    ("NE",  45.0),
    ("ENE", 67.5),
    ("E",   90.0),
    ("ESE", 112.5),
    ("SE",  135.0),
    ("SSE", 157.5),
    ("S",   180.0),
    ("SSW", 202.5),
    ("SW",  225.0),
    ("WSW", 247.5),
    ("W",   270.0),
    ("WNW", 292.5),
    ("NW",  315.0),
    ("NNW", 337.5),
    ("n",   0.0),      # case insensitive
    ("sw",  225.0),
])
def test_cardinal_to_degrees(cardinal, expected):
    assert cardinal_to_degrees(cardinal) == expected


def test_cardinal_to_degrees_invalid():
    with pytest.raises(ValueError, match="Unknown cardinal direction"):
        cardinal_to_degrees("INVALID")
