_CARDINALS = [
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
]

_CARDINAL_TO_DEGREES: dict[str, float] = {name: deg for name, deg in _CARDINALS}


def degrees_to_cardinal(degrees: float) -> str:
    """Convert wind direction degrees (0.0–359.99) to a 16-point cardinal label."""
    return _CARDINALS[round(degrees % 360 / 22.5) % 16][0]


def cardinal_to_degrees(cardinal: str) -> float:
    """Convert a 16-point cardinal direction to its center degrees (0.0–337.5)."""
    key = cardinal.upper()
    if key not in _CARDINAL_TO_DEGREES:
        raise ValueError(f"Unknown cardinal direction: {cardinal!r}")
    return _CARDINAL_TO_DEGREES[key]
