"""
final_validator.py — Pure-Python post-review gate.

Runs after the Plan Reviewer Agent.  The LLM cannot override this check.
Returns ("valid", plan) or ("invalid", violations_list).

Checks performed:
  1. Roadmap duration_days matches profile duration_days.
  2. Roadmap total_weeks == ceil(duration_days / 7).
  3. At least one rest day in Week 1.
  4. No active day exceeds available_time_mins.
  5. No banned terminology in any text field.
  6. No medical treatment claims in any text field.
"""
from __future__ import annotations

import math
import re
from typing import Literal

from .schemas import GeneratedFitnessPlan

# Banned bodybuilding / extreme-fitness terminology (same roots as safety_rules.py)
_BANNED_TERMS = re.compile(
    r"\b(bulk(?:ing)?|shred(?:ding|ded)?|hypertrophy|extreme\s+transformation"
    r"|gain\s+muscle\s+mass|max\s+out|heavy\s+lifting|pump|ripped|cut(?:ting)?)\b",
    re.IGNORECASE,
)

# Medical treatment claim markers
_MEDICAL_CLAIM_TERMS = re.compile(
    r"\b(cure[sd]?|treat(?:ment|s|ing)?|diagnos[ei]|fix(?:es|ing)?\s+(?:your\s+)?(?:pain|injury|condition)"
    r"|heals?\s+(?:your\s+)?(?:pain|injury))\b",
    re.IGNORECASE,
)


def _collect_text_fields(plan: GeneratedFitnessPlan) -> list[str]:
    """Extracts all free-text fields from a plan for terminology scanning."""
    texts: list[str] = []
    roadmap = plan.roadmap
    texts.append(roadmap.progression_notes)
    texts.extend(roadmap.phase_summaries)
    for day in plan.week_1.days:
        texts.append(day.focus)
        for ex in day.exercises:
            texts.append(ex.name)
            texts.extend(ex.instructions)
            texts.append(ex.safety_note)
    return texts


def validate_plan(
    plan: GeneratedFitnessPlan,
    profile_duration_days: int,
    profile_available_time_mins: int,
) -> tuple[Literal["valid", "invalid"], list[str]]:
    """
    Validates the enriched plan against deterministic rules.

    Returns:
        ("valid", [])                  — plan passes all checks
        ("invalid", [violation, ...])  — plan fails one or more checks
    """
    violations: list[str] = []

    # 1. Roadmap duration matches profile
    if plan.roadmap.duration_days != profile_duration_days:
        violations.append(
            f"Roadmap duration_days ({plan.roadmap.duration_days}) does not match "
            f"profile duration_days ({profile_duration_days})."
        )

    # 2. total_weeks == ceil(duration_days / 7)
    expected_weeks = math.ceil(plan.roadmap.duration_days / 7)
    if plan.roadmap.total_weeks != expected_weeks:
        violations.append(
            f"Roadmap total_weeks ({plan.roadmap.total_weeks}) must equal "
            f"ceil({plan.roadmap.duration_days}/7) = {expected_weeks}."
        )

    # 3. At least one rest day in Week 1
    rest_days = [d for d in plan.week_1.days if d.is_rest]
    if not rest_days:
        violations.append("Week 1 contains no rest day. At least one rest day is required.")

    # 4. No active day exceeds available_time_mins
    for day in plan.week_1.days:
        if not day.is_rest and day.total_duration_mins > profile_available_time_mins:
            violations.append(
                f"Day '{day.day}' total duration ({day.total_duration_mins} mins) "
                f"exceeds the available_time_mins limit ({profile_available_time_mins} mins)."
            )

    # 5. No banned terminology in any text field
    for text in _collect_text_fields(plan):
        match = _BANNED_TERMS.search(text)
        if match:
            violations.append(
                f"Plan contains prohibited term '{match.group()}' in text: "
                f"'{text[:80]}{'...' if len(text) > 80 else ''}'"
            )
            break  # One report is enough; the reviewer must fix the whole plan

    # 6. No medical treatment claims
    for text in _collect_text_fields(plan):
        match = _MEDICAL_CLAIM_TERMS.search(text)
        if match:
            violations.append(
                f"Plan contains medical claim '{match.group()}' in text: "
                f"'{text[:80]}{'...' if len(text) > 80 else ''}'"
            )
            break

    if violations:
        return "invalid", violations
    return "valid", []
