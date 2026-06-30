import pytest
import pytest_asyncio
import os
import hashlib
import logging
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models import GuestSession, GuestProfile

# Use a specific test SQLite database file
TEST_DB_FILE = "./test_fitpath.db"
TEST_DATABASE_URL = f"sqlite+aiosqlite:///{TEST_DB_FILE}"

# Setup async test engine and sessionmaker (renamed to avoid pytest collection)
async_test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
async_test_session = sessionmaker(
    async_test_engine, class_=AsyncSession, expire_on_commit=False
)

# Override the database session dependency
async def override_get_db():
    async with async_test_session() as session:
        yield session

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="session", autouse=True)
def manage_test_db_lifecycle():
    """Ensures settings point to the test DB and cleans up any existing DB file."""
    settings.DATABASE_PROVIDER = "sqlite"
    settings.DATABASE_URL = TEST_DATABASE_URL
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except Exception:
            pass
    yield
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except Exception:
            pass

@pytest_asyncio.fixture(autouse=True)
async def setup_test_tables():
    """Creates a fresh set of tables in the test database for every test."""
    async with async_test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

def test_health_and_ready_endpoints(client):
    """11. /health and /ready return valid JSON and expected status codes."""
    # Health endpoint
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["process"] == "alive"

    # Ready endpoint (table access succeeds because of setup_test_tables)
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"

def test_start_session_returns_id_and_token(client):
    """1. New guest session returns an ID and token."""
    response = client.post("/api/guest/start")
    assert response.status_code == 200
    data = response.json()
    assert "guest_id" in data
    assert "guest_token" in data
    assert "created_at" in data
    # Ensure guest_token is a strong random key
    assert len(data["guest_token"]) >= 32

@pytest.mark.asyncio
async def test_database_stores_token_hash_never_raw_token(client):
    """2. Database stores token hash, never raw token."""
    response = client.post("/api/guest/start")
    assert response.status_code == 200
    data = response.json()
    raw_token = data["guest_token"]
    guest_id = data["guest_id"]

    async with async_test_session() as db:
        result = await db.execute(
            select(GuestSession).where(GuestSession.guest_id == guest_id)
        )
        session = result.scalar_one()
        expected_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        
        # Verify hash matches
        assert session.guest_token_hash == expected_hash
        # Verify raw token is not stored anywhere in the field
        assert raw_token not in session.guest_token_hash

def test_missing_or_invalid_token_returns_403(client):
    """3. Missing token returns 403. 4. Invalid token returns 403."""
    payload = {
        "goal": "Improve stamina",
        "fitness_level": "Beginner",
        "duration_days": 30,
        "available_time_mins": 20,
        "days_per_week": 3,
        "equipment": ["No equipment"],
        "preferred_days": ["Monday"]
    }

    # 3. Missing header
    res_missing = client.post("/api/profile", json=payload)
    assert res_missing.status_code == 403
    assert res_missing.json()["detail"] == "Missing guest token"

    # 4. Invalid header
    res_invalid = client.post(
        "/api/profile",
        headers={"X-Guest-Token": "badtoken_999"},
        json=payload
    )
    assert res_invalid.status_code == 403
    assert res_invalid.json()["detail"] == "Invalid guest token"

def test_valid_token_accesses_matching_profile_only(client):
    """5. Valid token accesses only the matching guest profile."""
    # Create Guest A
    res_a = client.post("/api/guest/start").json()
    token_a = res_a["guest_token"]
    id_a = res_a["guest_id"]

    # Create Guest B
    res_b = client.post("/api/guest/start").json()
    token_b = res_b["guest_token"]
    id_b = res_b["guest_id"]

    # Save profile for A
    payload_a = {
        "goal": "Improve stamina",
        "fitness_level": "Beginner",
        "duration_days": 30,
        "available_time_mins": 20,
        "days_per_week": 3,
        "equipment": ["No equipment"],
        "preferred_days": ["Monday"]
    }
    client.post("/api/profile", headers={"X-Guest-Token": token_a}, json=payload_a)

    # Access A's profile via /me
    me_a = client.get("/api/guest/me", headers={"X-Guest-Token": token_a}).json()
    assert me_a["guest_id"] == id_a
    assert me_a["profile"] is not None
    assert me_a["profile"]["goal"] == "Improve stamina"

    # Access B's profile via /me (should have no profile yet)
    me_b = client.get("/api/guest/me", headers={"X-Guest-Token": token_b}).json()
    assert me_b["guest_id"] == id_b
    assert me_b["profile"] is None

@pytest.mark.asyncio
async def test_raw_notes_are_not_stored(client):
    """6. Raw notes are not stored."""
    res = client.post("/api/guest/start").json()
    token = res["guest_token"]
    guest_id = res["guest_id"]

    payload = {
        "goal": "Improve stamina",
        "fitness_level": "Beginner",
        "duration_days": 30,
        "available_time_mins": 30,
        "days_per_week": 4,
        "equipment": ["No equipment"],
        "preferred_days": ["Monday", "Wednesday"],
        "notes": "SECRET_RAW_ONBOARDING_NOTES_TEXT"
    }
    client.post("/api/profile", headers={"X-Guest-Token": token}, json=payload)

    # Inspect the DB to verify no column contains the notes content
    async with async_test_session() as db:
        result = await db.execute(
            select(GuestProfile).where(GuestProfile.guest_id == guest_id)
        )
        profile = result.scalar_one()
        # Verify the notes string is not stored in any text fields
        for attr in ["goal", "fitness_level", "safety_status", "safety_message"]:
            val = getattr(profile, attr)
            assert "SECRET_RAW_ONBOARDING_NOTES_TEXT" not in str(val)

def test_raw_notes_not_present_in_application_logs(caplog, client):
    """7. Raw notes are not present in application logs."""
    res = client.post("/api/guest/start").json()
    token = res["guest_token"]

    payload = {
        "goal": "Improve stamina",
        "fitness_level": "Beginner",
        "duration_days": 30,
        "available_time_mins": 30,
        "days_per_week": 4,
        "equipment": ["No equipment"],
        "preferred_days": ["Monday", "Wednesday"],
        "notes": "CONFIDENTIAL_LOG_EXCLUSION_CHECK_NOTE"
    }

    with caplog.at_level(logging.INFO):
        client.post("/api/profile", headers={"X-Guest-Token": token}, json=payload)
        # Verify note is not in the logs
        assert "CONFIDENTIAL_LOG_EXCLUSION_CHECK_NOTE" not in caplog.text

def test_bulking_request_redirects_with_negation_checks(client):
    """8. Bulking request returns general_fitness_redirect (including negation scenarios)."""
    res = client.post("/api/guest/start").json()
    token = res["guest_token"]

    # Positive trigger for bulking
    payload = {
        "goal": "Improve stamina",
        "fitness_level": "Beginner",
        "duration_days": 30,
        "available_time_mins": 30,
        "days_per_week": 4,
        "equipment": ["No equipment"],
        "preferred_days": ["Monday", "Wednesday"],
        "notes": "I want to do bodybuilding and bulk up"
    }
    r = client.post("/api/profile", headers={"X-Guest-Token": token}, json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["safety_status"] == "general_fitness_redirect"
    assert "bodybuilding" in data["safety_message"]
    assert data["medical_review_required"] is False
    assert data["safety_redirection_shown"] is True

    # Negated check: "no bodybuilding"
    payload["notes"] = "I want no bodybuilding, just daily energy improvements."
    r_neg = client.post("/api/profile", headers={"X-Guest-Token": token}, json=payload)
    assert r_neg.status_code == 200
    data_neg = r_neg.json()
    assert data_neg["safety_status"] == "safe"
    assert data_neg["safety_message"] == ""
    assert data_neg["medical_review_required"] is False

def test_chest_pain_request_medical_review_with_negation_checks(client):
    """9. Chest-pain request returns medical_review_required (including negation scenarios)."""
    res = client.post("/api/guest/start").json()
    token = res["guest_token"]

    # Positive trigger for chest pain
    payload = {
        "goal": "Improve stamina",
        "fitness_level": "Beginner",
        "duration_days": 30,
        "available_time_mins": 30,
        "days_per_week": 4,
        "equipment": ["No equipment"],
        "preferred_days": ["Monday", "Wednesday"],
        "notes": "I suffer from chest pain."
    }
    r = client.post("/api/profile", headers={"X-Guest-Token": token}, json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["safety_status"] == "medical_review_required"
    assert "medical review" in data["safety_message"]
    assert data["medical_review_required"] is True

    # Negated check: "no chest pain"
    payload["notes"] = "I have no chest pain and no recent surgery"
    r_neg = client.post("/api/profile", headers={"X-Guest-Token": token}, json=payload)
    assert r_neg.status_code == 200
    data_neg = r_neg.json()
    assert data_neg["safety_status"] == "safe"
    assert data_neg["safety_message"] == ""
    assert data_neg["medical_review_required"] is False

def test_extreme_timeline_redirect(client):
    """Extreme timeline requests map to general_fitness_redirect with a sustainable-wellness message."""
    res = client.post("/api/guest/start").json()
    token = res["guest_token"]

    payload = {
        "goal": "Improve stamina",
        "fitness_level": "Beginner",
        "duration_days": 30,
        "available_time_mins": 30,
        "days_per_week": 4,
        "equipment": ["No equipment"],
        "preferred_days": ["Monday", "Wednesday"],
        "notes": "I want to lose 20 kg in 5 days"
    }
    r = client.post("/api/profile", headers={"X-Guest-Token": token}, json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["safety_status"] == "general_fitness_redirect"
    assert "gradual, and sustainable" in data["safety_message"]
    assert data["medical_review_required"] is False

@pytest.mark.asyncio
async def test_delete_guest_removes_matching_data_only(client):
    """10. Delete guest removes only authenticated guest data."""
    # Guest A
    res_a = client.post("/api/guest/start").json()
    token_a = res_a["guest_token"]
    id_a = res_a["guest_id"]

    # Guest B
    res_b = client.post("/api/guest/start").json()
    token_b = res_b["guest_token"]
    id_b = res_b["guest_id"]

    # Profile payloads
    payload = {
        "goal": "Improve stamina",
        "fitness_level": "Beginner",
        "duration_days": 30,
        "available_time_mins": 20,
        "days_per_week": 3,
        "equipment": ["No equipment"],
        "preferred_days": ["Monday"]
    }
    # Create profiles for both
    client.post("/api/profile", headers={"X-Guest-Token": token_a}, json=payload)
    client.post("/api/profile", headers={"X-Guest-Token": token_b}, json=payload)

    # Delete Guest A
    res_del = client.delete("/api/guest", headers={"X-Guest-Token": token_a})
    assert res_del.status_code == 200
    assert res_del.json()["status"] == "success"

    # Verify Guest A database records are gone
    async with async_test_session() as db:
        session_a = await db.execute(
            select(GuestSession).where(GuestSession.guest_id == id_a)
        )
        assert session_a.scalar_one_or_none() is None
        
        profile_a = await db.execute(
            select(GuestProfile).where(GuestProfile.guest_id == id_a)
        )
        assert profile_a.scalar_one_or_none() is None

        # Verify Guest B database records are untouched
        session_b = await db.execute(
            select(GuestSession).where(GuestSession.guest_id == id_b)
        )
        assert session_b.scalar_one_or_none() is not None
        
        profile_b = await db.execute(
            select(GuestProfile).where(GuestProfile.guest_id == id_b)
        )
        assert profile_b.scalar_one_or_none() is not None

def test_pydantic_strict_validations(client):
    """4. Add strict Pydantic validation for profile schema fields."""
    res = client.post("/api/guest/start").json()
    token = res["guest_token"]

    base_payload = {
        "goal": "Improve stamina",
        "fitness_level": "Beginner",
        "duration_days": 30,
        "available_time_mins": 30,
        "days_per_week": 4,
        "equipment": ["No equipment"],
        "preferred_days": ["Monday", "Wednesday"],
        "reminder_time": "08:30"
    }

    # 1. Invalid duration_days (must be 30, 60, or 90)
    bad_duration = base_payload.copy()
    bad_duration["duration_days"] = 45
    r = client.post("/api/profile", headers={"X-Guest-Token": token}, json=bad_duration)
    assert r.status_code == 422
    assert "duration_days" in r.text

    # 2. Invalid days_per_week (must be between 2 and 6)
    bad_days = base_payload.copy()
    bad_days["days_per_week"] = 7
    r = client.post("/api/profile", headers={"X-Guest-Token": token}, json=bad_days)
    assert r.status_code == 422
    assert "days_per_week" in r.text

    # 3. Invalid available_time_mins (must be between 10 and 180)
    bad_time = base_payload.copy()
    bad_time["available_time_mins"] = 5
    r = client.post("/api/profile", headers={"X-Guest-Token": token}, json=bad_time)
    assert r.status_code == 422
    assert "available_time_mins" in r.text

    # 4. Invalid equipment value
    bad_equip = base_payload.copy()
    bad_equip["equipment"] = ["Treadmill"]
    r = client.post("/api/profile", headers={"X-Guest-Token": token}, json=bad_equip)
    assert r.status_code == 422
    assert "equipment" in r.text

    # 5. Invalid preferred_days (not unique)
    bad_pref = base_payload.copy()
    bad_pref["preferred_days"] = ["Monday", "Monday"]
    r = client.post("/api/profile", headers={"X-Guest-Token": token}, json=bad_pref)
    assert r.status_code == 422
    assert "preferred_days" in r.text

    # 6. Invalid reminder_time format
    bad_reminder = base_payload.copy()
    bad_reminder["reminder_time"] = "8:30"  # Missing leading zero
    r = client.post("/api/profile", headers={"X-Guest-Token": token}, json=bad_reminder)
    assert r.status_code == 422
    assert "reminder_time" in r.text
