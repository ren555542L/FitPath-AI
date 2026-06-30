"""intake_agent.py — Intake Agent definition."""
from __future__ import annotations

from google.adk.agents import LlmAgent
from app.config import settings
from .schemas import AgentFitnessContext


def build_intake_agent() -> LlmAgent:
    """
    Builds the Intake Agent.
    Derives focus tags and plan weeks from profile fields.
    """
    return LlmAgent(
        name="intake_agent",
        model=settings.MODEL_NAME,
        instruction=(
            "You are the FitPath Intake Agent. Your job is to analyze the user's fitness profile "
            "and produce an enriched fitness context.\n\n"
            "Profile Details:\n"
            "- Goal: {goal}\n"
            "- Fitness Level: {fitness_level}\n"
            "- Duration Days: {duration_days}\n"
            "- Available Time (mins): {available_time_mins}\n"
            "- Days Per Week: {days_per_week}\n"
            "- Equipment: {equipment}\n"
            "- Preferred Days: {preferred_days}\n\n"
            "Analyze their goal and fitness level to derive 2-4 functional fitness focus tags "
            "(e.g., stamina, mobility, daily strength, posture, balance, recovery, core, flexibility). "
            "Derive total_weeks = ceil(duration_days / 7).\n\n"
            "Populate and return the AgentFitnessContext schema."
        ),
        output_schema=AgentFitnessContext,
        output_key="fitness_context",
    )
