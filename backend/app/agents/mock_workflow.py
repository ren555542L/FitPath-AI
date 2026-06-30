"""
mock_workflow.py — Deterministic mock workflow for FitPath.

This module intentionally does NOT import anything from:
  - google.adk
  - google.genai
  - google.adk.tools

It uses only:
  - The exercises.json catalog (via plan_normalizer.load_exercise_catalog)
  - The deterministic plan normalizer (plan_normalizer.normalize_plan)
  - The deterministic final validator (final_validator.validate_plan)
  - FitPath schema types

All trace events are labeled with mock_mode=True.
The execution_mode field is always "mock".
"""
from __future__ import annotations

import math
import time
import uuid
from typing import Any

from .plan_normalizer import load_exercise_catalog, normalize_plan, PlanNormalizationError
from .final_validator import validate_plan
from .trace import emit_trace
from .schemas import (
    WorkflowInput,
    WorkflowResult,
    DraftGeneratedFitnessPlan,
    DraftWeeklyPlan,
    DraftWorkoutDay,
    DraftWorkoutExercise,
    FitnessRoadmap,
    GeneratedFitnessPlan,
    SafetyGuidanceResponse,
    PlanReviewResult,
)

# ---------------------------------------------------------------------------
# Catalog-based exercise selection helpers
# ---------------------------------------------------------------------------

# Map profile equipment labels → catalog canonical values (mirrors plan_normalizer)
_EQUIPMENT_MAP: dict[str, str] = {
    "Dumbbells": "dumbbells",
    "Resistance bands": "resistance_bands",
    "Yoga mat": "yoga_mat",
}

# Fitness-level progression map for difficulty filtering
_LEVEL_ORDER = {"beginner": 0, "returning after a break": 1, "intermediate": 2}

# Day-of-week names for week schedule
_WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _canonical_equipment(profile_equipment: list[str]) -> set[str]:
    """Convert profile equipment labels to catalog canonical values."""
    result: set[str] = set()
    for label in profile_equipment:
        if label in _EQUIPMENT_MAP:
            result.add(_EQUIPMENT_MAP[label])
    return result


def _select_exercises(
    catalog: dict[str, dict],
    fitness_level: str,
    available_equipment: set[str],
    available_time_mins: int,
    count: int,
) -> list[dict]:
    """
    Select `count` catalog exercises suitable for the given fitness level and equipment.

    Strategy:
    - Filter to exercises the user has equipment for (required_equipment ⊆ available OR empty).
    - Prefer the user's fitness level; fall back to beginner for short sessions.
    - Select until total estimated_duration_minutes fits within available_time_mins.
    - Return at most `count` exercises.
    """
    level_rank = _LEVEL_ORDER.get(fitness_level.lower(), 0)

    def _is_compatible(ex: dict) -> bool:
        required = set(ex.get("required_equipment", []))
        return required.issubset(available_equipment)

    def _level_rank(ex: dict) -> int:
        return _LEVEL_ORDER.get(ex.get("difficulty", "beginner").lower(), 0)

    compatible = [ex for ex in catalog.values() if _is_compatible(ex)]

    # Sort: prefer exercises at or below user's level, then by estimated duration ascending
    compatible.sort(key=lambda e: (abs(_level_rank(e) - level_rank), e.get("estimated_duration_minutes", 5)))

    selected: list[dict] = []
    total_mins = 0
    for ex in compatible:
        dur = ex.get("estimated_duration_minutes", 5)
        if total_mins + dur > available_time_mins:
            continue
        selected.append(ex)
        total_mins += dur
        if len(selected) >= count:
            break

    # If nothing fits (very short time), just take the shortest single exercise
    if not selected and compatible:
        selected = [min(compatible, key=lambda e: e.get("estimated_duration_minutes", 5))]

    return selected


def _build_draft_plan(
    workflow_input: WorkflowInput,
    catalog: dict[str, dict],
) -> DraftGeneratedFitnessPlan:
    """
    Deterministically build a DraftGeneratedFitnessPlan from the catalog.
    No LLM calls — pure Python selection logic.
    """
    available_equipment = _canonical_equipment(workflow_input.equipment)
    duration_days = workflow_input.duration_days
    total_weeks = math.ceil(duration_days / 7)
    days_per_week = workflow_input.days_per_week

    # Pick exercises for a workout day (up to 4 exercises)
    exercises_pool = _select_exercises(
        catalog=catalog,
        fitness_level=workflow_input.fitness_level,
        available_equipment=available_equipment,
        available_time_mins=workflow_input.available_time_mins,
        count=4,
    )

    # Assign workouts to preferred_days; rest to remaining days
    preferred = workflow_input.preferred_days[:days_per_week] if workflow_input.preferred_days else _WEEKDAYS[:days_per_week]
    week_days: list[DraftWorkoutDay] = []

    for day_name in _WEEKDAYS:
        if day_name in preferred:
            # Distribute exercises across workout days (rotate pool)
            day_exercises = [
                DraftWorkoutExercise(name=ex["name"])  # duration_mins=None → normalizer fills from catalog
                for ex in exercises_pool
            ]
            week_days.append(DraftWorkoutDay(
                day=day_name,
                is_rest=False,
                focus=workflow_input.goal,
                exercises=day_exercises,
            ))
        else:
            week_days.append(DraftWorkoutDay(
                day=day_name,
                is_rest=True,
                focus="Rest and recovery",
                exercises=[],
            ))

    # Build phase summaries
    num_phases = math.ceil(total_weeks / 4)
    phase_summaries = [f"Phase {i + 1}: Progressive {workflow_input.goal} training" for i in range(num_phases)]

    roadmap = FitnessRoadmap(
        duration_days=duration_days,
        total_weeks=total_weeks,
        phase_summaries=phase_summaries,
        progression_notes=(
            f"A {duration_days}-day {workflow_input.goal} program for {workflow_input.fitness_level} level. "
            f"Workouts scheduled {days_per_week} days per week with full rest days for recovery."
        ),
    )

    return DraftGeneratedFitnessPlan(
        roadmap=roadmap,
        week_1=DraftWeeklyPlan(week_number=1, days=week_days),
    )


# ---------------------------------------------------------------------------
# Public mock workflow entrypoint
# ---------------------------------------------------------------------------

async def run_mock_workflow(workflow_input: WorkflowInput) -> WorkflowResult:
    """
    Deterministic mock plan generation.

    Never calls Gemini, ADK agents, MCP tools, or SkillToolset.
    Returns the same WorkflowResult schema as the real ADK workflow.
    All trace events include mock_mode=True.
    """
    request_id = f"mock-{uuid.uuid4().hex[:12]}"
    trace_events: list[dict] = []

    # 1. Safety routing — same semantics as live workflow
    if workflow_input.safety_status == "medical_review_required":
        trace_events.append(emit_trace(
            request_id=request_id,
            workflow_stage="safety_check",
            agent_name="mock_safety_router",
            outcome="blocked",
            duration_ms=0.1,
            mock_mode=True,
        ))
        return WorkflowResult(
            request_id=request_id,
            workflow_status="safety_blocked",
            execution_mode="mock",
            safety_guidance=SafetyGuidanceResponse(
                safety_status="medical_review_required",
                title="Medical Review Required",
                message=(
                    workflow_input.safety_message
                    or "Your notes suggest a medical or injury concern. Please consult a qualified healthcare professional before starting a new fitness programme. FitPath provides general wellness information only."
                ),
                can_proceed=False,
            ),
            trace_events=trace_events,
        )

    if workflow_input.safety_status == "general_fitness_redirect":
        trace_events.append(emit_trace(
            request_id=request_id,
            workflow_stage="safety_check",
            agent_name="mock_safety_router",
            outcome="redirected",
            duration_ms=0.1,
            mock_mode=True,
        ))
        return WorkflowResult(
            request_id=request_id,
            workflow_status="redirected",
            execution_mode="mock",
            safety_guidance=SafetyGuidanceResponse(
                safety_status="general_fitness_redirect",
                title="Let's Adjust Your Goal",
                message=(
                    workflow_input.safety_message
                    or "Your requested goal is outside FitPath's general wellness scope. We focus on gradual, sustainable fitness improvement — not extreme transformations. Let's build a realistic plan for you."
                ),
                can_proceed=False,
            ),
            trace_events=trace_events,
        )

    # 2. Load catalog
    t0 = time.perf_counter()
    catalog = load_exercise_catalog()
    trace_events.append(emit_trace(
        request_id=request_id,
        workflow_stage="catalog_load",
        agent_name="mock_plan_builder",
        outcome="success",
        duration_ms=round((time.perf_counter() - t0) * 1000, 2),
        mock_mode=True,
    ))

    # 3. Build draft plan deterministically
    t0 = time.perf_counter()
    try:
        draft = _build_draft_plan(workflow_input, catalog)
    except Exception as e:
        trace_events.append(emit_trace(
            request_id=request_id,
            workflow_stage="draft_build",
            agent_name="mock_plan_builder",
            outcome="failed",
            duration_ms=round((time.perf_counter() - t0) * 1000, 2),
            error_type=type(e).__name__,
            mock_mode=True,
        ))
        return WorkflowResult(
            request_id=request_id,
            workflow_status="normalisation_failed",
            execution_mode="mock",
            review_result=PlanReviewResult(passed=False, violations=[f"Draft build failed: {e}"]),
            trace_events=trace_events,
        )

    trace_events.append(emit_trace(
        request_id=request_id,
        workflow_stage="draft_build",
        agent_name="mock_plan_builder",
        outcome="success",
        duration_ms=round((time.perf_counter() - t0) * 1000, 2),
        mock_mode=True,
    ))

    # 4. Normalise (reuses the real deterministic normalizer)
    t0 = time.perf_counter()
    try:
        enriched_plan: GeneratedFitnessPlan = normalize_plan(
            draft, workflow_input.equipment, catalog
        )
    except PlanNormalizationError as e:
        trace_events.append(emit_trace(
            request_id=request_id,
            workflow_stage="normalisation",
            agent_name="mock_normalizer",
            outcome="failed",
            duration_ms=round((time.perf_counter() - t0) * 1000, 2),
            error_type="PlanNormalizationError",
            mock_mode=True,
        ))
        return WorkflowResult(
            request_id=request_id,
            workflow_status="normalisation_failed",
            execution_mode="mock",
            review_result=PlanReviewResult(passed=False, violations=e.violations),
            trace_events=trace_events,
        )

    trace_events.append(emit_trace(
        request_id=request_id,
        workflow_stage="normalisation",
        agent_name="mock_normalizer",
        outcome="success",
        duration_ms=round((time.perf_counter() - t0) * 1000, 2),
        mock_mode=True,
    ))

    # 5. Final validation (reuses the real deterministic validator)
    t0 = time.perf_counter()
    val_status, val_violations = validate_plan(
        enriched_plan,
        profile_duration_days=workflow_input.duration_days,
        profile_available_time_mins=workflow_input.available_time_mins,
    )
    trace_events.append(emit_trace(
        request_id=request_id,
        workflow_stage="final_validation",
        agent_name="mock_validator",
        outcome="success" if val_status == "valid" else "failed",
        duration_ms=round((time.perf_counter() - t0) * 1000, 2),
        mock_mode=True,
    ))

    if val_status == "invalid":
        return WorkflowResult(
            request_id=request_id,
            workflow_status="review_failed",
            execution_mode="mock",
            review_result=PlanReviewResult(passed=False, violations=val_violations),
            trace_events=trace_events,
        )

    return WorkflowResult(
        request_id=request_id,
        workflow_status="completed",
        execution_mode="mock",
        fitness_plan=enriched_plan,
        review_result=PlanReviewResult(
            passed=True,
            violations=[],
            approved_plan=enriched_plan,
        ),
        trace_events=trace_events,
    )
