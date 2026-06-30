"""plan_reviewer_agent.py — Plan Reviewer Agent definition."""
from __future__ import annotations

from pathlib import Path
from google.adk.agents import LlmAgent
from google.adk.skills import load_skill_from_dir
from google.adk.tools.skill_toolset import SkillToolset
from app.config import settings
from .schemas import PlanReviewResult

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SKILL_DIR = PROJECT_ROOT / "skills" / "fitness-plan-review"


def build_plan_reviewer_agent(skill_toolset: SkillToolset) -> LlmAgent:
    """
    Builds the Plan Reviewer Agent with a real SkillToolset.
    The agent must call load_skill to load the review rules.
    """
    return LlmAgent(
        name="plan_reviewer_agent",
        model=settings.MODEL_NAME,
        instruction=(
            "You are the FitPath Plan Reviewer Agent. Your job is to review the generated/enriched fitness plan "
            "and check it against the strict safety and suitability guidelines.\n\n"
            "Instructions:\n"
            "1. You MUST use the `load_skill` tool with skill_name='fitness-plan-review' to read your review rules. DO NOT GUESS THE RULES. You MUST call the tool before making a decision.\n"
            "2. Read the enriched plan from state: {enriched_plan}\n"
            "3. User's profile details: duration={duration_days}, time limit={available_time_mins}, equipment={equipment}.\n"
            "4. Perform all checks according to the skill rules. If everything is fully compliant, set passed=True, violations=[], and approved_plan to the input enriched_plan.\n"
            "5. If there are any compliance issues, set passed=False and list the specific violations in detail in the violations list.\n\n"
            "Populate and return the PlanReviewResult schema."
        ),
        output_schema=PlanReviewResult,
        output_key="review_result",
        tools=[skill_toolset],
    )
