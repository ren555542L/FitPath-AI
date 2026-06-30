"""
workflow.py — FitPath ADK graph-based workflow.

Protects the singleton McpToolset by serializing execution using a global asyncio.Lock.

Design notes:
  - All function nodes use parameter_binding='state' (ADK default).
  - Individual profile fields are passed via state_delta before the workflow runs.
  - intake_router reads individual state fields, not a typed WorkflowInput node_input.
  - new_message is always supplied so the runner has a trigger event.
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.apps import App
from google.adk.events.event import Event
from google.adk.runners import InMemoryRunner
from google.adk.tools.mcp_tool import McpToolset
from google.adk.workflow import Workflow, START
from google.genai import types as genai_types

from .schemas import (
    WorkflowInput,
    WorkflowResult,
    SafetyGuidanceResponse,
    DraftGeneratedFitnessPlan,
    GeneratedFitnessPlan,
    PlanReviewResult,
)
from .plan_normalizer import normalize_plan, PlanNormalizationError
from .final_validator import validate_plan
from .trace import emit_trace

# A global lock to serialize workflow executions and protect the shared stdio MCP session.
# Documented MVP limitation for single-user/local-development.
_workflow_lock = asyncio.Lock()


# ---------------------------------------------------------------------------
# 1. Custom Python Nodes (Functions)
# ---------------------------------------------------------------------------

def intake_router(
    ctx: Any,
    node_input: Any,
    safety_status: str = "safe",
    goal: str = "",
    fitness_level: str = "",
    duration_days: int = 30,
    available_time_mins: int = 30,
    days_per_week: int = 3,
    equipment: list = None,
    preferred_days: list = None,
    safety_message: str = "",
):
    """
    Python node — reads profile fields from ctx.state and routes:
      - 'needs_guidance' branch for medical_review_required / general_fitness_redirect
      - 'safe' branch for safe profiles

    All parameters except ctx and node_input are bound from ctx.state.
    """
    if equipment is None:
        equipment = []
    if preferred_days is None:
        preferred_days = []

    state_delta = {
        "goal": goal,
        "fitness_level": fitness_level,
        "duration_days": duration_days,
        "available_time_mins": available_time_mins,
        "days_per_week": days_per_week,
        "equipment": equipment,
        "preferred_days": preferred_days,
        "safety_status": safety_status,
        "safety_message": safety_message,
        "focus_tags": [],          # populated by intake_agent via fitness_context; default empty for template substitution
        "fitness_context": {},
        "trace_events": [],
    }

    if safety_status in ("medical_review_required", "general_fitness_redirect"):
        return Event(output={"safety_status": safety_status}, route="needs_guidance", state=state_delta)

    return Event(output={"safety_status": safety_status}, route="safe", state=state_delta)


def normalize_plan_node(ctx: Any, node_input: Any):
    """
    Deterministic plan normalizer.
    Converts DraftGeneratedFitnessPlan → Enriched GeneratedFitnessPlan.
    Reads the draft plan from node_input (previous agent's output).
    """
    start_time = time.perf_counter()
    request_id = ctx.session.id

    # node_input is the output dict from the plan_generator_agent
    # The agent output_key="draft_plan" so state["draft_plan"] has the data
    draft_data = node_input
    if draft_data is None:
        draft_data = ctx.state.get("draft_plan")

    try:
        if isinstance(draft_data, str):
            draft_data = json.loads(draft_data)

        draft_plan = DraftGeneratedFitnessPlan(**draft_data)
        profile_equipment = ctx.state.get("equipment", [])

        enriched_plan = normalize_plan(draft_plan, profile_equipment)
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        trace = emit_trace(
            request_id=request_id,
            workflow_stage="normalisation",
            agent_name="plan_normalizer",
            outcome="success",
            duration_ms=duration_ms,
        )

        trace_events = list(ctx.state.get("trace_events", []))
        trace_events.append(trace)

        return Event(
            output=enriched_plan.model_dump(),
            route="normalized",
            state={
                "enriched_plan": enriched_plan.model_dump(),
                "trace_events": trace_events,
            },
        )
    except PlanNormalizationError as e:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        trace = emit_trace(
            request_id=request_id,
            workflow_stage="normalisation",
            agent_name="plan_normalizer",
            outcome="failed",
            duration_ms=duration_ms,
            error_type="PlanNormalizationError",
        )

        trace_events = list(ctx.state.get("trace_events", []))
        trace_events.append(trace)

        return Event(
            output={"violations": e.violations},
            route="normalization_failed",
            state={
                "normalization_error": e.violations,
                "trace_events": trace_events,
            },
        )
    except Exception as e:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        trace = emit_trace(
            request_id=request_id,
            workflow_stage="normalisation",
            agent_name="plan_normalizer",
            outcome="failed",
            duration_ms=duration_ms,
            error_type=type(e).__name__,
        )

        trace_events = list(ctx.state.get("trace_events", []))
        trace_events.append(trace)

        return Event(
            output={"violations": [f"Normalisation error: {str(e)}"]},
            route="normalization_failed",
            state={
                "normalization_error": [str(e)],
                "trace_events": trace_events,
            },
        )


def final_validator_node(ctx: Any, node_input: Any):
    """
    Pure Python final validator. Enforces constraints on PlanReviewResult.
    Reads the review result from node_input (previous agent output).
    """
    start_time = time.perf_counter()
    request_id = ctx.session.id

    # node_input is the review agent's output dict
    review_data = node_input
    if review_data is None:
        review_data = ctx.state.get("review_result", {})

    if isinstance(review_data, str):
        try:
            review_data = json.loads(review_data)
        except Exception:
            review_data = {}

    if not isinstance(review_data, dict):
        review_data = {}

    reviewer_passed = review_data.get("passed", False)
    violations = list(review_data.get("violations", []))
    approved_plan_dict = review_data.get("approved_plan")

    if approved_plan_dict:
        try:
            plan = GeneratedFitnessPlan(**approved_plan_dict)
            profile_duration_days = int(ctx.state.get("duration_days", 0))
            profile_available_time_mins = int(ctx.state.get("available_time_mins", 0))

            val_status, val_violations = validate_plan(
                plan,
                profile_duration_days=profile_duration_days,
                profile_available_time_mins=profile_available_time_mins,
            )
            if val_status == "invalid":
                reviewer_passed = False
                violations.extend(val_violations)
        except Exception as e:
            reviewer_passed = False
            violations.append(f"Validation error: {str(e)}")
    else:
        if reviewer_passed:
            reviewer_passed = False
            violations.append("Reviewer approved the plan but omitted the approved_plan object.")

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    outcome = "success" if reviewer_passed else "failed"

    trace = emit_trace(
        request_id=request_id,
        workflow_stage="final_validation",
        agent_name="final_validator",
        outcome=outcome,
        duration_ms=duration_ms,
        error_type=None if reviewer_passed else "ValidationError",
    )

    trace_events = list(ctx.state.get("trace_events", []))
    trace_events.append(trace)

    if reviewer_passed:
        return Event(
            output={
                "passed": True,
                "violations": [],
                "approved_plan": approved_plan_dict,
            },
            route="valid",
            state={"trace_events": trace_events},
        )
    else:
        return Event(
            output={
                "passed": False,
                "violations": list(set(violations)),
                "approved_plan": None,
            },
            route="invalid",
            state={"trace_events": trace_events},
        )


# ---------------------------------------------------------------------------
# 2. Result Packaging Nodes
# ---------------------------------------------------------------------------

def package_safety_result(ctx: Any, node_input: Any) -> WorkflowResult:
    safety_status = ctx.state.get("safety_status", "medical_review_required")
    safety_message = ctx.state.get("safety_message", "")

    # Try to parse node_input as safety guidance if it's a dict
    if isinstance(node_input, dict) and "safety_status" in node_input:
        guidance_data = node_input
    else:
        guidance_data = ctx.state.get("safety_guidance", {})

    if not guidance_data or "title" not in guidance_data:
        # Build a minimal guidance from state
        guidance_data = {
            "safety_status": safety_status,
            "title": "Safety Review Required" if safety_status == "medical_review_required" else "General Fitness Redirect",
            "message": safety_message or "Please consult a professional.",
            "can_proceed": False,
        }

    guidance = SafetyGuidanceResponse(**guidance_data)
    status_map = {
        "medical_review_required": "safety_blocked",
        "general_fitness_redirect": "redirected",
    }
    workflow_status = status_map.get(guidance.safety_status, "safety_blocked")
    return WorkflowResult(
        request_id=ctx.session.id,
        workflow_status=workflow_status,
        safety_guidance=guidance,
        trace_events=list(ctx.state.get("trace_events", [])),
    )


def package_normalization_failure(ctx: Any, node_input: Any) -> WorkflowResult:
    violations = []
    if isinstance(node_input, dict):
        violations = node_input.get("violations", ["Normalisation failed"])
    return WorkflowResult(
        request_id=ctx.session.id,
        workflow_status="normalisation_failed",
        review_result=PlanReviewResult(
            passed=False,
            violations=violations or ["Normalisation failed"],
        ),
        trace_events=list(ctx.state.get("trace_events", [])),
    )


def package_valid_result(ctx: Any, node_input: Any) -> WorkflowResult:
    plan = GeneratedFitnessPlan(**node_input["approved_plan"])
    return WorkflowResult(
        request_id=ctx.session.id,
        workflow_status="completed",
        fitness_plan=plan,
        review_result=PlanReviewResult(passed=True, violations=[]),
        trace_events=list(ctx.state.get("trace_events", [])),
    )


def package_invalid_result(ctx: Any, node_input: Any) -> WorkflowResult:
    violations = []
    if isinstance(node_input, dict):
        violations = node_input.get("violations", [])
    return WorkflowResult(
        request_id=ctx.session.id,
        workflow_status="review_failed",
        review_result=PlanReviewResult(
            passed=False,
            violations=violations,
        ),
        trace_events=list(ctx.state.get("trace_events", [])),
    )


# ---------------------------------------------------------------------------
# 3. Safety Guidance Output Unpacker
# ---------------------------------------------------------------------------

def unpack_safety_guidance(ctx: Any, node_input: Any):
    """
    After safety_guidance_agent runs, its output dict is in node_input.
    Store it in state so package_safety_result can read it.
    """
    guidance_data = node_input
    if guidance_data is None:
        guidance_data = ctx.state.get("safety_guidance_response", {})

    return Event(
        output=guidance_data,
        state={"safety_guidance": guidance_data if isinstance(guidance_data, dict) else {}},
    )


# ---------------------------------------------------------------------------
# 4. Workflow Graph Setup
# ---------------------------------------------------------------------------

def build_workflow_graph(
    intake_agent: LlmAgent,
    safety_guidance_agent: LlmAgent,
    plan_generator_agent: LlmAgent,
    plan_reviewer_agent: LlmAgent,
) -> Workflow:
    """
    Builds the graph-based Workflow API.
    """
    edges = [
        # Start entrypoint → intake_router (reads from state)
        (START, intake_router),
        # Safety/Redirection branch
        (intake_router, {"needs_guidance": safety_guidance_agent, "safe": intake_agent}),
        (safety_guidance_agent, unpack_safety_guidance),
        (unpack_safety_guidance, package_safety_result),
        # Safe branch
        (intake_agent, plan_generator_agent),
        (plan_generator_agent, normalize_plan_node),
        # Normalization routing
        (normalize_plan_node, {"normalization_failed": package_normalization_failure, "normalized": plan_reviewer_agent}),
        # Reviewer routing
        (plan_reviewer_agent, final_validator_node),
        (final_validator_node, {"valid": package_valid_result, "invalid": package_invalid_result}),
    ]

    return Workflow(
        name="fitpath_workflow",
        output_schema=WorkflowResult,
        edges=edges,
    )


# ---------------------------------------------------------------------------
# 5. Entrypoint Runner
# ---------------------------------------------------------------------------

async def run_fitpath_workflow(
    workflow_input: WorkflowInput,
    mcp_toolset: McpToolset,
    intake_agent: LlmAgent,
    safety_guidance_agent: LlmAgent,
    plan_generator_agent: LlmAgent,
    plan_reviewer_agent: LlmAgent,
) -> WorkflowResult:
    """
    Runs the FitPath multi-agent workflow graph.
    Uses asyncio.Lock to serialize runs and protect the singleton stdio MCP connection.
    """
    request_id = f"fitpath-req-{int(time.time())}"
    start_time = time.perf_counter()

    # Pre-populate state with all profile fields before the workflow starts.
    # Also include ADK instruction template defaults so substitution never raises KeyError.
    initial_state = {
        **workflow_input.model_dump(),
        "focus_tags": [],        # flat key for plan_generator_agent {focus_tags} template
        "fitness_context": {},   # populated by intake_agent
        "draft_plan": None,
        "enriched_plan": None,
        "safety_guidance": {},
        "review_result": {},
        "trace_events": [],
    }

    async with _workflow_lock:
        workflow = build_workflow_graph(
            intake_agent=intake_agent,
            safety_guidance_agent=safety_guidance_agent,
            plan_generator_agent=plan_generator_agent,
            plan_reviewer_agent=plan_reviewer_agent,
        )

        app = App(name="fitpath_app", root_agent=workflow)
        runner = InMemoryRunner(app=app)

        session = await runner.session_service.create_session(
            app_name="fitpath_app", user_id="guest_user", session_id=request_id
        )

        # Pass state_delta to pre-populate session state AND new_message to trigger the workflow
        trigger_message = genai_types.Content(
            role="user",
            parts=[genai_types.Part.from_text(text="Generate fitness plan")],
        )

        final_result = None
        try:
            async for event in runner.run_async(
                user_id="guest_user",
                session_id=session.id,
                new_message=trigger_message,
                state_delta=initial_state,
            ):
                if event.output is not None:
                    # The workflow output is a WorkflowResult instance
                    final_result = event.output
        finally:
            await runner.close()

        if final_result is None:
            # Fallback if no output was generated
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return WorkflowResult(
                request_id=request_id,
                workflow_status="normalisation_failed",
                review_result=PlanReviewResult(
                    passed=False,
                    violations=["Workflow executed but produced no final output."],
                ),
                trace_events=[
                    emit_trace(
                        request_id=request_id,
                        workflow_stage="execution",
                        agent_name="workflow",
                        outcome="failed",
                        duration_ms=duration_ms,
                        error_type="NoOutputError",
                    )
                ],
            )

        # Reconstruct typed WorkflowResult if it returned dict
        if isinstance(final_result, dict):
            final_result = WorkflowResult(**final_result)

        return final_result
