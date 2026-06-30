---
name: fitness_plan_review
description: |
  Rules and checks for reviewing fitness plans generated for FitPath.
  Validates functional wellness focus, equipment matching, and duration constraints.
---

# Fitness Plan Review Guidelines

When reviewing a generated fitness plan for a FitPath user, you must verify the plan complies with the following strict safety and suitability parameters:

## 1. Language and Tone
- The plan must use calm, supportive, functional, and beginner-friendly language.
- **NEVER** use bodybuilding, bulking, or extreme transformation terminology.
- Prohibited terms: *bulk, shred, hypertrophy, extreme transformation, gain muscle mass, max out, heavy lifting, pump*.
- Permitted/preferred terms: *stamina, flexibility, daily strength, posture, balance, mobility, recovery, consistency, wellness*.

## 2. Timing Constraints
- The total daily workout duration (including rest between exercises) must not exceed the available time specified in the user's profile:
  - If user selects "10-15 minutes", total exercises + rest must fit within 15 minutes.
  - If user selects "20-30 minutes", total must fit within 30 minutes, etc.

## 3. Equipment Alignment
- Only include exercises that utilize the equipment listed in the user's profile.
- If the user selects "No equipment", the plan must contain bodyweight or free-standing exercises only.
- If the user selects dumbbells or resistance bands, they may be included in strength sessions, but bodyweight options are still preferred as a baseline.

## 4. Rest and Recovery Inclusion
- Every weekly plan must contain at least 1-2 designated **Rest Days**.
- Rest days should not include scheduled exercises; they should note passive recovery or light walking/breathing guidance.

## 5. Safety Warnings
- If the onboarding flags any minor injury notes (e.g. "slight knee stiffness"), ensure the plan contains a specific, prominent safety warning and modification note (e.g., "Wall push-up modification: keep body vertical if shoulder feels stiff").
