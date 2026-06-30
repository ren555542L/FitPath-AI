import hashlib
import logging
import secrets
import time
import uuid
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Header, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import init_db, get_db, check_db_ready
from app.repositories import GuestRepository, PlanRepository
from app.safety_rules import screen_notes
from app.schemas import (
    GuestStartResponse,
    ProfileCreateRequest,
    ProfileResponse,
    GuestMeResponse,
    ReminderUpdateRequest,
    DashboardResponse,
    WorkoutCompleteResponse,
)

# Phase 4/5 Imports
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.skill_toolset import SkillToolset
from google.adk.skills import load_skill_from_dir
from google.adk.agents import LlmAgent

from app.agents.schemas import (
    WorkflowInput,
    WorkflowResult,
    CheckInInput,
    ProgressAdjustment
)
from app.agents.mcp_tools import create_mcp_toolset, ALLOWED_MCP_TOOLS
from app.agents.intake_agent import build_intake_agent
from app.agents.safety_guidance_agent import build_safety_guidance_agent
from app.agents.plan_generator_agent import build_plan_generator_agent
from app.agents.plan_reviewer_agent import build_plan_reviewer_agent, SKILL_DIR
from app.agents.progress_coach_agent import build_progress_coach_agent
from app.agents.workflow import run_fitpath_workflow
from app.agents.mock_workflow import run_mock_workflow
from google.adk.apps import App
from google.adk.runners import InMemoryRunner


# Configure structured logging format
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fitpath")

# Custom JSON Formatter for structured logs
class StructuredJSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        # Add custom structured fields if present
        for field in ["request_id", "route", "duration_ms", "outcome", "error_type"]:
            if hasattr(record, field):
                log_data[field] = getattr(record, field)
        return json.dumps(log_data)

# Setup handler with formatter
handler = logging.StreamHandler()
handler.setFormatter(StructuredJSONFormatter())
logger.handlers = [handler]
logger.propagate = False


# Singleton containers for Phase 4 workflow resources
_mcp_toolset: McpToolset | None = None
_skill_toolset: SkillToolset | None = None
_intake_agent: LlmAgent | None = None
_safety_guidance_agent: LlmAgent | None = None
_plan_generator_agent: LlmAgent | None = None
_plan_reviewer_agent: LlmAgent | None = None
_progress_coach_agent: LlmAgent | None = None


# Lifespan context manager for startup and shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _mcp_toolset, _skill_toolset
    global _intake_agent, _safety_guidance_agent, _plan_generator_agent, _plan_reviewer_agent, _progress_coach_agent

    # 1. Initialize database tables
    await init_db()

    # 2. Skip MCP and LLM init in mock mode
    if settings.MOCK_AGENT_MODE:
        logger.info("MOCK_AGENT_MODE is enabled. Skipping ADK, MCP, and Gemini initialization.")
    else:
        # Build Singleton MCP Toolset (starts the stdio subprocess)
        logger.info("Initializing MCP Toolset subprocess...")
        _mcp_toolset = create_mcp_toolset()

        # Build Singleton Skill Toolset (loads SKILL.md)
        logger.info(f"Loading reviewer skill from: {SKILL_DIR}")
        skill = load_skill_from_dir(SKILL_DIR)
        _skill_toolset = SkillToolset(skills=[skill])

        # Build Singleton LlmAgents using configured model name
        logger.info(f"Building LLM Agents using model: {settings.MODEL_NAME}")
        _intake_agent = build_intake_agent()
        _safety_guidance_agent = build_safety_guidance_agent()
        _plan_generator_agent = build_plan_generator_agent(_mcp_toolset)
        _plan_reviewer_agent = build_plan_reviewer_agent(_skill_toolset)
        _progress_coach_agent = build_progress_coach_agent()

    yield  # Application is running and serving requests

    # 5. Clean up persistent toolset sessions on shutdown
    if not settings.MOCK_AGENT_MODE:
        logger.info("Shutting down toolsets...")
        if _mcp_toolset:
            await _mcp_toolset.close()
        if _skill_toolset:
            await _skill_toolset.close()
    logger.info("Lifespan cleanup complete.")


app = FastAPI(
    title="FitPath API",
    description="Safety-First AI Fitness Concierge Backend",
    version="0.1.0",
    lifespan=lifespan
)

# Enable CORS for local React development (Explicit Origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware for tracking Request IDs and durations
@app.middleware("http")
async def add_structured_logs_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    start_time = time.perf_counter()
    response = None
    outcome = "success"
    error_type = None
    route_path = request.url.path
    
    try:
        response = await call_next(request)
        if response.status_code >= 400:
            outcome = "error"
            error_type = f"HTTP_{response.status_code}"
    except Exception as e:
        outcome = "failure"
        error_type = type(e).__name__
        logger.error(
            "Unhandled exception occurred",
            extra={
                "request_id": request_id,
                "route": route_path,
                "outcome": outcome,
                "error_type": error_type
            },
            exc_info=True
        )
        response = JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Internal Server Error"}
        )
    finally:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info(
            f"Request processed: {request.method} {route_path}",
            extra={
                "request_id": request_id,
                "route": route_path,
                "duration_ms": duration_ms,
                "outcome": outcome,
                "error_type": error_type
            }
        )
        if response:
            response.headers["X-Request-ID"] = request_id
            
    return response

# Repositories initialization
guest_repo = GuestRepository()
plan_repo = PlanRepository()

# Security dependency to fetch the authenticated guest session
async def get_current_guest(
    x_guest_token: str | None = Header(None, alias="X-Guest-Token"),
    db: AsyncSession = Depends(get_db)
):
    if not x_guest_token:
        logger.warning("Authentication failed: Missing X-Guest-Token header")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing guest token"
        )
        
    computed_hash = hashlib.sha256(x_guest_token.encode("utf-8")).hexdigest()
    
    session = await guest_repo.get_session_by_hash(db, computed_hash)
    if not session:
        logger.warning("Authentication failed: Guest token not found in database")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid guest token"
        )
        
    if not secrets.compare_digest(session.guest_token_hash, computed_hash):
        logger.warning("Authentication failed: Secrets verification mismatch")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid guest token"
        )
        
    return session

# Dependencies to access startup singletons safely
def get_mcp_toolset() -> McpToolset:
    if _mcp_toolset is None:
        raise HTTPException(status_code=503, detail="MCP Toolset is not initialized.")
    return _mcp_toolset

def get_skill_toolset() -> SkillToolset:
    if _skill_toolset is None:
        raise HTTPException(status_code=503, detail="Skill Toolset is not initialized.")
    return _skill_toolset

def get_intake_agent() -> LlmAgent:
    if _intake_agent is None:
         raise HTTPException(status_code=503, detail="Intake Agent is not initialized.")
    return _intake_agent

def get_safety_guidance_agent() -> LlmAgent:
    if _safety_guidance_agent is None:
         raise HTTPException(status_code=503, detail="Safety Guidance Agent is not initialized.")
    return _safety_guidance_agent

def get_plan_generator_agent() -> LlmAgent:
    if _plan_generator_agent is None:
         raise HTTPException(status_code=503, detail="Plan Generator Agent is not initialized.")
    return _plan_generator_agent

def get_plan_reviewer_agent() -> LlmAgent:
    if _plan_reviewer_agent is None:
         raise HTTPException(status_code=503, detail="Plan Reviewer Agent is not initialized.")
    return _plan_reviewer_agent

def get_progress_coach_agent() -> LlmAgent:
    if _progress_coach_agent is None:
         raise HTTPException(status_code=503, detail="Progress Coach Agent is not initialized.")
    return _progress_coach_agent


@app.get("/health")
async def health_check():
    """
    Process liveness only.
    Returns 200 if the process is alive — does not call MCP or check dependencies.
    """
    return {
        "status": "healthy",
        "process": "alive",
    }


@app.get("/ready")
async def readiness_check():
    """
    Returns readiness status after validating database connection.
    If live mode, also validates MCP toolset discovery.
    """
    # 1. Validate Database readiness
    is_db_ready = await check_db_ready()
    if not is_db_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection or table access failed"
        )

    # 2. Validate MCP Toolset readiness (if live mode)
    if not settings.MOCK_AGENT_MODE:
        if _mcp_toolset is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="MCP Toolset is not initialized"
            )
        try:
            discovered_tools = await _mcp_toolset.get_tools()
            discovered_names = {t.name for t in discovered_tools}
            expected_names = set(ALLOWED_MCP_TOOLS)
            if not expected_names.issubset(discovered_names):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"MCP tools discovery incomplete. Found: {discovered_names}, Expected: {expected_names}"
                )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"MCP tools discovery check failed: {str(e)}"
            )
        return {"status": "ready", "execution_mode": "live"}

    return {"status": "ready", "execution_mode": "mock"}


@app.post("/api/guest/start", response_model=GuestStartResponse)
async def start_guest_session(db: AsyncSession = Depends(get_db)):
    """Generates a secure no-login guest session."""
    guest_id = str(uuid.uuid4())
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    
    session = await guest_repo.create_session(db, guest_id, token_hash)
    return {
        "guest_id": session.guest_id,
        "guest_token": raw_token,
        "created_at": session.created_at
    }


@app.post("/api/profile", response_model=ProfileResponse)
async def create_or_update_guest_profile(
    profile_data: ProfileCreateRequest,
    current_session = Depends(get_current_guest),
    db: AsyncSession = Depends(get_db)
):
    """Saves guest onboarding profile while screening notes in-memory."""
    safety = screen_notes(profile_data.notes)
    
    db_profile_data = {
        "goal": profile_data.goal,
        "fitness_level": profile_data.fitness_level,
        "duration_days": profile_data.duration_days,
        "available_time_mins": profile_data.available_time_mins,
        "days_per_week": profile_data.days_per_week,
        "equipment": profile_data.equipment,
        "preferred_days": profile_data.preferred_days,
        "reminder_time": profile_data.reminder_time,
        "reminder_enabled": profile_data.reminder_enabled,
        "safety_status": safety["safety_status"],
        "medical_review_required": safety["medical_review_required"],
        "safety_redirection_shown": safety["safety_status"] != "safe",
        "safety_message": safety["message"]
    }
    
    profile = await guest_repo.create_or_update_profile(
        db, current_session.guest_id, db_profile_data
    )
    return profile


@app.get("/api/guest/me", response_model=GuestMeResponse)
async def get_current_guest_info(
    current_session = Depends(get_current_guest),
    db: AsyncSession = Depends(get_db)
):
    """Retrieves authenticated guest session and profile details."""
    profile = await guest_repo.get_profile(db, current_session.guest_id)
    return {
        "guest_id": current_session.guest_id,
        "created_at": current_session.created_at,
        "profile": profile
    }


@app.delete("/api/guest")
async def delete_guest_session(
    current_session = Depends(get_current_guest),
    db: AsyncSession = Depends(get_db)
):
    """Deletes all authenticated session and profile data."""
    success = await guest_repo.delete_guest_data(db, current_session.guest_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Guest data not found"
        )
    return {
        "status": "success",
        "message": "Guest session and profile successfully deleted"
    }


# ---------------------------------------------------------------------------
# Phase 4/5 Multi-Agent Routes
# ---------------------------------------------------------------------------

@app.post("/api/plan/generate", response_model=WorkflowResult)
async def generate_plan(
    request: Request,
    current_session = Depends(get_current_guest),
    db: AsyncSession = Depends(get_db),
):
    """
    Triggers FitPath's workflow to generate and review a fitness plan.
    Branch: Mock (local deterministic) vs Live (ADK + MCP).
    Persists plan if successful.
    """
    profile = await guest_repo.get_profile(db, current_session.guest_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found. Please complete onboarding first."
        )

    workflow_input = WorkflowInput(
        goal=profile.goal,
        fitness_level=profile.fitness_level,
        duration_days=profile.duration_days,
        available_time_mins=profile.available_time_mins,
        days_per_week=profile.days_per_week,
        equipment=profile.equipment,
        preferred_days=profile.preferred_days,
        safety_status=profile.safety_status,
        safety_message=profile.safety_message
    )

    try:
        if settings.MOCK_AGENT_MODE:
            result = await run_mock_workflow(workflow_input=workflow_input)
        else:
            result = await run_fitpath_workflow(
                workflow_input=workflow_input,
                mcp_toolset=get_mcp_toolset(),
                intake_agent=get_intake_agent(),
                safety_guidance_agent=get_safety_guidance_agent(),
                plan_generator_agent=get_plan_generator_agent(),
                plan_reviewer_agent=get_plan_reviewer_agent()
            )

        # Persist plan if successfully generated
        if result.workflow_status == "completed" and result.fitness_plan:
            await plan_repo.save_plan(
                db=db,
                guest_id=current_session.guest_id,
                execution_mode=result.execution_mode,
                duration_days=profile.duration_days,
                roadmap_json=result.fitness_plan.roadmap.model_dump(),
                week_1_json=result.fitness_plan.week_1.model_dump(),
            )

        return result

    except Exception as e:
        logger.error(f"Workflow execution failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to execute plan generation workflow: {str(e)}"
        )


@app.get("/api/plan")
async def get_active_plan(
    current_session = Depends(get_current_guest),
    db: AsyncSession = Depends(get_db)
):
    """Returns the authenticated guest's active persisted plan."""
    plan = await plan_repo.get_active_plan(db, current_session.guest_id)
    if not plan:
        raise HTTPException(status_code=404, detail="No active plan found.")
    
    return {
        "plan_id": plan.plan_id,
        "execution_mode": plan.execution_mode,
        "duration_days": plan.duration_days,
        "start_date": plan.start_date.isoformat(),
        "roadmap": plan.roadmap_json,
        "week_1": plan.week_1_json
    }


@app.delete("/api/plan")
async def delete_active_plan(
    current_session = Depends(get_current_guest),
    db: AsyncSession = Depends(get_db)
):
    """Deletes only the authenticated user’s active plan and workout sessions."""
    success = await plan_repo.delete_active_plan(db, current_session.guest_id)
    if not success:
        raise HTTPException(status_code=404, detail="No active plan found.")
    return {"status": "success"}


@app.get("/api/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    current_session = Depends(get_current_guest),
    db: AsyncSession = Depends(get_db)
):
    """Returns real dashboard metrics derived from persisted data."""
    data = await plan_repo.get_dashboard_data(db, current_session.guest_id)
    return DashboardResponse(**data)


@app.post("/api/workouts/{session_id}/complete", response_model=WorkoutCompleteResponse)
async def complete_workout(
    session_id: str,
    current_session = Depends(get_current_guest),
    db: AsyncSession = Depends(get_db)
):
    """Marks a workout session as complete."""
    ws = await plan_repo.complete_workout_session(db, session_id, current_session.guest_id)
    if not ws:
        raise HTTPException(status_code=403, detail="Session not found or forbidden.")
    
    return {
        "status": "completed",
        "completed_at": ws.completed_at.isoformat()
    }


@app.patch("/api/reminders")
async def update_reminders(
    body: ReminderUpdateRequest,
    current_session = Depends(get_current_guest),
    db: AsyncSession = Depends(get_db)
):
    """Updates the guest's reminder preferences."""
    profile = await guest_repo.update_reminder(
        db, current_session.guest_id, body.reminder_enabled, body.reminder_time
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found.")
    
    return {
        "reminder_enabled": profile.reminder_enabled,
        "reminder_time": profile.reminder_time
    }


@app.post("/api/checkins", response_model=ProgressAdjustment)
async def submit_checkin(
    body: CheckInInput,
    current_session = Depends(get_current_guest),
    db: AsyncSession = Depends(get_db),
):
    """
    Evaluates check-in inputs, saves them, and returns progress coach adjustments.
    Mock Mode: returns a deterministic mock adjustment.
    Live Mode: calls the ADK coach agent.
    """
    plan = await plan_repo.get_active_plan(db, current_session.guest_id)
    if not plan:
        raise HTTPException(status_code=404, detail="No active plan found.")
    
    final_result = None

    if settings.MOCK_AGENT_MODE:
        # Return a deterministic mock adjustment
        final_result = ProgressAdjustment(
            recommendation="Keep up the great work! Your consistency is excellent.",
            reasoning="You have completed all planned sessions with great energy.",
            next_week_modifications=["Increase intensity slightly"]
        ).model_dump()
    else:
        # Live Mode - invoke the coach agent
        coach_agent = get_progress_coach_agent()
        from google.genai import types as genai_types
        app_runner = App(name="fitpath_coach", root_agent=coach_agent)
        runner = InMemoryRunner(app=app_runner)

        session = await runner.session_service.create_session(
            app_name="fitpath_coach",
            user_id=current_session.guest_id,
            session_id=f"checkin-{current_session.guest_id}-{uuid.uuid4().hex[:8]}",
        )

        try:
            async for event in runner.run_async(
                user_id=current_session.guest_id,
                session_id=session.id,
                new_message=genai_types.Content(
                    role="user",
                    parts=[genai_types.Part.from_text(text="Submit weekly check-in")],
                ),
                state_delta=body.model_dump(),
            ):
                if event.actions and event.actions.state_delta:
                    progress = event.actions.state_delta.get("progress_adjustment")
                    if progress:
                        final_result = progress
        finally:
            await runner.close()

    if final_result is None:
        raise HTTPException(status_code=500, detail="Progress Coach agent produced no output.")

    # Save to database
    await plan_repo.save_checkin(
        db=db,
        guest_id=current_session.guest_id,
        plan_id=plan.plan_id,
        week_number=1, # Fixed to 1 for MVP
        completed_sessions=body.completed_sessions,
        energy_level=body.energy_level,
        difficulty_rating=body.difficulty_rating,
        adjustment_json=final_result,
    )

    if isinstance(final_result, dict):
        return ProgressAdjustment(**final_result)
    return final_result
