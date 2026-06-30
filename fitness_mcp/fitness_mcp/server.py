"""
FitPath Fitness MCP Server

Runs over stdio using FastMCP. All protocol messages go to stdout.
All logs go to stderr. No database writes, no external API calls.

Usage:
    cd fitness_mcp
    uv run python -m fitness_mcp.server
"""

from __future__ import annotations

import logging
import sys

from mcp.server.fastmcp import FastMCP

from fitness_mcp.tools import (
    get_exercise_safety_notes,
    get_weekly_plan_template,
    search_exercises,
)

# ---------------------------------------------------------------------------
# Logging: stderr only — stdout is reserved exclusively for MCP protocol
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastMCP server
# ---------------------------------------------------------------------------
mcp = FastMCP(name="fitpath-fitness-mcp")


# ---------------------------------------------------------------------------
# Register tools
# ---------------------------------------------------------------------------

@mcp.tool()
def search_exercises_tool(
    level: str | None = None,
    available_equipment: list[str] | None = None,
    max_duration_minutes: int | None = None,
    focus_tags: list[str] | None = None,
) -> dict:
    """
    Search the curated FitPath exercise library.

    Returns exercises whose required_equipment is a subset of the user's
    available_equipment. Results are capped at 10 matches.

    Args:
        level: Difficulty level filter (e.g. "beginner").
        available_equipment: Equipment the user has available. Pass an empty
            list to return only bodyweight exercises.
        max_duration_minutes: Exclude exercises longer than this.
        focus_tags: Return exercises matching at least one of these tags.
    """
    logger.info(
        "search_exercises called: level=%r equipment=%r duration=%r tags=%r",
        level, available_equipment, max_duration_minutes, focus_tags,
    )
    return search_exercises(
        level=level,
        available_equipment=available_equipment,
        max_duration_minutes=max_duration_minutes,
        focus_tags=focus_tags,
    )


@mcp.tool()
def get_exercise_safety_notes_tool(exercise_name: str) -> dict:
    """
    Return the safety notes and step-by-step instructions for a named exercise.

    Returns a structured not-found response if the exercise does not exist
    in the library rather than raising an exception.

    Args:
        exercise_name: Name of the exercise (case-insensitive, partial match supported).
    """
    logger.info("get_exercise_safety_notes called: exercise_name=%r", exercise_name)
    return get_exercise_safety_notes(exercise_name)


@mcp.tool()
def get_weekly_plan_template_tool(goal: str, days_per_week: int) -> dict:
    """
    Generate a deterministic 7-day weekly workout template.

    Validates that days_per_week is between 2 and 6. Returns a schedule with
    active and rest days, suggested focus categories, and a wellness note.
    Does not make medical or weight-loss claims.

    Args:
        goal: The user's primary wellness goal (e.g. "improve stamina").
        days_per_week: Number of active workout days per week (2-6 inclusive).
    """
    logger.info(
        "get_weekly_plan_template called: goal=%r days_per_week=%r",
        goal, days_per_week,
    )
    return get_weekly_plan_template(goal=goal, days_per_week=days_per_week)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    logger.info("FitPath Fitness MCP Server starting (stdio transport).")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
