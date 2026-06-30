"""
FitPath Fitness MCP Tools

Read-only tools for exercise lookup, safety notes, and weekly plan templates.
No external APIs, no database writes, no user/guest data.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_EXERCISES_PATH = Path(__file__).parent / "data" / "exercises.json"

# ---------------------------------------------------------------------------
# Exercise data loader (lazy, cached)
# ---------------------------------------------------------------------------

_exercises_cache: list[dict[str, Any]] | None = None


def _load_exercises() -> list[dict[str, Any]]:
    global _exercises_cache
    if _exercises_cache is None:
        try:
            with _EXERCISES_PATH.open("r", encoding="utf-8") as f:
                _exercises_cache = json.load(f)
            logger.info("Loaded %d exercises from database.", len(_exercises_cache))
        except Exception as exc:
            logger.error("Failed to load exercises.json: %s", exc)
            _exercises_cache = []
    return _exercises_cache


# ---------------------------------------------------------------------------
# Tool: search_exercises
# ---------------------------------------------------------------------------

def search_exercises(
    level: str | None = None,
    available_equipment: list[str] | None = None,
    max_duration_minutes: int | None = None,
    focus_tags: list[str] | None = None,
) -> dict[str, Any]:
    """
    Search the curated exercise library.

    Args:
        level: Difficulty filter. One of "beginner", "intermediate", or "advanced".
        available_equipment: List of equipment the user has available. An exercise is
            returned only if its required_equipment is a subset of this list.
            Pass an empty list or omit to return only bodyweight exercises.
        max_duration_minutes: Exclude exercises longer than this many minutes.
        focus_tags: Return exercises that match at least one of these tags.

    Returns:
        A structured dict with filters_applied, match_count, and exercises list.
    """
    exercises = _load_exercises()
    filters_applied: list[str] = []

    results = list(exercises)

    # --- Filter by difficulty level ---
    if level is not None:
        level_lower = level.strip().lower()
        results = [e for e in results if e.get("difficulty", "").lower() == level_lower]
        filters_applied.append(f"level={level_lower}")

    # --- Filter by equipment ---
    # An exercise is included only if its required_equipment is a
    # subset of the user's available_equipment.
    if available_equipment is not None:
        user_equip = {item.strip().lower() for item in available_equipment}
        filters_applied.append(f"available_equipment={sorted(user_equip)}")

        def _equipment_ok(exercise: dict[str, Any]) -> bool:
            required = {item.strip().lower() for item in exercise.get("required_equipment", [])}
            return required.issubset(user_equip)

        results = [e for e in results if _equipment_ok(e)]

    # --- Filter by duration ---
    if max_duration_minutes is not None:
        results = [
            e for e in results
            if e.get("estimated_duration_minutes", 0) <= max_duration_minutes
        ]
        filters_applied.append(f"max_duration_minutes={max_duration_minutes}")

    # --- Filter by focus tags ---
    if focus_tags:
        tag_set = {t.strip().lower() for t in focus_tags}
        results = [
            e for e in results
            if tag_set.intersection({ft.lower() for ft in e.get("focus_tags", [])})
        ]
        filters_applied.append(f"focus_tags={sorted(tag_set)}")

    # Cap results at 10
    capped = results[:10]

    return {
        "filters_applied": filters_applied,
        "match_count": len(capped),
        "total_before_cap": len(results),
        "exercises": [
            {
                "name": e["name"],
                "category": e["category"],
                "difficulty": e["difficulty"],
                "required_equipment": e.get("required_equipment", []),
                "optional_equipment": e.get("optional_equipment", []),
                "focus_tags": e.get("focus_tags", []),
                "estimated_duration_minutes": e.get("estimated_duration_minutes"),
            }
            for e in capped
        ],
    }


# ---------------------------------------------------------------------------
# Tool: get_exercise_safety_notes
# ---------------------------------------------------------------------------

def get_exercise_safety_notes(exercise_name: str) -> dict[str, Any]:
    """
    Return safety notes and instructions for a specific exercise.

    Args:
        exercise_name: The exact or approximate name of the exercise.

    Returns:
        A structured dict with the exercise details and safety notes,
        or a not-found result if the exercise cannot be located.
    """
    exercises = _load_exercises()
    query = exercise_name.strip().lower()

    # Try exact match first, then substring match
    match: dict[str, Any] | None = None
    for exercise in exercises:
        if exercise.get("name", "").lower() == query:
            match = exercise
            break

    if match is None:
        for exercise in exercises:
            if query in exercise.get("name", "").lower():
                match = exercise
                break

    if match is None:
        logger.info("Exercise not found: %r", exercise_name)
        return {
            "found": False,
            "exercise_name": exercise_name,
            "message": (
                f"No exercise named '{exercise_name}' was found in the FitPath library. "
                "Use search_exercises to browse available exercises."
            ),
            "safety_notes": None,
            "instructions": None,
        }

    return {
        "found": True,
        "exercise_name": match["name"],
        "category": match["category"],
        "difficulty": match["difficulty"],
        "estimated_duration_minutes": match.get("estimated_duration_minutes"),
        "required_equipment": match.get("required_equipment", []),
        "optional_equipment": match.get("optional_equipment", []),
        "focus_tags": match.get("focus_tags", []),
        "instructions": match.get("instructions", []),
        "safety_notes": match.get("safety_notes", "No specific safety notes on record."),
    }


# ---------------------------------------------------------------------------
# Tool: get_weekly_plan_template
# ---------------------------------------------------------------------------

_GOAL_FOCUS_MAP: dict[str, list[str]] = {
    "improve stamina": ["low-impact cardio", "low-impact cardio", "recovery", "low-impact cardio"],
    "build everyday strength": ["functional strength", "recovery", "functional strength", "balance and posture"],
    "improve mobility": ["mobility", "recovery", "mobility", "balance and posture"],
    "improve posture and balance": ["balance and posture", "mobility", "recovery", "balance and posture"],
    "lose weight gradually": ["low-impact cardio", "functional strength", "recovery", "low-impact cardio"],
    "build a workout habit": ["mobility", "functional strength", "recovery", "low-impact cardio"],
}

_WELLNESS_NOTES: dict[str, str] = {
    "improve stamina": "Focus on steady-state movement and building duration gradually. Never sacrifice form for speed.",
    "build everyday strength": "Rest adequately between strength days. Consistency over weeks matters more than intensity.",
    "improve mobility": "Gentle mobility work daily is safe and beneficial. Breathe deeply through each stretch.",
    "improve posture and balance": "Posture improvements take time. Practice micro-corrections throughout your day.",
    "lose weight gradually": "Sustainable weight management comes from consistent movement and rest, not extreme effort.",
    "build a workout habit": "Focus on showing up regularly. A 10-minute session completed beats a 60-minute session skipped.",
}


def get_weekly_plan_template(goal: str, days_per_week: int) -> dict[str, Any]:
    """
    Generate a deterministic weekly workout template.

    Args:
        goal: The user's primary wellness goal. Must be one of the supported goals.
        days_per_week: Number of active workout days (2-6 inclusive).

    Returns:
        A structured weekly schedule with active/rest days and wellness notes,
        or a validation error if inputs are out of range.
    """
    # --- Validate days_per_week ---
    if not isinstance(days_per_week, int) or days_per_week < 2 or days_per_week > 6:
        return {
            "valid": False,
            "error": (
                f"days_per_week must be between 2 and 6 inclusive. "
                f"Received: {days_per_week!r}"
            ),
            "schedule": None,
        }

    # --- Resolve goal ---
    goal_lower = goal.strip().lower()
    focus_cycle = _GOAL_FOCUS_MAP.get(goal_lower)

    if focus_cycle is None:
        supported = list(_GOAL_FOCUS_MAP.keys())
        return {
            "valid": False,
            "error": (
                f"Goal '{goal}' is not recognised. Supported goals: {supported}"
            ),
            "schedule": None,
        }

    # --- Build 7-day schedule ---
    days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    # Distribute active days evenly across the week
    # Strategy: spread active days with at least one rest day between them where possible
    active_slots: list[int] = []
    if days_per_week <= 3:
        # Spread with gaps
        step = 7 // days_per_week
        for i in range(days_per_week):
            active_slots.append(min(i * step, 6))
    else:
        # For 4-6 days, spread with at least one rest embedded
        # Simple pattern: fill Mon-Sat for 6 days, skip Sun
        # For fewer days, add rests near mid-week and end
        patterns = {
            4: [0, 1, 3, 4],   # Mon, Tue, Thu, Fri
            5: [0, 1, 2, 4, 5], # Mon, Tue, Wed, Fri, Sat
            6: [0, 1, 2, 3, 4, 5], # Mon-Sat
        }
        active_slots = patterns[days_per_week]

    # Assign focus categories cycling through the focus list
    schedule = []
    focus_idx = 0
    for day_idx, day_name in enumerate(days_of_week):
        if day_idx in active_slots:
            category = focus_cycle[focus_idx % len(focus_cycle)]
            schedule.append({
                "day": day_name,
                "type": "active",
                "focus_category": category,
                "suggested_duration_minutes": 20,
            })
            focus_idx += 1
        else:
            schedule.append({
                "day": day_name,
                "type": "rest",
                "focus_category": None,
                "suggested_duration_minutes": 0,
            })

    wellness_note = _WELLNESS_NOTES.get(goal_lower, "Consistency and rest are both part of a healthy routine.")

    return {
        "valid": True,
        "goal": goal,
        "days_per_week": days_per_week,
        "rest_days": 7 - days_per_week,
        "wellness_note": wellness_note,
        "disclaimer": (
            "FitPath provides general wellness guidance only and does not diagnose, "
            "treat, or replace professional medical advice. Consult your doctor "
            "before starting any new exercise programme."
        ),
        "schedule": schedule,
    }
