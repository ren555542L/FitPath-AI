# FitPath Fitness MCP Server

A read-only MCP (Model Context Protocol) server that provides curated fitness tools to the FitPath AI agent pipeline.

## Overview

The server exposes three narrowly scoped, read-only tools over a standard stdio transport:

| Tool | Purpose |
|------|---------|
| `search_exercises_tool` | Filter exercises by level, equipment, duration, or focus tags |
| `get_exercise_safety_notes_tool` | Look up detailed instructions and safety guidance for a named exercise |
| `get_weekly_plan_template_tool` | Generate a deterministic 7-day workout schedule for a goal and day count |

**Design constraints:**
- Read-only. No database writes, no user/guest IDs, no health data stored.
- No external API calls. All data is served from the local `exercises.json` library.
- Protocol messages write strictly to **stdout**.
- All log output writes strictly to **stderr** (see [Why stderr for logs?](#why-stderr-for-logs)).

---

## Setup

From the **monorepo root** (`FitPath-ai/`), all dependencies are managed via the root `uv` workspace. Install the fitness-mcp dev dependencies:

```bash
cd fitness_mcp
uv sync --group dev
```

---

## Run the Server (stdio)

```bash
cd fitness_mcp
uv run python -m fitness_mcp.server
```

The server will log startup to stderr and then wait for JSON-RPC messages over stdin. Ctrl+C to exit.

---

## Run Tests

```bash
cd fitness_mcp
uv run pytest tests/ -v
```

**Expected output:**
```
12 passed in ~10s
```

Tests use the official MCP Python client (`stdio_client` + `ClientSession`) and exercise every tool through the real MCP protocol lifecycle.

---

## Tool Reference

### `search_exercises_tool`

Search the 25-exercise library with optional filters.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `level` | `str \| None` | Difficulty filter (`"beginner"`) |
| `available_equipment` | `list[str] \| None` | Equipment the user has. Pass `[]` for bodyweight-only. |
| `max_duration_minutes` | `int \| None` | Exclude exercises longer than this |
| `focus_tags` | `list[str] \| None` | Match exercises containing at least one of these tags |

**Equipment matching rule:** An exercise is returned only when its `required_equipment` is a **subset** of `available_equipment`. Passing `[]` will return only bodyweight exercises.

**Result is capped at 10 matches.** Response includes `match_count`, `total_before_cap`, and `filters_applied`.

**Example call (MCP Python client):**
```python
result = await session.call_tool(
    "search_exercises_tool",
    {"level": "beginner", "available_equipment": ["yoga_mat"], "max_duration_minutes": 10},
)
```

**Example response:**
```json
{
  "filters_applied": ["level=beginner", "available_equipment=['yoga_mat']", "max_duration_minutes=10"],
  "match_count": 10,
  "total_before_cap": 18,
  "exercises": [
    {
      "name": "Cat-Cow Stretch",
      "category": "mobility",
      "difficulty": "beginner",
      "required_equipment": [],
      "optional_equipment": ["yoga_mat"],
      "focus_tags": ["spine", "lower back", "core", "flexibility"],
      "estimated_duration_minutes": 5
    }
  ]
}
```

---

### `get_exercise_safety_notes_tool`

Return detailed instructions and safety notes for a named exercise.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `exercise_name` | `str` | Exact or partial exercise name (case-insensitive) |

Returns a structured `found: false` result for unknown names — never raises.

**Example call:**
```python
result = await session.call_tool(
    "get_exercise_safety_notes_tool",
    {"exercise_name": "Glute Bridge"},
)
```

**Example response (found):**
```json
{
  "found": true,
  "exercise_name": "Glute Bridge",
  "category": "functional strength",
  "difficulty": "beginner",
  "estimated_duration_minutes": 8,
  "required_equipment": [],
  "optional_equipment": ["yoga_mat"],
  "focus_tags": ["glutes", "lower back", "core", "hips", "posture"],
  "instructions": [
    "Lie on your back with knees bent and feet flat on the floor, hip-width apart.",
    "..."
  ],
  "safety_notes": "Do not hyperextend your lower back at the top of the movement. ..."
}
```

**Example response (not found):**
```json
{
  "found": false,
  "exercise_name": "Dragon Squat Ultra Extreme",
  "message": "No exercise named 'Dragon Squat Ultra Extreme' was found in the FitPath library. Use search_exercises to browse available exercises.",
  "safety_notes": null,
  "instructions": null
}
```

---

### `get_weekly_plan_template_tool`

Generate a deterministic 7-day workout schedule.

**Parameters:**

| Parameter | Type | Constraints |
|-----------|------|-------------|
| `goal` | `str` | One of the supported goals (see below) |
| `days_per_week` | `int` | **2–6 inclusive**. 1 and 7 are rejected with `valid: false` |

**Supported goals:**
- `"improve stamina"`
- `"build everyday strength"`
- `"improve mobility"`
- `"improve posture and balance"`
- `"lose weight gradually"`
- `"build a workout habit"`

Returns `valid: false` with an `error` message for out-of-range days or unrecognised goals. Includes a safety disclaimer on every response.

**Example call:**
```python
result = await session.call_tool(
    "get_weekly_plan_template_tool",
    {"goal": "build a workout habit", "days_per_week": 4},
)
```

**Example response:**
```json
{
  "valid": true,
  "goal": "build a workout habit",
  "days_per_week": 4,
  "rest_days": 3,
  "wellness_note": "Focus on showing up regularly. A 10-minute session completed beats a 60-minute session skipped.",
  "disclaimer": "FitPath provides general wellness guidance only and does not diagnose, treat, or replace professional medical advice. Consult your doctor before starting any new exercise programme.",
  "schedule": [
    {"day": "Monday", "type": "active", "focus_category": "mobility", "suggested_duration_minutes": 20},
    {"day": "Tuesday", "type": "active", "focus_category": "functional strength", "suggested_duration_minutes": 20},
    {"day": "Wednesday", "type": "rest", "focus_category": null, "suggested_duration_minutes": 0},
    {"day": "Thursday", "type": "active", "focus_category": "recovery", "suggested_duration_minutes": 20},
    {"day": "Friday", "type": "active", "focus_category": "low-impact cardio", "suggested_duration_minutes": 20},
    {"day": "Saturday", "type": "rest", "focus_category": null, "suggested_duration_minutes": 0},
    {"day": "Sunday", "type": "rest", "focus_category": null, "suggested_duration_minutes": 0}
  ]
}
```

---

## Why stderr for Logs?

MCP communicates over **stdio**: the client reads JSON-RPC messages from the server's **stdout** and writes messages to the server's **stdin**.

If any log output (even a single character) is written to stdout, it corrupts the JSON-RPC framing and the connection fails. All logging in this server is configured with `stream=sys.stderr` to guarantee that only protocol-conformant bytes ever reach stdout.

---

## Exercise Library

25 curated beginner-friendly exercises across 5 categories:

| Category | Count |
|----------|-------|
| Mobility | 5 |
| Functional Strength | 5 |
| Low-Impact Cardio | 5 |
| Balance and Posture | 5 |
| Recovery | 5 |

Equipment schema uses two fields:
- `required_equipment`: Must be available. Empty `[]` means bodyweight only.
- `optional_equipment`: Enhances comfort but is not required.

Valid equipment values: `"dumbbells"`, `"resistance_bands"`, `"yoga_mat"`.
