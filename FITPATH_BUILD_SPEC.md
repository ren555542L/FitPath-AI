Build a polished, portfolio-ready MVP called **FitPath - A Safety-First AI Fitness Concierge**.

## Product Purpose

FitPath is a responsive web application that helps adults become fitter for life, not bulkier for show.

It focuses on:

* Improving stamina and daily activity
* Building everyday strength
* Improving flexibility and mobility
* Better posture and balance
* Building a sustainable workout habit
* Gradual weight-management support
* Recovery, sleep, hydration, and consistency habits

FitPath must **not** be a bodybuilding, bulking, aggressive transformation, medical diagnosis, treatment, or prescription-diet application.

The product should feel calm, supportive, practical, and beginner-friendly. Avoid “gym bro” language such as “bulk,” “shredded,” “hypertrophy,” or “extreme transformation.”

## Mandatory No-Login Guest Mode

There must be **no sign-up, login, email, password, OTP, or paywall**.

The user journey must be:

1. User opens the landing page.
2. User clicks **Start Your Journey**.
3. Generate a unique `guestId` using UUID.
4. Save the `guestId` in browser `localStorage`.
5. Start onboarding immediately.
6. Store the user profile, workout plan, dashboard data, check-ins, and reminder settings under that `guestId`.

Add a Settings page with:

* Reset Guest Data
* Delete My Plan
* Enable/disable reminders
* A small Guest Mode privacy explanation

## Technology Stack

Use this stack:

* **Frontend:** React + Vite + TypeScript
* **Styling:** Tailwind CSS
* **Charts:** Recharts
* **Backend:** Python FastAPI
* **Validation:** Pydantic schemas
* **Agent Framework:** Google ADK
* **Model:** Gemini model configured through `.env`
* **MCP:** Custom Python Fitness MCP Server
* **Database:** MongoDB if configured, otherwise SQLite fallback for MVP
* **Exercise Data:** Curated `exercises.json`
* **Deployment:** Vercel for frontend and Render or Google Cloud Run for backend
* **Development Environment:** Antigravity IDE

Never hardcode API keys, secrets, MongoDB URLs, or passwords. Add `.env.example`.

## Landing Page

Create a polished landing page with:

* Product title: **FitPath**
* Tagline: **Get fitter for life - not bulkier for show.**
* Short description of safe, personalized home fitness
* Safety-first messaging
* A single strong CTA button: **Start Your Journey**
* Responsive design for desktop and mobile

## Onboarding Flow

Create a clean multi-step onboarding wizard. Collect:

* Primary goal:

  * Improve stamina
  * Build everyday strength
  * Improve mobility
  * Improve posture and balance
  * Lose weight gradually
  * Build a workout habit

* Fitness level:

  * Beginner
  * Returning after a break
  * Intermediate

* Available workout time:

  * 10-15 minutes
  * 20-30 minutes
  * 30-45 minutes
  * 45+ minutes

* Weekly availability:

  * 2 to 6 days per week

* Equipment:

  * No equipment
  * Resistance bands
  * Dumbbells
  * Yoga mat

* Plan duration:

  * 30 days
  * 60 days
  * 90 days

* Preferred workout days

* Preferred reminder time

* Optional notes with a visible disclaimer that FitPath is not a medical tool

Use cards, buttons, sliders, and friendly progress indicators instead of long boring forms.

## Multi-Agent ADK Workflow

Use Google ADK with visible conditional routing.

```text
START
  -> Intake Agent
  -> Safety and Goal Validator Agent
      -> Unsafe / unrealistic / medical-sensitive request
         -> Safe Guidance Response
      -> Normal wellness request
         -> Plan Generator Agent
         -> Fitness MCP Server tools
         -> Plan Reviewer Agent
         -> Save Plan
         -> Dashboard

Weekly Check-In
  -> Progress Coach Agent
  -> Adjust Next Week Plan
  -> Refresh Dashboard
```

Create clear modules for these agents:

### 1. Intake Agent

Converts onboarding data and optional user notes into a validated structured fitness profile.

### 2. Safety Agent

Checks for:

* Unrealistic timelines
* Extreme weight-loss requests
* Unsafe workout intensity
* Injury-risk mentions
* Medical diagnosis/treatment requests
* Requests outside general wellness scope

Example: if a user says they want to go from 150 kg to 60 kg in 30 days, do not generate an aggressive plan. Explain supportively that the goal is unrealistic and suggest gradual, sustainable wellness habits.

### 3. Plan Generator Agent

Creates a gradual home-fitness plan based on:

* Fitness level
* Goal
* Available time
* Weekly availability
* Equipment
* Plan duration

Plans should include walking, bodyweight exercises, mobility, balance, stretching, low-impact cardio, recovery, light resistance training where appropriate, and rest days.

### 4. Plan Reviewer Agent

Checks whether the generated plan:

* Matches the user’s fitness level
* Fits their available time
* Uses available equipment only
* Includes recovery and rest
* Avoids unsafe intensity
* Uses functional fitness language instead of bodybuilding language

### 5. Progress Coach Agent

Uses weekly check-in data to adapt the upcoming week.

It can:

* Maintain intensity
* Reduce workout difficulty
* Add recovery
* Increase difficulty gradually
* Recommend consistency before progression

## Custom Fitness MCP Server

Create a separate custom MCP server with typed tools:

```text
search_exercises(level, equipment, duration, focus_tags)
get_exercise_safety_notes(exercise_name)
get_weekly_plan_template(goal, days_per_week)
get_progress_summary(guest_id)
save_weekly_checkin(guest_id, completed_sessions, energy_level, difficulty_rating)
get_next_workout(guest_id)
```

The MCP server should use a curated exercise library.

Do not give the LLM unrestricted database access. The backend must provide the active `guestId`; the model must never choose or invent user IDs.

## Core Features

### Personalized Fitness Plan

Generate a 30, 60, or 90-day fitness plan with:

* Weekly schedule
* Workout day cards
* Exercise instructions
* Sets/reps or time duration
* Rest days
* Estimated duration
* Difficulty level
* General wellness notes

### Safety Guidance

Create a dedicated safety result screen for unsafe or unrealistic goals.

Use supportive wording. Do not shame users.

Include a disclaimer:

> FitPath provides general wellness information only and does not diagnose, treat, or replace professional medical advice.

### Dashboard

Build a polished dashboard with:

* Current plan and current week
* Today’s or next workout
* Workout completion percentage
* Active streak
* Weekly consistency score
* Upcoming sessions
* Progress chart
* Weekly check-in status
* Reminder settings
* Plan progress for 30/60/90-day journey

### Weekly Check-In

Ask users:

* How many sessions they completed
* Energy level
* Workout difficulty
* Optional feedback

After submission, run the Progress Coach Agent and clearly show what changed in the next week’s plan.

### Reminders

Users can choose workout days and preferred time.

Implement:

* Next Reminder card on dashboard
* In-app reminder system
* Browser notification only after explicit user permission
* Pause reminders
* Disable reminders

Do not claim notifications work after the browser closes unless that is actually supported by the implementation.

## API Endpoints

Create documented FastAPI endpoints:

```text
POST /api/guest/start
POST /api/profile
POST /api/plan/generate
GET /api/dashboard/{guest_id}
POST /api/checkins
PATCH /api/reminders
DELETE /api/guest/{guest_id}
```

Use Pydantic validation and meaningful error responses.

## Data Models

Create schemas/types for:

```text
GuestProfile
FitnessPlan
WorkoutSession
Exercise
WeeklyCheckin
ReminderPreference
SafetyResult
ProgressSummary
```

## Safety, Privacy, and Security

Implement these rules:

* Use `.env` and `.env.example`
* Never expose secrets in frontend code
* Validate frontend and backend input
* Do not store unnecessary health-sensitive information
* Do not log raw optional health notes
* Keep MCP tools narrow and typed
* Add basic rate-limit-ready middleware or endpoint protection
* Allow users to delete/reset guest data
* Require permission before browser notifications
* Do not diagnose conditions or prescribe diets/treatment

## UI Design Requirements

Use a modern, accessible, mobile-first layout.

Design style:

* Calm, friendly, health-focused
* Accessible contrast
* Clean cards and readable typography
* Subtle progress visuals
* Responsive on mobile
* Helpful loading, empty, and error states

Avoid dark aggressive gym visuals or bodybuilder imagery.

## Required Screens

* Landing Page
* Guest Onboarding Wizard
* Safety Guidance Screen
* Personalized Plan Screen
* Dashboard
* Weekly Check-In Screen
* Settings and Guest Data Reset Screen

## Testing

Add tests for:

* Normal beginner plan generation
* Unrealistic goal safety response
* Weekly check-in adaptation
* Reminder preference update
* Guest data deletion/reset

## Documentation

Create a strong `README.md` containing:

* Problem statement
* Solution overview
* Key features
* Technology stack
* Google ADK agent architecture
* Mermaid architecture diagram
* MCP tools
* Safety and privacy strategy
* Setup instructions
* `.env.example` explanation
* Local run commands
* Test commands
* Deployment instructions
* Judge demo flow

## Build Order

1. Scaffold the monorepo and shared schemas.
2. Build the FastAPI backend.
3. Implement ADK workflow and agents.
4. Build the custom Fitness MCP server.
5. Add curated exercise data.
6. Test safety and plan generation.
7. Build React onboarding and dashboard.
8. Connect frontend to APIs.
9. Add reminders and guest data reset.
10. Fix lint, type, and runtime errors.
11. Provide a final summary with files created, commands, and setup steps.

Use a mock/demo fallback only if required environment variables are unavailable, but keep the real ADK and MCP integration present in the codebase and documented.
