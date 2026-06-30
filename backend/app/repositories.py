import datetime
import math
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, and_
from app.models import GuestSession, GuestProfile, FitnessPlan, WorkoutSession, WeeklyCheckin


class GuestRepository:
    async def create_session(self, db: AsyncSession, guest_id: str, token_hash: str) -> GuestSession:
        """Creates a new guest session in the database."""
        session = GuestSession(guest_id=guest_id, guest_token_hash=token_hash)
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session

    async def get_session_by_hash(self, db: AsyncSession, token_hash: str) -> GuestSession | None:
        """Retrieves a guest session by the SHA-256 hash of its token."""
        result = await db.execute(
            select(GuestSession).where(GuestSession.guest_token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def get_profile(self, db: AsyncSession, guest_id: str) -> GuestProfile | None:
        """Retrieves a guest profile by guest ID."""
        result = await db.execute(
            select(GuestProfile).where(GuestProfile.guest_id == guest_id)
        )
        return result.scalar_one_or_none()

    async def create_or_update_profile(self, db: AsyncSession, guest_id: str, profile_data: dict) -> GuestProfile:
        """Creates or updates a guest profile."""
        profile = await self.get_profile(db, guest_id)
        if profile:
            for key, value in profile_data.items():
                setattr(profile, key, value)
        else:
            profile = GuestProfile(guest_id=guest_id, **profile_data)
            db.add(profile)
        await db.commit()
        await db.refresh(profile)
        return profile

    async def update_reminder(self, db: AsyncSession, guest_id: str, reminder_enabled: bool, reminder_time: str | None) -> GuestProfile | None:
        """Updates reminder settings for a guest profile."""
        profile = await self.get_profile(db, guest_id)
        if not profile:
            return None
        profile.reminder_enabled = reminder_enabled
        profile.reminder_time = reminder_time
        await db.commit()
        await db.refresh(profile)
        return profile

    async def delete_guest_data(self, db: AsyncSession, guest_id: str) -> bool:
        """Deletes guest session and profile (explicit deletion first for safety)."""
        deleted = False

        # Explicitly delete profile first for safety across SQLite configurations
        profile = await self.get_profile(db, guest_id)
        if profile:
            await db.delete(profile)
            deleted = True

        # Delete session (cascade deletes plans, sessions, checkins)
        result = await db.execute(
            select(GuestSession).where(GuestSession.guest_id == guest_id)
        )
        session = result.scalar_one_or_none()
        if session:
            await db.delete(session)
            deleted = True

        if deleted:
            await db.commit()

        return deleted


class PlanRepository:
    """Handles FitnessPlan, WorkoutSession, and WeeklyCheckin persistence."""

    # ------------------------------------------------------------------
    # FitnessPlan
    # ------------------------------------------------------------------

    async def save_plan(
        self,
        db: AsyncSession,
        guest_id: str,
        execution_mode: str,
        duration_days: int,
        roadmap_json: dict,
        week_1_json: dict,
    ) -> FitnessPlan:
        """
        Deactivates any existing active plan for this guest, then persists a new one.
        Creates WorkoutSession rows for all non-rest days in Week 1.
        """
        old_plan = await self.get_active_plan(db, guest_id)
        if old_plan:
            old_plan.active = False

        plan = FitnessPlan(
            plan_id=str(uuid.uuid4()),
            guest_id=guest_id,
            execution_mode=execution_mode,
            duration_days=duration_days,
            start_date=datetime.datetime.utcnow(),
            active=True,
            roadmap_json=roadmap_json,
            week_1_json=week_1_json,
        )
        db.add(plan)
        await db.flush()  # Get plan_id before creating sessions

        # Create WorkoutSession rows for Week 1 active days
        schedule_order = 1
        for day in week_1_json.get("days", []):
            if not day.get("is_rest", False):
                total_mins = day.get("total_duration_mins", 30)
                ws = WorkoutSession(
                    session_id=str(uuid.uuid4()),
                    plan_id=plan.plan_id,
                    guest_id=guest_id,
                    week_number=week_1_json.get("week_number", 1),
                    day_name=day["day"],
                    schedule_order=schedule_order,
                    status="pending",
                    estimated_duration_mins=total_mins,
                )
                db.add(ws)
                schedule_order += 1

        await db.commit()
        await db.refresh(plan)
        return plan

    async def get_active_plan(self, db: AsyncSession, guest_id: str) -> FitnessPlan | None:
        """Returns the active FitnessPlan for the guest, or None. Cleans up duplicates."""
        result = await db.execute(
            select(FitnessPlan).where(
                and_(FitnessPlan.guest_id == guest_id, FitnessPlan.active == True)  # noqa: E712
            ).order_by(FitnessPlan.created_at.desc())
        )
        plans = list(result.scalars().all())
        if not plans:
            return None
            
        retained_plan = plans[0]
        if len(plans) > 1:
            import logging
            logging.getLogger(__name__).warning(f"Found {len(plans) - 1} duplicate active plans. Marking them inactive.")
            for duplicate in plans[1:]:
                duplicate.active = False
            await db.commit()
            
        return retained_plan

    async def delete_active_plan(self, db: AsyncSession, guest_id: str) -> bool:
        """Deletes the active plan (and cascades to workout sessions and checkins)."""
        plan = await self.get_active_plan(db, guest_id)
        if not plan:
            return False
        await db.delete(plan)
        await db.commit()
        return True

    # ------------------------------------------------------------------
    # WorkoutSession
    # ------------------------------------------------------------------

    async def get_workout_session(self, db: AsyncSession, session_id: str) -> WorkoutSession | None:
        result = await db.execute(
            select(WorkoutSession).where(WorkoutSession.session_id == session_id)
        )
        return result.scalar_one_or_none()

    async def complete_workout_session(
        self, db: AsyncSession, session_id: str, guest_id: str
    ) -> WorkoutSession | None:
        """
        Marks a workout session as completed. Verifies the session belongs to the guest.
        Returns None if session not found or ownership mismatch.
        """
        ws = await self.get_workout_session(db, session_id)
        if not ws or ws.guest_id != guest_id:
            return None
        ws.status = "completed"
        ws.completed_at = datetime.datetime.utcnow()
        await db.commit()
        await db.refresh(ws)
        return ws

    async def get_sessions_for_plan(self, db: AsyncSession, plan_id: str) -> list[WorkoutSession]:
        result = await db.execute(
            select(WorkoutSession)
            .where(WorkoutSession.plan_id == plan_id)
            .order_by(WorkoutSession.schedule_order)
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # WeeklyCheckin
    # ------------------------------------------------------------------

    async def save_checkin(
        self,
        db: AsyncSession,
        guest_id: str,
        plan_id: str,
        week_number: int,
        completed_sessions: int,
        energy_level: int,
        difficulty_rating: int,
        adjustment_json: dict | None,
    ) -> WeeklyCheckin:
        """Saves a weekly check-in. Never stores raw free-text."""
        checkin = WeeklyCheckin(
            checkin_id=str(uuid.uuid4()),
            guest_id=guest_id,
            plan_id=plan_id,
            week_number=week_number,
            completed_sessions=completed_sessions,
            energy_level=energy_level,
            difficulty_rating=difficulty_rating,
            adjustment_json=adjustment_json,
        )
        db.add(checkin)
        await db.commit()
        await db.refresh(checkin)
        return checkin

    async def get_latest_checkin(self, db: AsyncSession, plan_id: str) -> WeeklyCheckin | None:
        result = await db.execute(
            select(WeeklyCheckin)
            .where(WeeklyCheckin.plan_id == plan_id)
            .order_by(WeeklyCheckin.submitted_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # Dashboard calculations
    # ------------------------------------------------------------------

    async def get_dashboard_data(self, db: AsyncSession, guest_id: str) -> dict:
        """
        Computes all dashboard metrics from persisted data.
        Returns a dict ready to be serialised as DashboardResponse.
        """
        plan = await self.get_active_plan(db, guest_id)
        if not plan:
            return {"has_plan": False, "execution_mode": "mock"}

        sessions = await self.get_sessions_for_plan(db, plan.plan_id)
        total_sessions = len(sessions)
        completed_sessions = sum(1 for s in sessions if s.status == "completed")
        completion_pct = round(completed_sessions / total_sessions * 100, 1) if total_sessions else 0.0

        # Plan duration progress
        today = datetime.datetime.utcnow().date()
        start = plan.start_date.date() if isinstance(plan.start_date, datetime.datetime) else plan.start_date
        days_elapsed = max(1, (today - start).days + 1)
        plan_days_progress_pct = round(min(days_elapsed / plan.duration_days * 100, 100.0), 1)

        # Active streak — consecutive completed sessions from the start by schedule_order
        streak = 0
        for s in sorted(sessions, key=lambda x: x.schedule_order):
            if s.status == "completed":
                streak += 1
            else:
                break  # Streak breaks on first incomplete session

        # Weekly consistency score = completed this week / days_per_week
        # For MVP Week 1 only: completed / total planned workout days
        week_completed = sum(1 for s in sessions if s.status == "completed" and s.week_number == 1)
        week_total = sum(1 for s in sessions if s.week_number == 1)
        week_completion_pct = round(week_completed / week_total * 100, 1) if week_total else 0.0
        consistency_score = round(week_completed / week_total, 2) if week_total else 0.0

        # Next pending workout
        next_workout = None
        for s in sorted(sessions, key=lambda x: x.schedule_order):
            if s.status == "pending":
                next_workout = {
                    "session_id": s.session_id,
                    "day_name": s.day_name,
                    "week_number": s.week_number,
                    "estimated_duration_mins": s.estimated_duration_mins,
                }
                break

        # Latest checkin adjustment
        latest_checkin = await self.get_latest_checkin(db, plan.plan_id)
        latest_adjustment = latest_checkin.adjustment_json if latest_checkin else None

        # Profile reminder settings
        profile_result = await db.execute(
            select(GuestProfile).where(GuestProfile.guest_id == guest_id)
        )
        profile = profile_result.scalar_one_or_none()

        return {
            "has_plan": True,
            "execution_mode": plan.execution_mode,
            "plan_id": plan.plan_id,
            "duration_days": plan.duration_days,
            "start_date": plan.start_date.isoformat() if hasattr(plan.start_date, "isoformat") else str(plan.start_date),
            "days_elapsed": days_elapsed,
            "plan_days_progress_pct": plan_days_progress_pct,
            "week_total_sessions": week_total,
            "week_completed_sessions": week_completed,
            "week_completion_pct": week_completion_pct,
            "workout_streak": streak,
            "weekly_consistency_score": consistency_score,
            "next_workout": next_workout,
            "reminder_enabled": profile.reminder_enabled if profile else False,
            "reminder_time": profile.reminder_time if profile else None,
            "preferred_days": profile.preferred_days if profile else [],
            "latest_adjustment": latest_adjustment,
        }

