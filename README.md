# FitPath - A Safety-First AI Fitness Concierge

FitPath is a modern, responsive web application that helps adults become fitter for life, not bulkier for show. It focuses on functional daily wellness (improving stamina, strength, mobility, posture, and balance) while keeping safety, privacy, and beginner-friendliness at its core.

---

## 1. Problem Statement & Solution

Traditional fitness apps often focus heavily on intense bodybuilding, aesthetic bulking, or extreme transformations. This leaves behind adults who want to improve their daily energy, balance, and health in a safe, sustainable way without gym jargon ("shredded", "hypertrophy") or heavy lifting.

**FitPath** solves this by providing:
- A calm, supportive, non-intimidating home wellness planner.
- Deterministic safety pre-screening to protect users from injury or medical risks.
- A private, secure no-login guest environment.
- Weekly check-in adaptation to scale workout intensity based on actual user energy and difficulty feedback.

---

## 2. Key Features

- **Multi-Step Onboarding**: Easy conversational setup of goals, equipment, schedule, and preferred reminder timings.
- **Secure Guest Mode**: Instant access with no sign-up or credentials, authenticated securely via local storage tokens.
- **Deterministic & AI Safety Screening**: Hard pre-checks filter medical risks, injury flags, or extreme goals before any AI generation.
- **Visual Wellness Dashboard**: View workout roadmaps, daily checklists, weekly streaks, and overall program completion.
- **Progress Coach Adaptation**: Submit weekly check-ins to intelligently dial down or scale up exercises.
- **In-App Reminders**: Dashboard notification cards matching preferred days and times.
- **Agent Activity Panel**: Visual timeline showing agent steps (Intake -> Safety -> Generator -> Reviewer) in real-time.

---

## 3. Technology Stack

- **Frontend**: React, Vite, TypeScript, Tailwind CSS, Recharts
- **Backend**: Python FastAPI, Uvicorn, SQLAlchemy (SQLite) / Motor (MongoDB Ready)
- **Agent Framework**: Google ADK (Agent Development Kit)
- **Model**: Google Gemini (`gemini-2.5-flash` recommended)
- **MCP Server**: Custom Stdio Model Context Protocol Server (`fitness_mcp`)
- **Testing**: pytest (for backend, APIs, and safety checks)

---

## 4. Google ADK Agent Architecture

FitPath leverages Google ADK to run an intelligent multi-agent pipeline with visible conditional routing:

```
[START Onboarding]
   │
   ▼
[Hard Pre-Checks (Python)] ──(Triggered Unsafe/Medical)──► [Safe Guidance / Refusal Screen]
   │
   │ (Passed Safe)
   ▼
[FitPathOrchestrator]
   ├── Intake Agent (Structures onboarding parameters)
   ├── Safety Agent (Additional safety analysis and explanations)
   ├── Plan Generator Agent (Queries fitness_mcp tools for exercises)
   └── Plan Reviewer Agent (Cross-references plan against constraints using fitness_plan_review skill)
   │
   ▼
[Save Plan to Database]
   │
   ▼
[Load Dashboard]
```

### Custom MCP Tools
- `search_exercises`: Query curated local exercise database.
- `get_exercise_safety_notes`: Fetch safety precautions for specific movements.
- `get_weekly_plan_template`: Load safe structural templates for specific days and availability.

---

## 5. Safety & Privacy Strategy

1. **No Numerical Weight**: Numerical weights are never collected or stored.
2. **Notes Discarding**: Free-text notes are analyzed immediately for medical risks and discarded. Raw medical text is never written to databases, logs, or analytics.
3. **Redirection Status**: We only store minimal derived flags (`medical_review_required`, `safety_redirection_shown`).
4. **Token Verification**: Database operations resolve identity directly from the `X-Guest-Token` header.

---

## 6. Setup and Running Locally

### 6.1 Prerequisites

Install the following before running FitPath locally:

- Python 3.11 or newer
- Node.js 18 or newer
- npm
- `uv` Python package manager
- A Google API key only for Live Agent Mode

Check your installations:

```bash
python --version
node --version
npm --version
uv --version
6.2 Clone the Repository
git clone <your-repository-url>
cd FitPath-ai
6.3 Install Backend Dependencies

From the project root, install the Python workspace dependencies:

uv sync --all-packages

This installs the FastAPI backend, Google ADK dependencies, the custom Fitness MCP server, and testing tools.

6.4 Configure Environment Variables

Create a local environment file inside the backend folder.

Windows PowerShell
cd backend
Copy-Item .env.example .env

Open backend/.env and use the following configuration:

MODEL_NAME=gemini-2.5-flash
GOOGLE_API_KEY=

DATABASE_PROVIDER=sqlite
DATABASE_URL=sqlite+aiosqlite:///./fitpath.db

PORT=8001
MOCK_AGENT_MODE=true
FRONTEND_ORIGIN=http://localhost:3000
Environment Variable Notes
Variable	Purpose
GOOGLE_API_KEY	Required only when running the real Gemini + ADK workflow
MOCK_AGENT_MODE=true	Uses the deterministic demo workflow without Gemini API calls
MOCK_AGENT_MODE=false	Enables the live Google ADK, Gemini, MCP, and SkillToolset workflow
DATABASE_URL	Creates and uses a local SQLite database
FRONTEND_ORIGIN	Must match the URL shown when the React frontend starts

Never commit backend/.env or a real Google API key to GitHub.

6.5 Run the Backend

From the backend folder:

uv run uvicorn app.main:app --reload --port 8001

The backend should start at:

http://127.0.0.1:8001

Verify that it is running:

http://127.0.0.1:8001/health

Expected response:

{
  "status": "healthy",
  "process": "alive"
}

The SQLite database file, fitpath.db, is created automatically on the first run.

6.6 Run the Frontend

Open a second terminal window.

cd FitPath-ai\frontend
npm install
npm run dev

Open the local URL displayed by Vite. It may look like:

http://localhost:3000

or:

http://localhost:5173

If Vite starts on a port other than 3000, update this value in backend/.env:

FRONTEND_ORIGIN=http://localhost:<vite-port>

Restart the backend after changing environment variables.

6.7 Running in Demo Mode

For the most reliable local demonstration, keep this setting enabled:

MOCK_AGENT_MODE=true

Demo Mode:

Does not call the Gemini API
Does not consume API quota
Uses the same onboarding, safety rules, plan normalization, validation, dashboard, and persistence flow
Is useful for testing, recordings, and offline-friendly demonstrations

The UI clearly identifies when Demo Mode is active.

6.8 Running the Live Agent Workflow

To use the full Google ADK and Gemini workflow, update backend/.env:

MOCK_AGENT_MODE=false
GOOGLE_API_KEY=your_google_api_key_here

Restart the backend:

uv run uvicorn app.main:app --reload --port 8001

Live Agent Mode enables:

Google ADK multi-agent workflow
Intake Agent
Safety Guidance Agent
Plan Generator Agent
Plan Reviewer Agent
Progress Coach Agent
Custom Fitness MCP tools
Fitness plan reviewer skill

A valid API key, available quota, and internet access are required.

6.9 Run Tests

Run backend tests from the backend directory:

uv run pytest tests/ -v

For a shorter test summary:

uv run pytest tests/ -q

Build the frontend to verify production readiness:

cd ..\frontend
npm run build
6.10 Reset Local Demo Data

To reset the local guest session, plans, workouts, and check-ins, stop the backend and delete the SQLite database:

cd FitPath-ai\backend
Remove-Item .\fitpath.db

Start the backend again:

uv run uvicorn app.main:app --reload --port 8001

Then clear browser site data for localhost before beginning a fresh demo session.

6.11 Common Issues
Issue	Fix
Frontend cannot connect to backend	Confirm the backend is running on port 8001 and FRONTEND_ORIGIN exactly matches the Vite URL
CORS error in browser	Update FRONTEND_ORIGIN in backend/.env, then restart FastAPI
Gemini quota or API error	Use MOCK_AGENT_MODE=true for the deterministic demo workflow
Multiple rows were found error	Reset the local SQLite database and browser site data before creating a new demo plan
MCP tool is unavailable	Run uv sync --all-packages again from the repository root
Port 8001 is unavailable	Stop the process using that port or choose a free port and update the frontend API configuration accordingly

Use `MOCK_AGENT_MODE=true` in the README’s default `.env`; it gives reviewers a smooth setup even without a Gemini key.
