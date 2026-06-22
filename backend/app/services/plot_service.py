import uuid
from datetime import date
from typing import List, Optional, Sequence

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crop_phases import get_phase_days
from app.models.crop import CropCycle, CropCycleStatus
from app.models.field import GrowingAreaPlot


def is_harvest_day(plot: GrowingAreaPlot, d: Optional[date] = None) -> bool:
    """Return True if the given date falls on one of the plot's scheduled harvest weekdays.

    ISO weekday: 1=Monday … 7=Sunday. Returns False for open-field sentinels (harvest_weekdays is None).
    Defaults to today when d is not supplied.
    """
    if not plot.harvest_weekdays:
        return False
    target = d or date.today()
    return target.isoweekday() in plot.harvest_weekdays


async def get_harvest_plots_for_date(
    growing_area_id: uuid.UUID,
    d: Optional[date],
    db: AsyncSession,
) -> List[GrowingAreaPlot]:
    """Return active plots in the area whose harvest_weekdays include the given date's ISO weekday."""
    target = d or date.today()
    weekday = target.isoweekday()

    result = await db.execute(
        select(GrowingAreaPlot).where(
            GrowingAreaPlot.growing_area_id == growing_area_id,
            GrowingAreaPlot.is_active.is_(True),
            GrowingAreaPlot.harvest_weekdays.is_not(None),
        )
    )
    plots: Sequence[GrowingAreaPlot] = result.scalars().all()
    return [p for p in plots if weekday in (p.harvest_weekdays or [])]


async def check_weekday_overlap(
    growing_area_id: uuid.UUID,
    harvest_weekdays: List[int],
    exclude_plot_id: Optional[uuid.UUID],
    db: AsyncSession,
) -> None:
    """Raise 422 if any sibling plot in the area already owns one of the requested weekdays."""
    result = await db.execute(
        select(GrowingAreaPlot).where(
            GrowingAreaPlot.growing_area_id == growing_area_id,
            GrowingAreaPlot.harvest_weekdays.is_not(None),
        )
    )
    siblings = result.scalars().all()
    new_days = set(harvest_weekdays)
    for sibling in siblings:
        if exclude_plot_id and sibling.id == exclude_plot_id:
            continue
        conflict = new_days & set(sibling.harvest_weekdays or [])
        if conflict:
            day_names = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat", 7: "Sun"}
            names = ", ".join(day_names[d] for d in sorted(conflict))
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Weekday conflict: {names} already assigned to plot "
                    f"'{sibling.name or sibling.plot_index}' in this area."
                ),
            )


async def log_harvest_pick(
    plot_id: uuid.UUID,
    pick_date: Optional[date],
    db: AsyncSession,
) -> GrowingAreaPlot:
    """Record a harvest pick on a plot, enforcing the crop's minimum pick interval.

    Looks up the active CropCycle on the plot to determine the crop's min_pick_interval_days.
    Raises 422 if the interval since last_harvest_date has not been met.
    Raises 404 if no active cycle exists (cannot pick from a row with no active cycle).
    Updates last_harvest_date on success.
    """
    plot = await db.get(GrowingAreaPlot, plot_id)
    if plot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plot not found")

    target_date = pick_date or date.today()

    result = await db.execute(
        select(CropCycle).where(
            CropCycle.growing_area_plot_id == plot_id,
            CropCycle.status == CropCycleStatus.active,
        )
    )
    active_cycle = result.scalar_one_or_none()
    if active_cycle is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No active crop cycle on this plot. Cannot log a harvest pick.",
        )

    if active_cycle.crop_id is not None:
        crop_result = await db.execute(
            select(CropCycle.crop_id).where(CropCycle.id == active_cycle.id)
        )
        from app.models.crop import Crop
        crop = await db.get(Crop, active_cycle.crop_id)
        if crop:
            phase = get_phase_days(crop.name, active_cycle.planted_at)
            min_interval = phase.min_pick_interval_days
            if min_interval and plot.last_harvest_date:
                days_since = (target_date - plot.last_harvest_date).days
                if days_since < min_interval:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=(
                            f"Only {days_since} day(s) since last pick on this row. "
                            f"{crop.name} requires at least {min_interval} days between picks."
                        ),
                    )

    plot.last_harvest_date = target_date
    await db.commit()
    await db.refresh(plot)
    return plot


async def resolve_plot_id(
    growing_area_id: uuid.UUID,
    growing_area_plot_id: uuid.UUID | None,
    db: AsyncSession,
) -> uuid.UUID:
    """
    Resolve an optional growing_area_plot_id to a concrete UUID before any DB write or read.

    If growing_area_plot_id is provided: validate it belongs to the growing area and return it.
    If growing_area_plot_id is None: resolve to the plot_index=0 sentinel row for the area.

    Raises 422 if the provided ID does not belong to the given area.
    Raises 404 if no sentinel (plot_index=0) exists — indicates a migration integrity failure.

    Never pass None into query logic. Always call this at the service/API boundary.
    """
    if growing_area_plot_id is not None:
        plot = await db.get(GrowingAreaPlot, growing_area_plot_id)
        if plot is None or plot.growing_area_id != growing_area_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"growing_area_plot_id {growing_area_plot_id} does not belong "
                    f"to growing_area {growing_area_id}."
                ),
            )
        return plot.id

    result = await db.execute(
        select(GrowingAreaPlot.id)
        .where(GrowingAreaPlot.growing_area_id == growing_area_id)
        .where(GrowingAreaPlot.plot_index == 0)
    )
    sentinel_id = result.scalar_one_or_none()
    if sentinel_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No sentinel plot (plot_index=0) found for growing_area {growing_area_id}. "
                "This indicates a migration integrity failure."
            ),
        )
    return sentinel_id
