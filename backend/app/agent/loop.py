"""
ReAct agent loop for anomaly detection.

Flow:
  1. Triggered by a sensor reading POST (via FastAPI BackgroundTask).
  2. Sends the reading context to Claude with the anomaly-check system prompt.
  3. Claude reasons and calls tools one at a time.
  4. We execute each tool via dispatch_tool() and return the result.
  5. Loop ends when Claude calls log_reading_assessment (no more tool calls).
"""

import uuid
from datetime import date, timezone

import anthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.prompts import ANOMALY_CHECK_SYSTEM_PROMPT
from app.agent.tool_handlers import dispatch_tool
from app.agent.tools import ANOMALY_CHECK_TOOLS
from app.config import settings
from app.core.crop_phases import get_phase_days
from app.core.crop_ranges import get_crop_ranges
from app.models.crop import Crop, CropCycle
from app.models.sensor_reading import AssessmentStatus, SensorReading

_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

MAX_ITERATIONS = 10  # safety ceiling — prevents runaway loops


async def run_anomaly_check(reading_id: uuid.UUID, db: AsyncSession) -> None:
    result = await db.execute(
        select(SensorReading).where(SensorReading.id == reading_id)
    )
    reading = result.scalar_one_or_none()
    if reading is None:
        return

    # Mark as processing so concurrent POSTs don't double-trigger
    reading.assessment_status = AssessmentStatus.processing
    await db.commit()

    crop_context = ""
    if reading.crop_cycle_id:
        cycle_result = await db.execute(select(CropCycle).where(CropCycle.id == reading.crop_cycle_id))
        cycle = cycle_result.scalar_one_or_none()
        if cycle and cycle.crop_id:
            crop_result = await db.execute(select(Crop).where(Crop.id == cycle.crop_id))
            crop = crop_result.scalar_one_or_none()
            if crop:
                days_in = (date.today() - cycle.planted_at).days
                phase_days = get_phase_days(
                    crop.name,
                    planted_at=cycle.planted_at,
                    forecasted_end=cycle.forecasted_end_date,
                )
                if days_in < phase_days.seeding_days:
                    phase = "seeding"
                elif days_in < phase_days.seeding_days + phase_days.growing_days:
                    phase = "growing"
                else:
                    phase = "harvest"

                ranges = get_crop_ranges(crop.name)
                if ranges:
                    phase_range = getattr(ranges, phase)
                    crop_context = (
                        f"- Crop: {crop.name} (phase: {phase}, day {days_in} of cycle)\n"
                        f"- Ideal temp range: {phase_range.temp_min_f}–{phase_range.temp_max_f}°F\n"
                        f"- Ideal humidity range: {phase_range.humidity_min}–{phase_range.humidity_max}%\n"
                    )

    user_message = (
        f"Assess this sensor reading:\n"
        f"- Reading ID: {reading.id}\n"
        f"- Growing Area ID: {reading.growing_area_id}\n"
        f"- Temperature: {reading.temperature}°F\n"
        f"- Humidity: {reading.humidity}%\n"
        f"- Source: {reading.reading_source.value}\n"
        f"- Read at: {reading.read_at.isoformat()}\n"
        f"- Crop Cycle ID: {reading.crop_cycle_id or 'none'}\n"
        + crop_context
    )

    messages = [{"role": "user", "content": user_message}]

    try:
        for _ in range(MAX_ITERATIONS):
            response = await _client.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=1024,
                system=ANOMALY_CHECK_SYSTEM_PROMPT,
                tools=ANOMALY_CHECK_TOOLS,
                messages=messages,
            )

            # Append Claude's response to the conversation
            messages.append({"role": "assistant", "content": response.content})

            # No tool calls — Claude is done
            if response.stop_reason == "end_turn":
                break

            # Process all tool calls in this response
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                tool_result = await dispatch_tool(block.name, block.input, db)

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(tool_result),
                })

                # log_reading_assessment is always the final tool — stop after it
                if block.name == "log_reading_assessment":
                    messages.append({"role": "user", "content": tool_results})
                    return

            messages.append({"role": "user", "content": tool_results})

    except Exception as e:
        # Mark the reading as errored so it can be reviewed manually
        reading.assessment_status = AssessmentStatus.error
        reading.assessment_summary = f"Agent loop failed: {e}"
        await db.commit()
