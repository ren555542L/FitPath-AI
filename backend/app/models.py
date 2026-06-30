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
