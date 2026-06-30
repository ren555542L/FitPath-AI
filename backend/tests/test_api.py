"""
test_api.py — Endpoint-level tests for FitPath FastAPI routes.
Uses FastAPI's TestClient to properly trigger the application lifespan.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.database import Base, get_db

# ---------------------------------------------------------------------------
# Test DB Setup
# ---------------------------------------------------------------------------
TEST_DB_FILE = "./test_api.db"
TEST_DATABASE_URL = f"sqlite+aiosqlite:///{TEST_DB_FILE}"

async_test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
async_test_session = sessionmaker(
    async_test_engine, class_=AsyncSession, expire_on_commit=False
)

async def override_get_db():
    async with async_test_session() as session:
        yield session

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(autouse=True, scope="session")
def prepare_test_db():
    import asyncio
    async def init_tables():
        async with async_test_engine.begin() as conn:
            from app.models import GuestSession, GuestProfile, FitnessPlan, WorkoutSession, WeeklyCheckin
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    asyncio.run(init_tables())
    yield
    import os
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except Exception:
            pass

# ---------------------------------------------------------------------------
# Fixtures & Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    """Sync HTTP client that manages the app lifespan."""
    with TestClient(app) as c:
        yield c


def _create_guest(client: TestClient) -> dict:
    r = client.post("/api/guest/start")
    assert r.status_code == 200
    return r.json()


def _create_profile(client: TestClient, token: str, **overrides) -> dict:
    payload = {
        "goal": "general wellness",
        "fitness_level": "beginner",
        "duration_days": 30,
        "available_time_mins": 30,
        "days_per_week": 3,
        "equipment": ["No equipment"],
        "preferred_days": ["Monday", "Wednesday", "Friday"],
        "notes": "",
        **overrides,
    }
    r = client.post(
        "/api/profile",
        json=payload,
        headers={"X-Guest-Token": token},
    )
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# 1. GET /health
# ---------------------------------------------------------------------------
def test_health_endpoint(client: TestClient):
    """
    /health must only report process liveness.
    It must NOT include mcp_connected or any dependency state.
    """
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "healthy"
    assert data["process"] == "alive"
    assert "mcp_connected" not in data


# ---------------------------------------------------------------------------
# 2. GET /ready
# ---------------------------------------------------------------------------
def test_ready_endpoint(client: TestClient):
    """/ready must verify DB access and MCP tool discovery."""
    r = client.get("/ready")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ready"


# ---------------------------------------------------------------------------
# 3. POST /api/plan/generate — missing token → 403
# ---------------------------------------------------------------------------
def test_generate_plan_missing_token(client: TestClient):
    r = client.post("/api/plan/generate")
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# 4. POST /api/plan/generate — invalid token → 403
# ---------------------------------------------------------------------------
def test_generate_plan_invalid_token(client: TestClient):
    r = client.post(
        "/api/plan/generate",
        headers={"X-Guest-Token": "definitely-not-a-valid-token"},
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# 5. POST /api/plan/generate — valid token but no profile → 404
# ---------------------------------------------------------------------------
def test_generate_plan_no_profile(client: TestClient):
    guest = _create_guest(client)
    token = guest["guest_token"]
    r = client.post(
        "/api/plan/generate",
        headers={"X-Guest-Token": token},
    )
    assert r.status_code == 404, r.text
    assert "profile" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 6. POST /api/plan/generate — blocked profile → safety guidance, no plan
# ---------------------------------------------------------------------------
def test_generate_plan_blocked_profile_returns_guidance(client: TestClient):
    """
    A profile with a blocked safety_status must return safety guidance
    and must NOT contain any MCP-tool or Plan-Generator trace events.
    Testing in MOCK_AGENT_MODE.
    """
    guest = _create_guest(client)
    token = guest["guest_token"]

    _create_profile(client, token, notes="I have chest pain when I exercise")

    r = client.post(
        "/api/plan/generate",
        headers={"X-Guest-Token": token},
    )
    assert r.status_code == 200, r.text
    data = r.json()

    assert data["workflow_status"] in ("safety_blocked", "redirected")
    assert data["fitness_plan"] is None
    assert data["safety_guidance"] is not None
    assert data["safety_guidance"]["can_proceed"] is False

    trace_agents = {ev.get("agent_name", "") for ev in (data.get("trace_events") or [])}
    forbidden_agents = {"plan_generator_agent", "normalize_plan_node",
                        "plan_reviewer_agent", "final_validator_node"}
    overlap = trace_agents & forbidden_agents
    assert not overlap, f"Blocked workflow trace shows forbidden agents: {overlap}"

    for ev in (data.get("trace_events") or []):
        assert "mcp" not in ev.get("agent_name", "").lower(), (
            f"MCP tool appeared in trace for blocked profile: {ev}"
        )


# ---------------------------------------------------------------------------
# 7. POST /api/checkins — missing token → 403
# ---------------------------------------------------------------------------
def test_checkin_missing_token(client: TestClient):
    r = client.post(
        "/api/checkins",
        json={
            "completed_sessions": 2,
            "energy_level": 3,
            "difficulty_rating": 3,
            "week_number": 1,
        },
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# 8. POST /api/checkins — invalid token → 403
# ---------------------------------------------------------------------------
def test_checkin_invalid_token(client: TestClient):
    r = client.post(
        "/api/checkins",
        json={
            "completed_sessions": 2,
            "energy_level": 3,
            "difficulty_rating": 3,
            "week_number": 1,
        },
        headers={"X-Guest-Token": "bogus-token"},
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Phase 5: New API Tests
# ---------------------------------------------------------------------------

def _setup_mock_plan(client: TestClient) -> dict:
    guest = _create_guest(client)
    token = guest["guest_token"]
    _create_profile(client, token)
    r = client.post(
        "/api/plan/generate",
        headers={"X-Guest-Token": token},
    )
    assert r.status_code == 200, r.text
    return {"token": token, "guest": guest, "plan": r.json()}


def test_generate_plan_persists_fitness_plan(client: TestClient):
    data = _setup_mock_plan(client)
    token = data["token"]
    
    # Verify active plan endpoint
    r = client.get("/api/plan", headers={"X-Guest-Token": token})
    assert r.status_code == 200
    plan_data = r.json()
    assert plan_data["execution_mode"] == "mock"
    assert "week_1" in plan_data


def test_dashboard_returns_real_stats_after_completion(client: TestClient):
    data = _setup_mock_plan(client)
    token = data["token"]

    r = client.get("/api/dashboard", headers={"X-Guest-Token": token})
    assert r.status_code == 200
    dash1 = r.json()
    assert dash1["has_plan"] is True
    assert dash1["week_completed_sessions"] == 0
    next_workout = dash1["next_workout"]
    assert next_workout is not None

    # Complete it
    r2 = client.post(
        f"/api/workouts/{next_workout['session_id']}/complete",
        headers={"X-Guest-Token": token}
    )
    assert r2.status_code == 200

    r3 = client.get("/api/dashboard", headers={"X-Guest-Token": token})
    dash2 = r3.json()
    assert dash2["week_completed_sessions"] == 1
    assert dash2["workout_streak"] == 1


def test_complete_workout_rejects_wrong_guest(client: TestClient):
    data1 = _setup_mock_plan(client)
    data2 = _setup_mock_plan(client)

    r = client.get("/api/dashboard", headers={"X-Guest-Token": data1["token"]})
    next_workout = r.json()["next_workout"]
    session_id = next_workout["session_id"]

    # Try to complete it with guest 2's token
    r2 = client.post(
        f"/api/workouts/{session_id}/complete",
        headers={"X-Guest-Token": data2["token"]}
    )
    assert r2.status_code == 403


def test_checkin_saves_and_returns_adjustment(client: TestClient):
    data = _setup_mock_plan(client)
    token = data["token"]

    r = client.post(
        "/api/checkins",
        json={
            "completed_sessions": 3,
            "energy_level": 4,
            "difficulty_rating": 3,
            "week_number": 1,
        },
        headers={"X-Guest-Token": token},
    )
    assert r.status_code == 200
    adj = r.json()
    assert "recommendation" in adj

    # Verify dashboard returns it
    r2 = client.get("/api/dashboard", headers={"X-Guest-Token": token})
    dash = r2.json()
    assert dash["latest_adjustment"] is not None


def test_reminder_update_persists(client: TestClient):
    data = _setup_mock_plan(client)
    token = data["token"]

    r = client.patch(
        "/api/reminders",
        json={"reminder_enabled": True, "reminder_time": "14:30"},
        headers={"X-Guest-Token": token}
    )
    assert r.status_code == 200

    r2 = client.get("/api/dashboard", headers={"X-Guest-Token": token})
    dash = r2.json()
    assert dash["reminder_enabled"] is True
    assert dash["reminder_time"] == "14:30"


def test_delete_plan_removes_workout_sessions(client: TestClient):
    data = _setup_mock_plan(client)
    token = data["token"]

    r = client.delete("/api/plan", headers={"X-Guest-Token": token})
    assert r.status_code == 200

    r2 = client.get("/api/dashboard", headers={"X-Guest-Token": token})
    dash = r2.json()
    assert dash["has_plan"] is False


@pytest.mark.parametrize("endpoint,method", [
    ("/api/plan", "GET"),
    ("/api/plan", "DELETE"),
    ("/api/dashboard", "GET"),
    ("/api/workouts/fake-session/complete", "POST"),
    ("/api/checkins", "POST"),
    ("/api/reminders", "PATCH"),
    ("/api/guest/me", "GET"),
])
def test_invalid_token_returns_403_on_all_new_endpoints(client: TestClient, endpoint: str, method: str):
    headers = {"X-Guest-Token": "invalid-token"}
    if method == "GET":
        r = client.get(endpoint, headers=headers)
    elif method == "POST":
        r = client.post(endpoint, headers=headers, json={})
    elif method == "PATCH":
        r = client.patch(endpoint, headers=headers, json={})
    else:
        r = client.delete(endpoint, headers=headers)
    
    # Either 403 or 422 if body is invalid, but auth happens before body validation in Depends()
    assert r.status_code == 403

