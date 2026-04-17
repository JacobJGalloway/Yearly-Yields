"""
Yield planning service — runs the yield prediction agent for a crop cycle.

Flow:
  1. Called from POST /yield-plans/ with a crop_cycle_id and target_yield.
  2. Loads crop cycle + area context and builds the user message.
  3. Runs the ReAct loop with YIELD_PREDICTION_SYSTEM_PROMPT and YIELD_PLAN_TOOLS.
  4. Loop ends when Claude calls save_yield_plan (terminal tool).
  5. Returns the saved YieldPlan record.
"""

import uuid

import anthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.prompts import YIELD_PREDICTION_SYSTEM_PROMPT
from app.agent.tool_handlers import dispatch_yield_tool
from app.agent.tools import YIELD_PLAN_TOOLS
from app.config import settings
from app.models.crop import Crop, CropCycle
from app.models.field import GrowingArea
from app.models.yield_plan import YieldPlan

_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

MAX_ITERATIONS = 10


async def generate_yield_plan(
    crop_cycle_id: uuid.UUID,
    target_yield: float,
    db: AsyncSession,
) -> YieldPlan | None:
    cycle_result = await db.execute(select(CropCycle).where(CropCycle.id == crop_cycle_id))
    cycle = cycle_result.scalar_one_or_none()
    if cycle is None:
        return None

    area_result = await db.execute(select(GrowingArea).where(GrowingArea.id == cycle.growing_area_id))
    area = area_result.scalar_one_or_none()

    crop_result = await db.execute(select(Crop).where(Crop.id == cycle.crop_id)) if cycle.crop_id else None
    crop = (await db.execute(select(Crop).where(Crop.id == cycle.crop_id))).scalar_one_or_none() if cycle.crop_id else None

    user_message = (
        f"Generate a yield plan for this crop cycle:\n"
        f"- Crop Cycle ID: {cycle.id}\n"
        f"- Crop: {crop.name if crop else 'unknown'}\n"
        f"- Growing Area: {area.name if area else 'unknown'} ({area.area_type.value if area else 'unknown'})\n"
        f"- Season Year: {cycle.season_year}, Cycle #{cycle.cycle_number}\n"
        f"- Planted: {cycle.planted_at}\n"
        f"- Yield Unit: {cycle.yield_unit.value}\n"
        f"- Target Yield: {target_yield} {cycle.yield_unit.value}\n"
        f"\nUse the available tools to gather historical sensor data and past cycle yields, "
        f"then call save_yield_plan with your recommendation."
    )

    messages = [{"role": "user", "content": user_message}]
    saved_plan_id: uuid.UUID | None = None

    for _ in range(MAX_ITERATIONS):
        response = await _client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=2048,
            system=YIELD_PREDICTION_SYSTEM_PROMPT,
            tools=YIELD_PLAN_TOOLS,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            break

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue

            result = await dispatch_yield_tool(block.name, block.input, db)

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": str(result),
            })

            if block.name == "save_yield_plan" and "yield_plan_id" in result:
                saved_plan_id = uuid.UUID(result["yield_plan_id"])
                messages.append({"role": "user", "content": tool_results})
                break

        else:
            messages.append({"role": "user", "content": tool_results})
            continue
        break

    if saved_plan_id is None:
        return None

    plan_result = await db.execute(select(YieldPlan).where(YieldPlan.id == saved_plan_id))
    return plan_result.scalar_one_or_none()
