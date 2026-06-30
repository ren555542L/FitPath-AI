from sqlalchemy import Column, String, Integer, Boolean, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
import datetime

class GuestSession(Base):
    __tablename__ = "guest_sessions"

    guest_id = Column(String, primary_key=True, index=True)
    guest_token_hash = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # One-to-one relationship to profile
    profile = relationship(
        "GuestProfile",
        back_populates="session",
        uselist=False,
        cascade="all, delete-orphan"
    )
    # One-to-many to plans
    plans = relationship(
        "FitnessPlan",
        back_populates="session",
        cascade="all, delete-orphan"
    )

class GuestProfile(Base):
    __tablename__ = "guest_profiles"

    guest_id = Column(
        String,
        ForeignKey("guest_sessions.guest_id", ondelete="CASCADE"),
        primary_key=True,
        index=True
    )
    goal = Column(String, nullable=False)
    fitness_level = Column(String, nullable=False)
    duration_days = Column(Integer, nullable=False)
    available_time_mins = Column(Integer, nullable=False)
    days_per_week = Column(Integer, nullable=False)

    # Store list of equipment and preferred days as JSON
    equipment = Column(JSON, nullable=False)
    preferred_days = Column(JSON, nullable=False)

    reminder_time = Column(String, nullable=True)
    reminder_enabled = Column(Boolean, default=False, nullable=False)

    safety_status = Column(String, nullable=False)
    medical_review_required = Column(Boolean, default=False, nullable=False)
    safety_redirection_shown = Column(Boolean, default=False, nullable=False)
    safety_message = Column(String, nullable=True, default="")

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False
    )

    session = relationship("GuestSession", back_populates="profile")


# ---------------------------------------------------------------------------
# Phase 5: Plan persistence models
# ---------------------------------------------------------------------------

class FitnessPlan(Base):
    """Persisted generated fitness plan (mock or live)."""
    __tablename__ = "fitness_plans"

    plan_id = Column(String, primary_key=True, index=True)
    guest_id = Column(
        String,
        ForeignKey("guest_sessions.guest_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    execution_mode = Column(String, nullable=False)   # "mock" | "live"
    duration_days = Column(Integer, nullable=False)
    start_date = Column(DateTime, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    roadmap_json = Column(JSON, nullable=False)
    week_1_json = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    session = relationship("GuestSession", back_populates="plans")
    workout_sessions = relationship(
        "WorkoutSession",
        back_populates="plan",
        cascade="all, delete-orphan",
    )
    checkins = relationship(
        "WeeklyCheckin",
        back_populates="plan",
        cascade="all, delete-orphan",
    )


class WorkoutSession(Base):
    """One scheduled workout day within a plan (Week 1 only for MVP)."""
    __tablename__ = "workout_sessions"

    session_id = Column(String, primary_key=True, index=True)
    plan_id = Column(
        String,
        ForeignKey("fitness_plans.plan_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    guest_id = Column(
        String,
        ForeignKey("guest_sessions.guest_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    week_number = Column(Integer, nullable=False, default=1)
    day_name = Column(String, nullable=False)        # "Monday", etc.
    schedule_order = Column(Integer, nullable=False) # 1-based position in week
    status = Column(String, default="pending", nullable=False)  # "pending" | "completed"
    completed_at = Column(DateTime, nullable=True)
    estimated_duration_mins = Column(Integer, nullable=False)

    plan = relationship("FitnessPlan", back_populates="workout_sessions")


class WeeklyCheckin(Base):
    """Weekly check-in record. Raw feedback text is never stored."""
    __tablename__ = "weekly_checkins"

    checkin_id = Column(String, primary_key=True, index=True)
    guest_id = Column(
        String,
        ForeignKey("guest_sessions.guest_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_id = Column(
        String,
        ForeignKey("fitness_plans.plan_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    week_number = Column(Integer, nullable=False)
    completed_sessions = Column(Integer, nullable=False)
    energy_level = Column(Integer, nullable=False)     # 1–5
    difficulty_rating = Column(Integer, nullable=False) # 1–5
    adjustment_json = Column(JSON, nullable=True)       # ProgressAdjustment dict (from mock or live)
    submitted_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    plan = relationship("FitnessPlan", back_populates="checkins")

