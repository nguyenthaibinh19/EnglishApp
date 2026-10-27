# AI agent workflow (StudyGuard)

How ChatGPT (Leader), Cursor (Developer), and Codex (selective QA) collaborate on this repository.

## Roles

| Role | Responsibility |
|------|----------------|
| **ChatGPT — Leader** | Architecture decisions, phase scope, acceptance criteria, review of diffs, go/no-go for commit/release |
| **Cursor — Developer** | Implement against Leader briefs; run tests; update `.ai/` when architecture/invariants change; produce reviewable diffs |
| **Codex — Independent QA** | Selective GUI / frozen / production verification when Leader assigns it — not automatic for every foundation phase |

## Default loop

1. Leader issues a written brief (baseline SHA, scope, restrictions, deliverables).
2. Developer reads `.ai/current_state.md`, `.ai/invariants.md`, relevant ADRs, then code/tests.
3. Developer implements the **smallest safe change** within scope.
4. Developer runs required tests (`pytest`, smoke when relevant) and reports exact counts.
5. Developer delivers summary + **complete `git diff HEAD`** (including new files / `.ai/` docs).
6. Leader reviews the diff before commit/push unless the brief already authorized them.
7. Codex runs only when Leader requests independent QA (e.g. Windows GUI, frozen exe).

## Documentation requirements

- Update durable memory (`.ai/`) when decisions, invariants, roadmap, or architecture change.
- Prefer ADRs for “why”; procedures for repeatable how-tos; `current_state.md` for position snapshots.
- Do **not** claim production activation, VPS deploy, or Windows client behavior without evidence named in the brief.
- Chat history is working context only — repository + `.ai/` + tests are source of truth.

## GitHub / release discipline

- Do not commit or push unless the Leader brief explicitly allows it.
- Do not rebuild/release or deploy VPS unless asked.
- Prefer attaching a full review diff (tracked + new files) before merge authorization.

## Selective Codex QA

Use Codex when the risk is operator-visible or environment-specific, for example:

- Tkinter selection / ScreenGuard / fullscreen lock behavior
- Frozen Windows `.exe` Listening / Vocabulary Manager flows
- Live authenticated API smoke against production

Skip automatic Codex for pure library foundations (e.g. Phase 18A sync store) unless Leader asks.
