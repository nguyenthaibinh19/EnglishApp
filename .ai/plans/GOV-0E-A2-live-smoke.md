# GOV-0E-A2 — Live Project automation smoke

Status: **CLOSED — LEADER ACCEPTED** (S1/S2). Pilot complete.

## Result

| Item | Value |
|---|---|
| Disposable issue | EnglishApp [#11](https://github.com/nguyenthaibinh19/EnglishApp/issues/11) — CLOSED Completed |
| Project item | `PVTI_lAHOB2-53c4BrAcGzhJ2vgs` (exactly one throughout) |
| S1 | `lsg:tracked` → Backlog — PASS |
| S2 | doing → review → blocked → unwind to Backlog — PASS (6 transitions) |
| Actions | Seven successful `lsg-project-sync` runs (Leader-verified) |
| Post-acceptance | Owner/Leader closed #11; Project Status set to **Done** after explicit acceptance |

## Known limitations (retained)

- Project field read/write is **not** compare-and-swap; concurrent manual Status edits can race an in-flight sync.
- Built-in Project workflow **Item added → Backlog** can race the script’s first Status write.
- Automation must **not** set Done or Approval Gate; Done requires explicit authorized approval (as for #11).

## Ordinary Project use (post-pilot)

1. Open an Issue when starting an authorized milestone.
2. Add it to LangstudyGuard (or apply `lsg:tracked`).
3. Use `lsg:doing` / `lsg:review` / `lsg:blocked` for automated Status.
4. Report completion as **In Review**.
5. Set **Done** and close the Issue only after explicit valid approval.

Do not add governance review cycles unless a concrete new risk appears.
