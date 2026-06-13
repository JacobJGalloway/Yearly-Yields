import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.field import GrowingAreaPlot


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
