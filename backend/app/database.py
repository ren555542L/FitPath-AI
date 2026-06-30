from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.event import listens_for
from sqlalchemy.pool import Pool
from app.config import settings

Base = declarative_base()

# Adapt standard SQLite URL to async aiosqlite if required
db_url = settings.DATABASE_URL
if db_url.startswith("sqlite://"):
    db_url = db_url.replace("sqlite://", "sqlite+aiosqlite://", 1)

# Async SQLAlchemy Engine
engine = None
async_session = None

if settings.DATABASE_PROVIDER == "sqlite":
    engine = create_async_engine(db_url, echo=False)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

# Enable SQLite foreign key enforcement
@listens_for(Pool, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if settings.DATABASE_PROVIDER == "sqlite":
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

async def init_db():
    """Initializes the database structure (creates tables for SQLite)."""
    if settings.DATABASE_PROVIDER == "sqlite" and engine is not None:
        async with engine.begin() as conn:
            # Import models to ensure they are registered with Base
            from app.models import GuestSession, GuestProfile
            await conn.run_sync(Base.metadata.create_all)

async def get_db():
    """Dependency injector for database session."""
    if settings.DATABASE_PROVIDER == "sqlite" and async_session is not None:
        async with async_session() as session:
            yield session
    else:
        # Placeholder for MongoDB client session generator
        yield None

async def check_db_ready() -> bool:
    """Verifies that the database connection is healthy and tables are accessible."""
    if settings.DATABASE_PROVIDER == "sqlite" and async_session is not None:
        try:
            async with async_session() as session:
                from sqlalchemy import text
                # Execute a simple query on our tables to ensure access works
                await session.execute(text("SELECT 1 FROM guest_sessions LIMIT 1"))
                return True
        except Exception:
            return False
    return False
