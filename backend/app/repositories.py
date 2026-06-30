from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models import GuestSession, GuestProfile

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

    async def delete_guest_data(self, db: AsyncSession, guest_id: str) -> bool:
        """Deletes guest session and profile (explicit deletion first for safety)."""
        deleted = False
        
        # Explicitly delete profile first for safety across SQLite configurations
        profile = await self.get_profile(db, guest_id)
        if profile:
            await db.delete(profile)
            deleted = True

        # Delete session
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
