import logging
import time
import uuid
import json
import hashlib
import secrets
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Header, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import init_db, get_db, check_db_ready
from app.repositories import GuestRepository
from app.safety_rules import screen_notes
from app.schemas import (
    GuestStartResponse,
    ProfileCreateRequest,
    ProfileResponse,
    GuestMeResponse
)

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

# Lifespan context manager for startup and shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables on startup
    await init_db()
    yield

app = FastAPI(
    title="FitPath API",
    description="Safety-First AI Fitness Concierge Backend",
    version="0.1.0",
    lifespan=lifespan
)

# Enable CORS for local React development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict this in production settings
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
        # Log request processing with strict exclusion of sensitive values
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
        
    # Standardize token hashing for O(1) secure lookups
    computed_hash = hashlib.sha256(x_guest_token.encode("utf-8")).hexdigest()
    
    session = await guest_repo.get_session_by_hash(db, computed_hash)
    if not session:
        logger.warning("Authentication failed: Guest token not found in database")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid guest token"
        )
        
    # Constant-time comparison for timing attack prevention
    if not secrets.compare_digest(session.guest_token_hash, computed_hash):
        logger.warning("Authentication failed: Secrets verification mismatch")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid guest token"
        )
        
    return session

@app.get("/health")
async def health_check():
    """Returns process status."""
    return {
        "status": "healthy",
        "process": "alive",
        "mcp_connected": False
    }

@app.get("/ready")
async def readiness_check():
    """Returns readiness status after validating database connection and table access."""
    is_db_ready = await check_db_ready()
    if not is_db_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection or table access failed"
        )
    return {
        "status": "ready"
    }

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
    # Safety screening on notes in-memory (raw notes are never saved or logged)
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
