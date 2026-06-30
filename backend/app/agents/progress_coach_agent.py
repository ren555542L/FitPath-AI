"""progress_coach_agent.py — Progress Coach Agent definition."""
from __future__ import annotations

from google.adk.agents import LlmAgent
from app.config import settings
from .schemas import ProgressAdjustment


def build_progress_coach_agent() -> LlmAgent:
    """
    Builds the Progress Coach Agent.
    Evaluates check-in inputs and recommends adjustments.
    """
    return LlmAgent(
        name="progress_coach_agent",
        model=settings.MODEL_NAME,
        instruction=(
            "You are the FitPath Progress Coach Agent. Your job is to evaluate a user's check-in feedback "
            "and provide safety-conscious progress recommendations and modifications.\n\n"
            "Check-In Feedback:\n"
            "- Completed Sessions: {completed_sessions}\n"
            "- Energy Level (1-5): {energy_level}\n"
            "- Difficulty Rating (1-5): {difficulty_rating}\n"
            "- Week Number: {week_number}\n\n"
            "Guidelines:\n"
            "- Keep safety first. If energy level is low (e.g. 1 or 2) or difficulty is high (e.g. 4 or 5), "
            "recommend 'reduce_intensity' or 'add_recovery' to prevent injury and promote sustainable wellness.\n"
            "- Provide supportive, clear reasoning and specific next-week modifications.\n\n"
            "Populate and return the ProgressAdjustment schema."
        ),
        output_schema=ProgressAdjustment,
        output_key="progress_adjustment",
    )
