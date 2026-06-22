"""
ReAct agent loop for anomaly detection.

Flow:
  1. Triggered by a sensor reading POST (via FastAPI BackgroundTask).
  2. Sends the reading context to Claude with the anomaly-check system prompt.
  3. Claude reasons and calls tools one at a time.
  4. MCP tools (get_cycle_context, get_active_alert, get_recent_readings) are
     routed to the local MCP server; all other tools dispatch via tool_handlers.py.
  5. Loop ends when Claude calls log_reading_assessment (no more tool calls).
"""

import json
import uuid
from typing import Any

import anthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.prompts import ANOMALY_CHECK_SYSTEM_PROMPT
from app.agent.tool_handlers import dispatch_tool
from app.agent.tools import ANOMALY_WRITE_TOOLS
from app.config import settings
from app.mcp.client import get_session as get_mcp_session
from app.models.sensor_reading import AssessmentStatus, SensorReading

_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

MAX_ITERATIONS = 10  # safety ceiling — prevents runaway loops

_MCP_TOOL_NAMES = frozenset({"get_cycle_context", "get_active_alert", "get_recent_readings"})

# Cached at first call — MCP tool schemas don't change at runtime.
_mcp_tool_schemas: list[dict[str, Any]] | None = None


async def _get_all_tools() -> list[dict[str, Any]]:
    global _mcp_tool_schemas
    if _mcp_tool_schemas is None:
        result = await get_mcp_session().list_tools()
        _mcp_tool_schemas = [
            {
                "name": t.name,
                "description": t.description or "",
                "input_schema": t.inputSchema,
            }
            for t in result.tools
        ]
    return _mcp_tool_schemas + ANOMALY_WRITE_TOOLS


async def _call_mcp_tool(name: str, tool_input: dict[str, Any]) -> str:
    result = await get_mcp_session().call_tool(name=name, arguments=tool_input)
    if result.isError:
        return json.dumps({"error": f"MCP tool {name} returned an error"})
    if result.content and hasattr(result.content[0], "text"):
        return result.content[0].text
    return json.dumps({"error": "empty MCP response"})


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

    user_message = (
        f"Assess this sensor reading:\n"
        f"- Reading ID: {reading.id}\n"
        f"- Growing Area ID: {reading.growing_area_id}\n"
        f"- Growing Area Plot ID: {reading.growing_area_plot_id}\n"
        f"- Temperature: {reading.temperature}°F\n"
        f"- Humidity: {reading.humidity}%\n"
        f"- Source: {reading.reading_source.value}\n"
        f"- Read at: {reading.read_at.isoformat()}\n"
        f"- Crop Cycle ID: {reading.crop_cycle_id or 'none'}\n"
    )

    messages = [{"role": "user", "content": user_message}]

    try:
        all_tools = await _get_all_tools()
        for _ in range(MAX_ITERATIONS):
            response = await _client.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=1024,
                system=[{"type": "text", "text": ANOMALY_CHECK_SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
                tools=all_tools,
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

                if block.name in _MCP_TOOL_NAMES:
                    tool_result = await _call_mcp_tool(block.name, block.input)
                else:
                    tool_result = await dispatch_tool(block.name, block.input, db)
                    tool_result = str(tool_result)

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": tool_result,
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
