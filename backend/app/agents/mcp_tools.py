"""
mcp_tools.py — Singleton McpToolset factory for the fitness_mcp server.

One toolset is created at FastAPI lifespan startup and reused for every
/api/plan/generate request.  The fitness_mcp subprocess starts once and stays
running for the application lifetime.

MVP LIMITATION (deliberate): A single stdio MCP session is shared across all
requests.  Concurrent plan generations are serialised via an asyncio.Lock in
workflow.py.  This is acceptable for single-user / local-development usage.
A connection pool should be added before multi-user production deployment.
"""
from __future__ import annotations

import sys
from pathlib import Path

from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

# Resolve the fitness_mcp package root relative to this file:
# backend/app/agents/mcp_tools.py  →  parents[3] = FitPath-ai/
PROJECT_ROOT = Path(__file__).resolve().parents[3]
FITNESS_MCP_CWD = PROJECT_ROOT / "fitness_mcp"

# These are the only three tools the Plan Generator Agent is permitted to call.
ALLOWED_MCP_TOOLS: list[str] = [
    "search_exercises_tool",
    "get_exercise_safety_notes_tool",
    "get_weekly_plan_template_tool",
]


def create_mcp_toolset() -> McpToolset:
    """
    Creates a McpToolset connected to the local fitness_mcp stdio server.

    Called once at FastAPI startup.  The returned toolset holds a persistent
    subprocess connection — do NOT create a new one per request.
    """
    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command=sys.executable,
                args=["-m", "fitness_mcp.server"],
                cwd=str(FITNESS_MCP_CWD),
            )
        ),
        tool_filter=ALLOWED_MCP_TOOLS,
    )
