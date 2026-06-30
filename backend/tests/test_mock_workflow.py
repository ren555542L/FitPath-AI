import sys
import pytest
from app.agents.schemas import WorkflowInput
from app.agents.mock_workflow import run_mock_workflow


@pytest.fixture
def base_workflow_input():
    return WorkflowInput(
        goal="Lose weight",
        fitness_level="beginner",
        duration_days=30,
        available_time_mins=30,
        days_per_week=3,
        equipment=["No equipment"],
        preferred_days=["Monday", "Wednesday", "Friday"],
        safety_status="safe",
        safety_message=""
    )


@pytest.mark.asyncio
async def test_mock_workflow_safe_profile_returns_completed(base_workflow_input):
    result = await run_mock_workflow(base_workflow_input)
    assert result.workflow_status == "completed"
    assert result.execution_mode == "mock"
    assert result.fitness_plan is not None
    assert result.fitness_plan.roadmap.duration_days == 30
    assert len(result.fitness_plan.week_1.days) == 7


@pytest.mark.asyncio
async def test_mock_workflow_medical_blocked(base_workflow_input):
    input_data = base_workflow_input.model_copy(update={
        "safety_status": "medical_review_required",
        "safety_message": "Consult a doctor"
    })
    result = await run_mock_workflow(input_data)
    assert result.workflow_status == "safety_blocked"
    assert result.execution_mode == "mock"
    assert result.safety_guidance is not None
    assert result.safety_guidance.safety_status == "medical_review_required"


@pytest.mark.asyncio
async def test_mock_workflow_general_redirect(base_workflow_input):
    input_data = base_workflow_input.model_copy(update={
        "safety_status": "general_fitness_redirect",
        "safety_message": "Too extreme"
    })
    result = await run_mock_workflow(input_data)
    assert result.workflow_status == "redirected"
    assert result.execution_mode == "mock"
    assert result.safety_guidance is not None
    assert result.safety_guidance.safety_status == "general_fitness_redirect"


@pytest.mark.asyncio
async def test_mock_trace_events_all_labeled_mock_mode(base_workflow_input):
    result = await run_mock_workflow(base_workflow_input)
    assert len(result.trace_events) > 0
    for event in result.trace_events:
        assert event.get("mock_mode") is True


def test_mock_workflow_no_adk_imports():
    """Verify mock_workflow.py does not import google.adk or google.genai"""
    import app.agents.mock_workflow
    
    with open(app.agents.mock_workflow.__file__, "r", encoding="utf-8") as f:
        content = f.read()
        
    assert "import google.adk" not in content
    assert "from google.adk" not in content
    assert "import google.genai" not in content
    assert "from google.genai" not in content
