from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import List, Optional
from datetime import datetime
import re

class GuestStartResponse(BaseModel):
    guest_id: str
    guest_token: str
    created_at: datetime

class ProfileCreateRequest(BaseModel):
    goal: str = Field(..., min_length=1)
    fitness_level: str = Field(..., min_length=1)
    duration_days: int
    available_time_mins: int
    days_per_week: int
    equipment: List[str]
    preferred_days: List[str]
    reminder_time: Optional[str] = None
    reminder_enabled: bool = False
    notes: Optional[str] = None  # Processed in-memory, never stored

    @field_validator("duration_days")
    @classmethod
    def validate_duration_days(cls, v: int) -> int:
        if v not in {30, 60, 90}:
            raise ValueError("duration_days must be exactly 30, 60, or 90")
        return v

    @field_validator("days_per_week")
    @classmethod
    def validate_days_per_week(cls, v: int) -> int:
        if not (2 <= v <= 6):
            raise ValueError("days_per_week must be between 2 and 6")
        return v

    @field_validator("available_time_mins")
    @classmethod
    def validate_available_time(cls, v: int) -> int:
        # Sensible bounds: 10 mins to 180 mins
        if not (10 <= v <= 180):
            raise ValueError("available_time_mins must be between 10 and 180 minutes")
        return v

    @field_validator("equipment")
    @classmethod
    def validate_equipment(cls, v: List[str]) -> List[str]:
        approved_equipment = {"No equipment", "Resistance bands", "Dumbbells", "Yoga mat"}
        for item in v:
            if item not in approved_equipment:
                raise ValueError(f"Invalid equipment: '{item}'. Must be one of {approved_equipment}")
        return v

    @field_validator("preferred_days")
    @classmethod
    def validate_preferred_days(cls, v: List[str]) -> List[str]:
        valid_days = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"}
        if not v:
            raise ValueError("preferred_days cannot be empty")
        
        # Check uniqueness
        if len(v) != len(set(v)):
            raise ValueError("preferred_days must contain unique values")

        for day in v:
            if day not in valid_days:
                raise ValueError(f"Invalid weekday: '{day}'. Must be a valid weekday name.")
        return v

    @field_validator("reminder_time")
    @classmethod
    def validate_reminder_time(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        # Match HH:MM format (24-hour)
        if not re.match(r"^(?:[01]\d|2[0-3]):[0-5]\d$", v):
            raise ValueError("reminder_time must be in HH:MM format (24-hour, e.g. 08:30 or 21:00)")
        return v

class ProfileResponse(BaseModel):
    guest_id: str
    goal: str
    fitness_level: str
    duration_days: int
    available_time_mins: int
    days_per_week: int
    equipment: List[str]
    preferred_days: List[str]
    reminder_time: Optional[str]
    reminder_enabled: bool
    safety_status: str
    medical_review_required: bool
    safety_redirection_shown: bool
    safety_message: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class GuestMeResponse(BaseModel):
    guest_id: str
    created_at: datetime
    profile: Optional[ProfileResponse] = None

    model_config = ConfigDict(from_attributes=True)
