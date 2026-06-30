"""safety_guidance_agent.py — Safety Guidance Agent definition."""
from __future__ import annotations

from google.adk.agents import LlmAgent
from app.config import settings
from .schemas import SafetyGuidanceResponse


def build_safety_guidance_agent() -> LlmAgent:
    """
    Builds the Safety Guidance Agent.
    Explains the safety redirection supportively.
    """
    return LlmAgent(
        name="safety_guidance_agent",
        model=settings.MODEL_NAME,
        instruction=(
            "You are the FitPath Safety Guidance Agent. Your job is to explain the safety screening "
            "decision to the user in a supportive, empathetic, and clear manner.\n\n"
            "Safety Verdict:\n"
            "- Status: {safety_status}\n"
            "- Message: {safety_message}\n\n"
            "Provide a warm, structured response explaining the redirection. "
            "Set can_proceed to False.\n\n"
            "Populate and return the SafetyGuidanceResponse schema."
        ),
        output_schema=SafetyGuidanceResponse,
        output_key="safety_guidance",
    )
