"""
Tool schemas for the Yearly Yields anomaly-check agent.

These definitions are passed to the Claude API on every agent run.
Claude uses them to decide which tool to call and with what arguments.
The actual execution happens in tool_handlers.py.
"""

YIELD_PLAN_TOOLS = [
    {
        "name": "get_sensor_history",
        "description": (
            "Retrieve recent sensor readings for a growing area to understand current season "
            "temperature and humidity conditions. Returns up to 90 days of readings."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "growing_area_id": {
                    "type": "string",
                    "description": "UUID of the growing area.",
                },
            },
            "required": ["growing_area_id"],
        },
    },
    {
        "name": "get_cycle_yield_history",
        "description": (
            "Retrieve historical harvested crop cycles for a growing area and crop, "
            "including actual vs target yield. Use this to understand past performance "
            "and inform planting quantity recommendations."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "growing_area_id": {
                    "type": "string",
                    "description": "UUID of the growing area.",
                },
                "crop_id": {
                    "type": "string",
                    "description": "UUID of the crop.",
                },
            },
            "required": ["growing_area_id", "crop_id"],
        },
    },
    {
        "name": "get_weather_context",
        "description": (
            "Fetch current regional weather conditions from NOAA for the growing area's "
            "location. Use to factor in seasonal weather risk."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "growing_area_id": {
                    "type": "string",
                    "description": "UUID of the growing area.",
                },
            },
            "required": ["growing_area_id"],
        },
    },
    {
        "name": "save_yield_plan",
        "description": (
            "Save the completed yield plan recommendation. MUST be called as the final "
            "action. Provide your recommended planting quantity, confidence level, and "
            "a farmer-readable reasoning summary."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "crop_cycle_id": {
                    "type": "string",
                    "description": "UUID of the crop cycle this plan is for.",
                },
                "growing_area_id": {
                    "type": "string",
                    "description": "UUID of the growing area.",
                },
                "recommended_plant_quantity": {
                    "type": "number",
                    "description": "Recommended number of seeds or transplants.",
                },
                "target_yield": {
                    "type": "number",
                    "description": "Target yield in the crop's yield unit (lbs or bushels).",
                },
                "confidence_level": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "description": "Confidence in the recommendation.",
                },
                "reasoning": {
                    "type": "string",
                    "description": "Farmer-readable explanation of the recommendation and key risk factors.",
                },
            },
            "required": [
                "crop_cycle_id",
                "growing_area_id",
                "recommended_plant_quantity",
                "target_yield",
                "confidence_level",
                "reasoning",
            ],
        },
    },
]

ANOMALY_CHECK_TOOLS = [
    {
        "name": "get_historical_context",
        "description": (
            "Retrieve weekly historical summaries for a growing area and crop that are "
            "semantically similar to the current sensor reading. Uses vector similarity "
            "search over the past 3 years of data. Always call this first."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "growing_area_id": {
                    "type": "string",
                    "description": "UUID of the growing area.",
                },
                "crop_id": {
                    "type": "string",
                    "description": "UUID of the crop currently growing in the area.",
                },
                "temperature": {
                    "type": "number",
                    "description": "Current temperature reading in °F.",
                },
                "humidity": {
                    "type": "number",
                    "description": "Current humidity reading as a percentage (0-100).",
                },
            },
            "required": ["growing_area_id", "crop_id", "temperature", "humidity"],
        },
    },
    {
        "name": "get_weather_context",
        "description": (
            "Fetch current regional weather conditions from NOAA for the growing area's "
            "location. Call this when a reading appears anomalous to determine whether "
            "a regional weather event explains the deviation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "growing_area_id": {
                    "type": "string",
                    "description": "UUID of the growing area. Used to resolve lat/lon for NOAA lookup.",
                },
            },
            "required": ["growing_area_id"],
        },
    },
    {
        "name": "get_active_alert",
        "description": (
            "Check whether there is an active (unresolved) alert for the given growing area. "
            "Returns the alert record if one exists, or null if none is active. "
            "Always call this before creating a new alert."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "growing_area_id": {
                    "type": "string",
                    "description": "UUID of the growing area to check.",
                },
            },
            "required": ["growing_area_id"],
        },
    },
    {
        "name": "create_alert",
        "description": (
            "Create a new active alert for an anomalous reading. Only call this if "
            "get_active_alert returned no existing alert."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "growing_area_id": {
                    "type": "string",
                    "description": "UUID of the growing area.",
                },
                "crop_cycle_id": {
                    "type": "string",
                    "description": "UUID of the active crop cycle, if one exists.",
                },
                "triggering_reading_id": {
                    "type": "string",
                    "description": "UUID of the sensor reading that triggered this alert.",
                },
                "alert_type": {
                    "type": "string",
                    "enum": [
                        "temperature_high",
                        "temperature_low",
                        "humidity_high",
                        "humidity_low",
                        "combined",
                    ],
                    "description": "The type of anomaly detected.",
                },
                "assessment_summary": {
                    "type": "string",
                    "description": "Farmer-readable explanation of the anomaly. Be concise and specific.",
                },
            },
            "required": [
                "growing_area_id",
                "triggering_reading_id",
                "alert_type",
                "assessment_summary",
            ],
        },
    },
    {
        "name": "update_alert",
        "description": (
            "Update an existing active alert. Use this to increment consecutive_normal_count "
            "when a reading is normal, or to resolve the alert when consecutive_normal_count "
            "reaches 3."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "alert_id": {
                    "type": "string",
                    "description": "UUID of the alert to update.",
                },
                "consecutive_normal_count": {
                    "type": "integer",
                    "description": "Updated count of consecutive normal readings. Reset to 0 on anomaly.",
                },
                "status": {
                    "type": "string",
                    "enum": ["active", "resolved"],
                    "description": "Set to 'resolved' when consecutive_normal_count reaches 3.",
                },
                "assessment_summary": {
                    "type": "string",
                    "description": "Updated assessment summary for this reading.",
                },
            },
            "required": ["alert_id", "consecutive_normal_count", "status"],
        },
    },
    {
        "name": "send_alert_email",
        "description": (
            "Send an alert email to the growing area owner. Only call this if: "
            "(a) you just created a new alert, OR "
            "(b) an active alert exists AND more than ALERT_EMAIL_INTERVAL_HOURS hours "
            "have passed since last_email_sent_at."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "alert_id": {
                    "type": "string",
                    "description": "UUID of the alert to notify about.",
                },
            },
            "required": ["alert_id"],
        },
    },
    {
        "name": "log_reading_assessment",
        "description": (
            "Record the final assessment result on the sensor reading. "
            "MUST be called as the last action on every agent run without exception. "
            "This closes the agent run and marks the reading as assessed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reading_id": {
                    "type": "string",
                    "description": "UUID of the sensor reading being assessed.",
                },
                "assessment_status": {
                    "type": "string",
                    "enum": ["normal", "anomalous", "error"],
                    "description": "The final assessment outcome.",
                },
                "assessment_summary": {
                    "type": "string",
                    "description": "Farmer-readable summary of the assessment. Be concise and specific.",
                },
            },
            "required": ["reading_id", "assessment_status", "assessment_summary"],
        },
    },
]
