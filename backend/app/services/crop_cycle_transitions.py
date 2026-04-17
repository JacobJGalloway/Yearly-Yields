from app.models.crop import CropCycleStatus

VALID_TRANSITIONS: dict[CropCycleStatus, set[CropCycleStatus]] = {
    CropCycleStatus.active: {CropCycleStatus.harvested, CropCycleStatus.transplanted, CropCycleStatus.abandoned},
    CropCycleStatus.fallow: {CropCycleStatus.active},
    CropCycleStatus.harvested: set(),
    CropCycleStatus.transplanted: set(),
    CropCycleStatus.abandoned: set(),
}


class InvalidTransitionError(ValueError):
    pass


def validate_transition(current: CropCycleStatus, target: CropCycleStatus) -> None:
    allowed = VALID_TRANSITIONS[current]
    if target not in allowed:
        allowed_str = ", ".join(s.value for s in allowed) if allowed else "none (terminal state)"
        raise InvalidTransitionError(
            f"Cannot transition from '{current.value}' to '{target.value}'. "
            f"Allowed: {allowed_str}."
        )
