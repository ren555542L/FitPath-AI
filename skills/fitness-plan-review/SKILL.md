---
name: fitness-plan-review
description: Reviews FitPath plans for functional-fitness focus, safety, equipment compatibility, session duration, and recovery.
---

# Fitness Plan Review Guidelines

When reviewing a generated fitness plan for a FitPath user, apply every rule below
before returning your `PlanReviewResult`. Set `passed: false` and populate
`violations` with a clear, specific message for each rule that fails.

## 1. Language and Tone

- The plan must use calm, supportive, functional, and beginner-friendly language.
- **NEVER** use bodybuilding, bulking, or extreme transformation terminology.
- Prohibited terms: *bulk, shred, hypertrophy, extreme transformation, gain muscle mass, max out, heavy lifting, pump, ripped, cut, shredded*.
- Permitted/preferred terms: *stamina, flexibility, daily strength, posture, balance, mobility, recovery, consistency, wellness, functional fitness*.
- Violation example: `"Plan uses prohibited term 'hypertrophy' in week 1 description."`

## 2. Timing Constraints

- Every active day's total workout duration must not exceed the `available_time_mins` in the user's profile.
- Sum all `duration_mins` values within a single workout day and compare to the limit.
- Violation example: `"Day 1 total duration is 45 mins but user limit is 30 mins."`

## 3. Equipment Alignment

- Only include exercises whose `required_equipment` is a subset of the user's available equipment.
- If the user has "No equipment", the plan must contain only exercises with an empty `required_equipment` list.
- Optional equipment (e.g. yoga mat) must never cause a rejection.
- Violation example: `"Exercise 'Dumbbell Curl' requires dumbbells but user has no equipment."`

## 4. Rest and Recovery

- Every weekly plan must contain at least one day where `is_rest: true`.
- Rest days must not contain exercises.
- Violation example: `"Week 1 has no rest day."`

## 5. Roadmap Duration Accuracy

- The roadmap's `duration_days` field must exactly match the user's requested `duration_days` from their profile.
- The roadmap's `total_weeks` must equal `ceil(duration_days / 7)`.
- Violation example: `"Roadmap duration_days is 30 but user requested 60 days."`

## 6. Safety and Medical Claims

- Plans must never promise medical outcomes (e.g., "cures back pain", "fixes your injury").
- Plans must never claim to diagnose or treat medical conditions.
- Violation example: `"Plan claims to 'cure knee pain', which is a medical claim."`

## 7. Exercise Name Integrity

- Every exercise name must be a real exercise drawn from the fitness catalog.
- Do not invent exercise names or combine exercise names into portmanteau entries.
- Violation example: `"Exercise 'Turbo Squat Blast' is not a recognized catalog exercise."`
