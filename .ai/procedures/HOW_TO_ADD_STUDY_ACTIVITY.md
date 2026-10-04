# How to add a study activity

## Architecture path

```text
DailyStudyPlanner  →  StudySession  →  Tk adapter  →  activity UI
```

See [ADR-007](../decisions/ADR-007-daily-study-planner.md), [ADR-008](../decisions/ADR-008-study-session.md).

## Rules

1. Declare whether the activity is **required** or **optional** (and when unavailable).
2. Extend planner outputs only if Home/session need new workload semantics.
3. StudySession owns logical statuses (`pending` / `active` / `completed` / `skipped` / `unavailable`).
4. Tkinter/ScreenGuard remains lock enforcement — do not put security in the domain session model.
5. Do **not** insert the activity as a random `if` chain only in `main.py`.
6. Optional activities (like Reading) must not permanently block completion after required work when offline/AI fails.
7. Add focused tests for session/planner behavior without GUI automation.
8. Update `.ai/current_state.md` / roadmap if the activity set permanently changes.

## Current real activities

- **Vocabulary** — required when planned vocab count > 0
- **Reading** — optional when enabled
