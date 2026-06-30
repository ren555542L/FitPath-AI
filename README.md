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

*(Detailed run commands and environment instructions will be completed during implementation phases.)*
