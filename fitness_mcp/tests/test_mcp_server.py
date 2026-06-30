"""
Integration tests for the FitPath Fitness MCP Server.

Uses the official MCP Python client (stdio_client + ClientSession) to start the
server as a subprocess and exercise all three tools through the real MCP protocol.

Run with:
    cd fitness_mcp
    uv run pytest tests/ -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import pytest_asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# ---------------------------------------------------------------------------
# Server parameters: launch `python -m fitness_mcp.server`
# ---------------------------------------------------------------------------

SERVER_PARAMS = StdioServerParameters(
    command=sys.executable,
    args=["-m", "fitness_mcp.server"],
    cwd=str(Path(__file__).parent.parent),  # fitness_mcp/ package root
    env=None,
)


# ---------------------------------------------------------------------------
# Helper: run a test against a live session
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"


async def _make_session():
    """Context manager that yields an initialised ClientSession."""
    return stdio_client(SERVER_PARAMS)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_tool_discovery():
    """Tool list must include exactly the three expected tools."""
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_response = await session.list_tools()
            tool_names = {t.name for t in tools_response.tools}
            assert tool_names == {
                "search_exercises_tool",
                "get_exercise_safety_notes_tool",
                "get_weekly_plan_template_tool",
            }, f"Unexpected tool set: {tool_names}"


@pytest.mark.anyio
async def test_search_exercises_bodyweight_only():
    """With no equipment, dumbbell/band exercises must NOT be returned."""
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "search_exercises_tool",
                {"available_equipment": []},
            )
            data = result.content[0].text
            import json
            payload = json.loads(data)
            assert "exercises" in payload
            for exercise in payload["exercises"]:
                required = exercise.get("required_equipment", [])
                assert required == [], (
                    f"Exercise '{exercise['name']}' has required equipment "
                    f"{required} but was returned for a bodyweight-only search."
                )
            assert "filters_applied" in payload
            assert "match_count" in payload


@pytest.mark.anyio
async def test_search_exercises_duration_filter():
    """Duration filter must exclude exercises longer than max_duration_minutes."""
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "search_exercises_tool",
                {"max_duration_minutes": 5},
            )
            import json
            payload = json.loads(result.content[0].text)
            for exercise in payload["exercises"]:
                assert exercise["estimated_duration_minutes"] <= 5, (
                    f"Exercise '{exercise['name']}' duration "
                    f"{exercise['estimated_duration_minutes']} exceeds filter of 5 min."
                )


@pytest.mark.anyio
async def test_search_exercises_with_dumbbells():
    """When dumbbells are available, dumbbell exercises may be returned."""
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "search_exercises_tool",
                {"available_equipment": ["dumbbells"], "level": "beginner"},
            )
            import json
            payload = json.loads(result.content[0].text)
            # Check at least one dumbbell exercise is in the results
            dumbbell_exercises = [
                e for e in payload["exercises"]
                if "dumbbells" in e.get("required_equipment", [])
            ]
            assert len(dumbbell_exercises) >= 1, (
                "Expected at least one dumbbell exercise when dumbbells are available."
            )


@pytest.mark.anyio
async def test_search_exercises_result_capped_at_10():
    """Results must never exceed 10 exercises."""
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "search_exercises_tool",
                {},  # No filters — returns all, should be capped
            )
            import json
            payload = json.loads(result.content[0].text)
            assert payload["match_count"] <= 10, (
                f"match_count {payload['match_count']} exceeds the cap of 10."
            )


@pytest.mark.anyio
async def test_get_exercise_safety_notes_found():
    """Safety notes for a known exercise must return found=True with full data."""
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "get_exercise_safety_notes_tool",
                {"exercise_name": "Cat-Cow Stretch"},
            )
            import json
            payload = json.loads(result.content[0].text)
            assert payload["found"] is True
            assert payload["exercise_name"] == "Cat-Cow Stretch"
            assert payload["safety_notes"] is not None and len(payload["safety_notes"]) > 0
            assert isinstance(payload["instructions"], list)
            assert len(payload["instructions"]) > 0


@pytest.mark.anyio
async def test_get_exercise_safety_notes_not_found():
    """Unknown exercise must return found=False with a descriptive message, not raise."""
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "get_exercise_safety_notes_tool",
                {"exercise_name": "Dragon Squat Ultra Extreme"},
            )
            import json
            payload = json.loads(result.content[0].text)
            assert payload["found"] is False
            assert "message" in payload
            assert payload["safety_notes"] is None


@pytest.mark.anyio
async def test_weekly_template_valid():
    """A valid goal and day count must return a 7-day schedule."""
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "get_weekly_plan_template_tool",
                {"goal": "improve stamina", "days_per_week": 3},
            )
            import json
            payload = json.loads(result.content[0].text)
            assert payload["valid"] is True
            schedule = payload["schedule"]
            assert len(schedule) == 7
            active_days = [d for d in schedule if d["type"] == "active"]
            rest_days = [d for d in schedule if d["type"] == "rest"]
            assert len(active_days) == 3
            assert len(rest_days) == 4
            assert "wellness_note" in payload
            assert "disclaimer" in payload


@pytest.mark.anyio
async def test_weekly_template_rejects_1_day():
    """days_per_week=1 must return valid=False with an error message."""
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "get_weekly_plan_template_tool",
                {"goal": "improve stamina", "days_per_week": 1},
            )
            import json
            payload = json.loads(result.content[0].text)
            assert payload["valid"] is False
            assert "error" in payload


@pytest.mark.anyio
async def test_weekly_template_rejects_7_days():
    """days_per_week=7 must return valid=False with an error message."""
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "get_weekly_plan_template_tool",
                {"goal": "build everyday strength", "days_per_week": 7},
            )
            import json
            payload = json.loads(result.content[0].text)
            assert payload["valid"] is False
            assert "error" in payload


@pytest.mark.anyio
async def test_weekly_template_unknown_goal():
    """An unrecognised goal must return valid=False with supported goals listed."""
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "get_weekly_plan_template_tool",
                {"goal": "become a professional bodybuilder", "days_per_week": 4},
            )
            import json
            payload = json.loads(result.content[0].text)
            assert payload["valid"] is False
            assert "error" in payload


@pytest.mark.anyio
async def test_all_tools_reachable_in_single_session():
    """All three tools must succeed in a single connected session."""
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            import json

            r1 = await session.call_tool(
                "search_exercises_tool",
                {"level": "beginner", "available_equipment": ["yoga_mat"]},
            )
            assert not r1.isError, f"search_exercises_tool failed: {r1}"
            p1 = json.loads(r1.content[0].text)
            assert "exercises" in p1

            r2 = await session.call_tool(
                "get_exercise_safety_notes_tool",
                {"exercise_name": "Glute Bridge"},
            )
            assert not r2.isError, f"get_exercise_safety_notes_tool failed: {r2}"
            p2 = json.loads(r2.content[0].text)
            assert p2["found"] is True

            r3 = await session.call_tool(
                "get_weekly_plan_template_tool",
                {"goal": "build a workout habit", "days_per_week": 4},
            )
            assert not r3.isError, f"get_weekly_plan_template_tool failed: {r3}"
            p3 = json.loads(r3.content[0].text)
            assert p3["valid"] is True
