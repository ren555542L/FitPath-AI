"""
trace.py — safe trace event logging and collection.
Never includes raw notes, guest tokens, hashes, or database handles.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("fitpath.agents.trace")


def emit_trace(
    request_id: str,
    workflow_stage: str,
    agent_name: str,
    outcome: str,
    duration_ms: float,
    tool_name: str | None = None,
    error_type: str | None = None,
    mock_mode: bool = False,
) -> dict:
    """
    Creates and logs a safe trace event.
    Set mock_mode=True to clearly label events as coming from the deterministic mock workflow.
    """
    event: dict = {
        "request_id": request_id,
        "workflow_stage": workflow_stage,
        "agent_name": agent_name,
        "outcome": outcome,
        "duration_ms": duration_ms,
        "mock_mode": mock_mode,
    }
    if tool_name:
        event["tool_name"] = tool_name
    if error_type:
        event["error_type"] = error_type

    logger.info(
        f"Workflow trace: {workflow_stage} | Agent: {agent_name} | Outcome: {outcome} | Mock: {mock_mode}",
        extra=event,
    )
    return event
