import sys
import pytest
import math
from pathlib import Path

from google.adk.agents import LlmAgent
from google.adk.skills import load_skill_from_dir
from google.adk.tools.skill_toolset import SkillToolset
from google.adk.models.llm_response import LlmResponse
from google.adk.apps import App
from google.adk.runners import InMemoryRunner
from google.genai import types

from app.config import settings
from app.agents.schemas import (
    WorkflowInput,
    WorkflowResult,
    CheckInInput,
    ProgressAdjustment,
    DraftGeneratedFitnessPlan,
    DraftWeeklyPlan,
    DraftWorkoutDay,
    DraftWorkoutExercise,
    FitnessRoadmap,
    GeneratedFitnessPlan,
    EnrichedWeeklyPlan,
    EnrichedWorkoutDay,
    EnrichedWorkoutExercise,
)
from app.agents.mcp_tools import create_mcp_toolset, ALLOWED_MCP_TOOLS
from app.agents.plan_normalizer import (
    normalize_plan,
    PlanNormalizationError,
    load_exercise_catalog,
)
from app.agents.final_validator import validate_plan
from app.agents.trace import emit_trace
from app.agents.intake_agent import build_intake_agent
from app.agents.safety_guidance_agent import build_safety_guidance_agent
from app.agents.plan_generator_agent import build_plan_generator_agent
from app.agents.plan_reviewer_agent import build_plan_reviewer_agent, SKILL_DIR
from app.agents.progress_coach_agent import build_progress_coach_agent
from app.agents.workflow import run_fitpath_workflow


# ---------------------------------------------------------------------------
# Helper function to mock an agent's LLM response
# ---------------------------------------------------------------------------
def mock_agent_response(agent: LlmAgent, response_text: str):
    async def before_model_cb(callback_context, llm_request):
        return LlmResponse(
            content=types.Content(
                role="model",
                parts=[types.Part.from_text(text=response_text)],
            )
        )
    agent.before_model_callback = before_model_cb


# ---------------------------------------------------------------------------
# Test 1: medical_review_required never calls Plan Generator
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_medical_review_required_never_calls_generator():
    mcp_toolset = create_mcp_toolset()
    intake = build_intake_agent()
    safety_guidance = build_safety_guidance_agent()
    plan_gen = build_plan_generator_agent(mcp_toolset)
    plan_rev = build_plan_reviewer_agent(SkillToolset(skills=[]))

    # Mock safety guidance response
    mock_agent_response(
        safety_guidance,
        '{"safety_status": "medical_review_required", "title": "Medical Review Required", "message": "Need a doctor note.", "can_proceed": false}',
    )

    # If plan_gen is called, it raises an error
    async def bad_cb(callback_context, llm_request):
        pytest.fail("Plan Generator should not be called for medical review required status!")

    plan_gen.before_model_callback = bad_cb

    workflow_input = WorkflowInput(
        goal="stamina",
        fitness_level="beginner",
        duration_days=30,
        available_time_mins=30,
        days_per_week=3,
        equipment=["No equipment"],
        preferred_days=["Monday", "Wednesday", "Friday"],
        safety_status="medical_review_required",
        safety_message="Recent surgery noted.",
    )

    try:
        result = await run_fitpath_workflow(
            workflow_input=workflow_input,
            mcp_toolset=mcp_toolset,
            intake_agent=intake,
            safety_guidance_agent=safety_guidance,
            plan_generator_agent=plan_gen,
            plan_reviewer_agent=plan_rev,
        )

        assert result.workflow_status == "safety_blocked"
        assert result.safety_guidance is not None
        assert result.safety_guidance.can_proceed is False
        assert result.fitness_plan is None
    finally:
        await mcp_toolset.close()


# ---------------------------------------------------------------------------
# Test 2: general_fitness_redirect never calls Plan Generator
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_general_fitness_redirect_never_calls_generator():
    mcp_toolset = create_mcp_toolset()
    intake = build_intake_agent()
    safety_guidance = build_safety_guidance_agent()
    plan_gen = build_plan_generator_agent(mcp_toolset)
    plan_rev = build_plan_reviewer_agent(SkillToolset(skills=[]))

    # Mock safety guidance response
    mock_agent_response(
        safety_guidance,
        '{"safety_status": "general_fitness_redirect", "title": "General Fitness Redirection", "message": "FitPath is for wellness.", "can_proceed": false}',
    )

    async def bad_cb(callback_context, llm_request):
        pytest.fail("Plan Generator should not be called for general fitness redirect status!")

    plan_gen.before_model_callback = bad_cb

    workflow_input = WorkflowInput(
        goal="hypertrophy",
        fitness_level="beginner",
        duration_days=30,
        available_time_mins=30,
        days_per_week=3,
        equipment=["No equipment"],
        preferred_days=["Monday", "Wednesday", "Friday"],
        safety_status="general_fitness_redirect",
        safety_message="User wants to bulk up.",
    )

    try:
        result = await run_fitpath_workflow(
            workflow_input=workflow_input,
            mcp_toolset=mcp_toolset,
            intake_agent=intake,
            safety_guidance_agent=safety_guidance,
            plan_generator_agent=plan_gen,
            plan_reviewer_agent=plan_rev,
        )

        assert result.workflow_status == "redirected"
        assert result.safety_guidance is not None
        assert result.safety_guidance.can_proceed is False
        assert result.fitness_plan is None
    finally:
        await mcp_toolset.close()


# ---------------------------------------------------------------------------
# Test 3: safe profile runs full pipeline
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_safe_profile_runs_full_pipeline():
    mcp_toolset = create_mcp_toolset()
    intake = build_intake_agent()
    safety_guidance = build_safety_guidance_agent()
    plan_gen = build_plan_generator_agent(mcp_toolset)
    plan_rev = build_plan_reviewer_agent(SkillToolset(skills=[]))

    # Mock intake agent response
    mock_agent_response(
        intake,
        '{"goal": "stamina", "fitness_level": "beginner", "duration_days": 30, "total_weeks": 5, "available_time_mins": 30, "days_per_week": 3, "equipment": ["No equipment"], "preferred_days": ["Monday", "Wednesday", "Friday"], "focus_tags": ["stamina", "mobility"]}',
    )

    # Mock plan generator response (Draft plan)
    mock_agent_response(
        plan_gen,
        '{"roadmap": {"duration_days": 30, "total_weeks": 5, "phase_summaries": ["Phase 1: Mobility"], "progression_notes": "Progress"}, "week_1": {"week_number": 1, "days": ['
        '{"day": "Monday", "is_rest": false, "focus": "stamina", "exercises": [{"name": "Neck Half Circles", "duration_mins": 10, "sets": 2, "reps": 10}]},'
        '{"day": "Tuesday", "is_rest": true, "focus": "recovery", "exercises": []},'
        '{"day": "Wednesday", "is_rest": false, "focus": "stamina", "exercises": [{"name": "Cat-Cow Stretch", "duration_mins": 10, "sets": 2, "reps": 10}]},'
        '{"day": "Thursday", "is_rest": true, "focus": "recovery", "exercises": []},'
        '{"day": "Friday", "is_rest": false, "focus": "stamina", "exercises": [{"name": "Seated Hip Circles", "duration_mins": 10, "sets": 2, "reps": 10}]},'
        '{"day": "Saturday", "is_rest": true, "focus": "recovery", "exercises": []},'
        '{"day": "Sunday", "is_rest": true, "focus": "recovery", "exercises": []}'
        ']}}',
    )

    # Mock reviewer response (PlanReviewResult approved)
    mock_agent_response(
        plan_rev,
        '{"passed": true, "violations": [], "approved_plan": {'
        '"roadmap": {"duration_days": 30, "total_weeks": 5, "phase_summaries": ["Phase 1: Mobility"], "progression_notes": "Progress"},'
        '"week_1": {"week_number": 1, "days": ['
        '{"day": "Monday", "is_rest": false, "focus": "stamina", "exercises": [{"name": "Neck Half Circles", "duration_mins": 10, "sets": 2, "reps": 10, "instructions": ["Roll"], "safety_note": "Slow", "required_equipment": []}], "total_duration_mins": 10},'
        '{"day": "Tuesday", "is_rest": true, "focus": "recovery", "exercises": [], "total_duration_mins": 0},'
        '{"day": "Wednesday", "is_rest": false, "focus": "stamina", "exercises": [{"name": "Cat-Cow Stretch", "duration_mins": 10, "sets": 2, "reps": 10, "instructions": ["Arch"], "safety_note": "Slow", "required_equipment": []}], "total_duration_mins": 10},'
        '{"day": "Thursday", "is_rest": true, "focus": "recovery", "exercises": [], "total_duration_mins": 0},'
        '{"day": "Friday", "is_rest": false, "focus": "stamina", "exercises": [{"name": "Seated Hip Circles", "duration_mins": 10, "sets": 2, "reps": 10, "instructions": ["Circle"], "safety_note": "Slow", "required_equipment": []}], "total_duration_mins": 10},'
        '{"day": "Saturday", "is_rest": true, "focus": "recovery", "exercises": [], "total_duration_mins": 0},'
        '{"day": "Sunday", "is_rest": true, "focus": "recovery", "exercises": [], "total_duration_mins": 0}'
        ']}}}',
    )

    workflow_input = WorkflowInput(
        goal="stamina",
        fitness_level="beginner",
        duration_days=30,
        available_time_mins=30,
        days_per_week=3,
        equipment=["No equipment"],
        preferred_days=["Monday", "Wednesday", "Friday"],
        safety_status="safe",
        safety_message="",
    )

    try:
        result = await run_fitpath_workflow(
            workflow_input=workflow_input,
            mcp_toolset=mcp_toolset,
            intake_agent=intake,
            safety_guidance_agent=safety_guidance,
            plan_generator_agent=plan_gen,
            plan_reviewer_agent=plan_rev,
        )

        assert result.workflow_status == "completed"
        assert result.fitness_plan is not None
        assert result.fitness_plan.roadmap.duration_days == 30
        assert result.fitness_plan.roadmap.total_weeks == 5
        assert result.review_result.passed is True
        assert len(result.trace_events) >= 2  # Normalisation and validation trace events
    finally:
        await mcp_toolset.close()


# ---------------------------------------------------------------------------
# Test 4: normalizer raises PlanNormalizationError for unknown exercise name
# ---------------------------------------------------------------------------
def test_normalizer_unknown_exercise():
    draft = DraftGeneratedFitnessPlan(
        roadmap=FitnessRoadmap(
            duration_days=30,
            total_weeks=5,
            phase_summaries=["Phase 1"],
            progression_notes="Keep going",
        ),
        week_1=DraftWeeklyPlan(
            week_number=1,
            days=[
                DraftWorkoutDay(
                    day="Monday",
                    is_rest=False,
                    focus="stamina",
                    exercises=[
                        DraftWorkoutExercise(name="Turbo Pushup Blast", duration_mins=10)
                    ],
                )
            ],
        ),
    )

    with pytest.raises(PlanNormalizationError) as exc_info:
        normalize_plan(draft, profile_equipment=["No equipment"])

    assert "Turbo Pushup Blast" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test 4.1: normalizer falls back to catalog duration if missing
# ---------------------------------------------------------------------------
def test_normalizer_falls_back_to_catalog_duration():
    draft = DraftGeneratedFitnessPlan(
        roadmap=FitnessRoadmap(
            duration_days=30,
            total_weeks=5,
            phase_summaries=["Phase 1"],
            progression_notes="Keep going",
        ),
        week_1=DraftWeeklyPlan(
            week_number=1,
            days=[
                DraftWorkoutDay(
                    day="Monday",
                    is_rest=False,
                    focus="stamina",
                    exercises=[
                        DraftWorkoutExercise(name="Bodyweight Squat", duration_mins=None)
                    ],
                )
            ],
        ),
    )

    enriched = normalize_plan(draft, profile_equipment=["No equipment"])
    ex = enriched.week_1.days[0].exercises[0]
    # Bodyweight Squat has estimated_duration_minutes=8 in catalog
    assert ex.duration_mins == 8
    assert enriched.week_1.days[0].total_duration_mins == 8


# ---------------------------------------------------------------------------
# Test 4.2: normalizer rejects negative duration
# ---------------------------------------------------------------------------
def test_normalizer_rejects_negative_duration():
    draft = DraftGeneratedFitnessPlan(
        roadmap=FitnessRoadmap(
            duration_days=30,
            total_weeks=5,
            phase_summaries=["Phase 1"],
            progression_notes="Keep going",
        ),
        week_1=DraftWeeklyPlan(
            week_number=1,
            days=[
                DraftWorkoutDay(
                    day="Monday",
                    is_rest=False,
                    focus="stamina",
                    exercises=[
                        DraftWorkoutExercise(name="Bodyweight Squat", duration_mins=0)
                    ],
                )
            ],
        ),
    )

    with pytest.raises(PlanNormalizationError) as exc_info:
        normalize_plan(draft, profile_equipment=["No equipment"])

    assert "invalid duration_mins: 0" in str(exc_info.value)



# ---------------------------------------------------------------------------
# Test 5: normalizer enriches instructions and safety_note from catalog
# ---------------------------------------------------------------------------
def test_normalizer_enriches_correctly():
    draft = DraftGeneratedFitnessPlan(
        roadmap=FitnessRoadmap(
            duration_days=30,
            total_weeks=5,
            phase_summaries=["Phase 1"],
            progression_notes="Keep going",
        ),
        week_1=DraftWeeklyPlan(
            week_number=1,
            days=[
                DraftWorkoutDay(
                    day="Monday",
                    is_rest=False,
                    focus="stamina",
                    exercises=[
                        DraftWorkoutExercise(name="Neck Half Circles", duration_mins=5)
                    ],
                )
            ],
        ),
    )

    enriched = normalize_plan(draft, profile_equipment=["No equipment"])
    ex = enriched.week_1.days[0].exercises[0]

    assert ex.name == "Neck Half Circles"
    assert len(ex.instructions) > 0
    assert "Gently drop your right ear" in ex.instructions[1]
    assert "Move slowly and without force" in ex.safety_note


# ---------------------------------------------------------------------------
# Test 6: Validator rejects equipment not in user profile
# ---------------------------------------------------------------------------
def test_normalizer_rejects_missing_equipment():
    # Dumbbell Bent-Over Row requires dumbbells
    draft = DraftGeneratedFitnessPlan(
        roadmap=FitnessRoadmap(
            duration_days=30,
            total_weeks=5,
            phase_summaries=["Phase 1"],
            progression_notes="Keep going",
        ),
        week_1=DraftWeeklyPlan(
            week_number=1,
            days=[
                DraftWorkoutDay(
                    day="Monday",
                    is_rest=False,
                    focus="stamina",
                    exercises=[
                        DraftWorkoutExercise(name="Dumbbell Bent-Over Row", duration_mins=10)
                    ],
                )
            ],
        ),
    )

    with pytest.raises(PlanNormalizationError) as exc_info:
        normalize_plan(draft, profile_equipment=["No equipment"])

    assert "requires ['dumbbells']" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test 7: Validator rejects daily duration exceeding available_time_mins
# ---------------------------------------------------------------------------
def test_validator_rejects_excess_duration():
    plan = GeneratedFitnessPlan(
        roadmap=FitnessRoadmap(
            duration_days=30,
            total_weeks=5,
            phase_summaries=["Phase 1"],
            progression_notes="Keep going",
        ),
        week_1=EnrichedWeeklyPlan(
            week_number=1,
            days=[
                EnrichedWorkoutDay(
                    day="Monday",
                    is_rest=False,
                    focus="stamina",
                    exercises=[
                        EnrichedWorkoutExercise(
                            name="Neck Half Circles",
                            duration_mins=35,
                            instructions=["Stretch"],
                            safety_note="Careful",
                            required_equipment=[],
                        )
                    ],
                    total_duration_mins=35,
                )
            ],
        ),
    )

    status, violations = validate_plan(
        plan, profile_duration_days=30, profile_available_time_mins=30
    )
    assert status == "invalid"
    assert any("exceeds the available_time_mins" in v for v in violations)


# ---------------------------------------------------------------------------
# Test 8: Validator rejects Week 1 if it has no rest days
# ---------------------------------------------------------------------------
def test_validator_rejects_missing_rest_day():
    plan = GeneratedFitnessPlan(
        roadmap=FitnessRoadmap(
            duration_days=30,
            total_weeks=5,
            phase_summaries=["Phase 1"],
            progression_notes="Keep going",
        ),
        week_1=EnrichedWeeklyPlan(
            week_number=1,
            days=[
                EnrichedWorkoutDay(
                    day="Monday",
                    is_rest=False,
                    focus="stamina",
                    exercises=[],
                    total_duration_mins=0,
                )
            ],
        ),
    )

    status, violations = validate_plan(
        plan, profile_duration_days=30, profile_available_time_mins=30
    )
    assert status == "invalid"
    assert any("contains no rest day" in v for v in violations)


# ---------------------------------------------------------------------------
# Test 9: Validator rejects roadmap if duration_days mismatch
# ---------------------------------------------------------------------------
def test_validator_rejects_duration_mismatch():
    plan = GeneratedFitnessPlan(
        roadmap=FitnessRoadmap(
            duration_days=60,
            total_weeks=9,
            phase_summaries=["Phase 1", "Phase 2"],
            progression_notes="Keep going",
        ),
        week_1=EnrichedWeeklyPlan(
            week_number=1,
            days=[
                EnrichedWorkoutDay(
                    day="Monday",
                    is_rest=True,
                    focus="recovery",
                    exercises=[],
                    total_duration_mins=0,
                )
            ],
        ),
    )

    status, violations = validate_plan(
        plan, profile_duration_days=30, profile_available_time_mins=30
    )
    assert status == "invalid"
    assert any("does not match profile duration_days" in v for v in violations)


# ---------------------------------------------------------------------------
# Test 10: Validator rejects roadmap if total_weeks mismatch
# ---------------------------------------------------------------------------
def test_validator_rejects_weeks_mismatch():
    with pytest.raises(ValueError):
        FitnessRoadmap(
            duration_days=30,
            total_weeks=4,  # should be ceil(30/7) = 5
            phase_summaries=["Phase 1"],
            progression_notes="Notes",
        )


# ---------------------------------------------------------------------------
# Test 11: load_skill_from_dir succeeds and loads skill named fitness-plan-review
# ---------------------------------------------------------------------------
def test_skill_loading_succeeds():
    skill = load_skill_from_dir(SKILL_DIR)
    assert skill.frontmatter.name == "fitness-plan-review"
    assert "Fitness Plan Review Guidelines" in skill.instructions


# ---------------------------------------------------------------------------
# Test 12: SkillToolset is attached to Plan Reviewer agent and contains list_skills
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_reviewer_skill_toolset_attached():
    skill = load_skill_from_dir(SKILL_DIR)
    toolset = SkillToolset(skills=[skill])
    agent = build_plan_reviewer_agent(toolset)

    assert len(agent.tools) == 1
    attached_toolset = agent.tools[0]
    assert isinstance(attached_toolset, SkillToolset)

    tools = await attached_toolset.get_tools()
    tool_names = {t.name for t in tools}
    assert "list_skills" in tool_names
    assert "load_skill" in tool_names


# ---------------------------------------------------------------------------
# Test 13: MCP toolset discovers all 3 tools without making a paid Gemini call
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_mcp_discovery_succeeds():
    mcp_toolset = create_mcp_toolset()
    try:
        tools = await mcp_toolset.get_tools()
        tool_names = {t.name for t in tools}
        for expected in ALLOWED_MCP_TOOLS:
            assert expected in tool_names
    finally:
        await mcp_toolset.close()


# ---------------------------------------------------------------------------
# Test 14: Progress Coach returns reduce_intensity on low energy/high difficulty
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_progress_coach_reduce_intensity():
    from google.genai import types as genai_types
    coach = build_progress_coach_agent()

    # Mock LLM response for progress coach
    mock_agent_response(
        coach,
        '{"recommendation": "reduce_intensity", "reasoning": "Energy level is low.", "next_week_modifications": ["Decrease session time"]}',
    )

    app = App(name="fitpath_coach", root_agent=coach)
    runner = InMemoryRunner(app=app)

    try:
        session = await runner.session_service.create_session(
            app_name="fitpath_coach", user_id="guest_user", session_id="test_coach_sess"
        )

        final_result = None
        async for event in runner.run_async(
            user_id="guest_user",
            session_id=session.id,
            new_message=genai_types.Content(
                role="user",
                parts=[genai_types.Part.from_text(text="Submit check-in")],
            ),
            state_delta={"completed_sessions": 2, "energy_level": 2, "difficulty_rating": 4, "week_number": 1},
        ):
            # The progress_coach_agent uses output_key="progress_adjustment"
            # so the parsed result is stored in event.actions.state_delta["progress_adjustment"]
            if event.actions and event.actions.state_delta:
                progress = event.actions.state_delta.get("progress_adjustment")
                if progress:
                    final_result = progress

        assert final_result is not None
        assert final_result["recommendation"] == "reduce_intensity"
    finally:
        await runner.close()


# ---------------------------------------------------------------------------
# Test 15: Trace events contain no raw notes, tokens, or auth headers
# ---------------------------------------------------------------------------
def test_trace_events_are_safe():
    trace = emit_trace(
        request_id="req-123",
        workflow_stage="generation",
        agent_name="plan_generator",
        outcome="success",
        duration_ms=450.5,
    )

    # Asserts that sensitive keys never exist in trace dictionary
    for forbidden in ["notes", "token", "hash", "db", "auth", "header"]:
        for key in trace.keys():
            assert forbidden not in key.lower()
        for val in trace.values():
            if isinstance(val, str):
                assert forbidden not in val.lower()

    assert trace["request_id"] == "req-123"
    assert trace["workflow_stage"] == "generation"
    assert trace["outcome"] == "success"
