"""
plan_normalizer.py — Deterministic exercise enricher and validator.

The Plan Generator LLM produces a DraftGeneratedFitnessPlan containing only:
  - exercise name, duration_mins, sets, reps

This module:
  1. Verifies every exercise name exists in exercises.json (case-insensitive).
  2. Enriches exercises with canonical instructions, safety_note, and
     required_equipment from the catalog.
  3. Checks that required_equipment ⊆ user's available equipment.
  4. Computes total_duration_mins per active day.
  5. Converts DraftGeneratedFitnessPlan → GeneratedFitnessPlan.
  6. Raises PlanNormalizationError listing ALL violations found (fail-fast
     per exercise name, but continues to collect all unknown names).

Equipment normalisation rules (per plan spec):
  - User profile stores human-readable labels: "No equipment", "Dumbbells",
    "Resistance bands", "Yoga mat".
  - exercises.json stores canonical snake_case values: "dumbbells",
    "resistance_bands", "yoga_mat".
  - "No equipment" → empty available-equipment set (no canonical values).
  - Optional equipment never causes rejection.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from .schemas import (
    DraftGeneratedFitnessPlan,
    DraftWorkoutDay,
    EnrichedWorkoutExercise,
    EnrichedWorkoutDay,
    EnrichedWeeklyPlan,
    GeneratedFitnessPlan,
)

# Path to the exercise catalog
PROJECT_ROOT = Path(__file__).resolve().parents[3]
EXERCISES_PATH = PROJECT_ROOT / "fitness_mcp" / "fitness_mcp" / "data" / "exercises.json"

# Map from human-readable profile equipment labels → canonical catalog values
EQUIPMENT_LABEL_TO_CANONICAL: dict[str, str] = {
    "Dumbbells": "dumbbells",
    "Resistance bands": "resistance_bands",
    "Yoga mat": "yoga_mat",
    # "No equipment" → not included; handled as empty set
}


class PlanNormalizationError(ValueError):
    """Raised when normalisation fails.  `violations` contains all issues found."""

    def __init__(self, violations: list[str]) -> None:
        self.violations = violations
        super().__init__("; ".join(violations))


def load_exercise_catalog() -> dict[str, dict]:
    """
    Returns {exercise_name_lowercase: exercise_record} from exercises.json.
    exercises.json is a top-level list.
    """
    raw = json.loads(EXERCISES_PATH.read_text(encoding="utf-8"))
    # exercises.json is a top-level list of exercise objects
    exercises: list[dict] = raw if isinstance(raw, list) else raw.get("exercises", [])
    return {ex["name"].lower(): ex for ex in exercises}


def normalise_user_equipment(profile_equipment: list[str]) -> set[str]:
    """
    Converts the profile equipment list (human-readable labels) into a set of
    canonical snake_case equipment values used by exercises.json.

    "No equipment" (or an empty list) → empty set.
    """
    canonical: set[str] = set()
    for label in profile_equipment:
        if label in EQUIPMENT_LABEL_TO_CANONICAL:
            canonical.add(EQUIPMENT_LABEL_TO_CANONICAL[label])
        # "No equipment" and unknown labels are ignored (contribute nothing)
    return canonical


def normalize_plan(
    draft: DraftGeneratedFitnessPlan,
    profile_equipment: list[str],
    catalog: dict[str, dict] | None = None,
) -> GeneratedFitnessPlan:
    """
    Converts a DraftGeneratedFitnessPlan into a GeneratedFitnessPlan by:
      1. Validating all exercise names against the catalog.
      2. Enriching each exercise with canonical catalog data.
      3. Checking equipment compatibility (required_equipment ⊆ available).
      4. Computing total_duration_mins per active day.

    Args:
        draft:            The LLM-generated draft plan.
        profile_equipment: Raw equipment list from the user's stored profile.
        catalog:          Optional pre-loaded catalog (for testing / performance).

    Returns:
        GeneratedFitnessPlan with enriched exercises.

    Raises:
        PlanNormalizationError: If any exercise name is unknown or any required
                                equipment is missing from the user's profile.
    """
    if catalog is None:
        catalog = load_exercise_catalog()

    available_equipment = normalise_user_equipment(profile_equipment)
    violations: list[str] = []

    enriched_days: list[EnrichedWorkoutDay] = []

    for draft_day in draft.week_1.days:
        if draft_day.is_rest:
            enriched_days.append(
                EnrichedWorkoutDay(
                    day=draft_day.day,
                    is_rest=True,
                    focus=draft_day.focus,
                    exercises=[],
                    total_duration_mins=0,
                )
            )
            continue

        enriched_exercises: list[EnrichedWorkoutExercise] = []
        day_duration = 0

        for draft_ex in draft_day.exercises:
            name_lower = draft_ex.name.lower()
            catalog_entry = catalog.get(name_lower)

            if catalog_entry is None:
                violations.append(
                    f"Exercise '{draft_ex.name}' is not in the exercise catalog."
                )
                continue  # Collect all unknown names before raising

            # Check equipment compatibility
            required: list[str] = catalog_entry.get("required_equipment", [])
            missing = [eq for eq in required if eq not in available_equipment]
            if missing:
                violations.append(
                    f"Exercise '{draft_ex.name}' requires {missing} but user's "
                    f"available equipment is {sorted(available_equipment) or 'none'}."
                )
                continue

            # Build enriched exercise from catalog data
            raw_instructions = catalog_entry.get("instructions", [])
            if isinstance(raw_instructions, list):
                instructions = raw_instructions
            else:
                instructions = [str(raw_instructions)]

            safety_note = catalog_entry.get("safety_notes", "")

            duration_mins = draft_ex.duration_mins
            if duration_mins is None:
                duration_mins = catalog_entry.get("estimated_duration_minutes", 5)
            elif duration_mins <= 0:
                violations.append(
                    f"Exercise '{draft_ex.name}' has invalid duration_mins: {duration_mins}. Must be positive."
                )
                continue

            enriched_exercises.append(
                EnrichedWorkoutExercise(
                    name=catalog_entry["name"],   # Canonical casing from catalog
                    duration_mins=duration_mins,
                    sets=draft_ex.sets,
                    reps=draft_ex.reps,
                    instructions=instructions,
                    safety_note=safety_note,
                    required_equipment=required,
                )
            )
            day_duration += duration_mins

        enriched_days.append(
            EnrichedWorkoutDay(
                day=draft_day.day,
                is_rest=False,
                focus=draft_day.focus,
                exercises=enriched_exercises,
                total_duration_mins=day_duration,
            )
        )

    if violations:
        raise PlanNormalizationError(violations)

    return GeneratedFitnessPlan(
        roadmap=draft.roadmap,
        week_1=EnrichedWeeklyPlan(
            week_number=draft.week_1.week_number,
            days=enriched_days,
        ),
    )
