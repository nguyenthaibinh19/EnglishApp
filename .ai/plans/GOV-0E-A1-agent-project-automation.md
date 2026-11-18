# GOV-0E-A1 — Agent Project automation pilot

Status: **DESIGN + LOCAL CANDIDATE PREPARED — AWAITING LEADER REVIEW**  
Not activated. No live Project mutations. No token created. No merge.

## Baselines

| Ref | Value |
|---|---|
| Docs / candidate base | `60f6a9a9a2c2c4142d3bb38587cf9a6aa5d5d798` (`origin/main`) |
| Project | Private `LangstudyGuard` — https://github.com/users/nguyenthaibinh19/projects/1 |
| Owner / number | `nguyenthaibinh19` / `1` |
| GOV-0E | **CLOSED — Leader Accepted** (setup/docs only) |
| Pilot repo | EnglishApp only |

## Candidate location

| Field | Value |
|---|---|
| Worktree | `D:\EnglishApp-worktrees\gov0e-a1-project-automation` |
| Branch | `gov0e/a1-project-automation` |
| State | Uncommitted workflow + script + offline tests only |
| Production App code | Untouched |
| Deployment scripts | Untouched |

## 1. Proposed architecture

Event-driven GitHub Actions job on EnglishApp `issues` (`labeled` / `unlabeled`):

1. Ignore events whose label does not start with `lsg:`.
2. Fail closed on unsupported `lsg:*` labels (e.g. `lsg:done`).
3. Require `lsg:tracked` before any Project mutation.
4. Resolve user Project V2 ID + Status field/option IDs via GraphQL (dynamic; not hard-coded option IDs).
5. Find existing Project item by Issue node ID; if absent, `addProjectV2ItemById`.
6. Set Status via `updateProjectV2ItemFieldValue` using typed variables.
7. Rely on the Project’s built-in “Item added → Backlog” workflow for new items; still set desired Status explicitly for idempotency.

Automation may set: **Backlog**, **In Progress**, **In Review**, **Blocked**.  
Automation must **not** set: **Done**, **Ready**, or **Approval Gate = Approved**.

## 2. Workflow and script inventory

| Path | Role |
|---|---|
| `.github/workflows/lsg-project-sync.yml` | Issue label trigger; minimal permissions; no `pull_request_target` |
| `tools/lsg_project_sync/sync_project_item.py` | GraphQL sync (stdlib only) |
| `tools/lsg_project_sync/__init__.py` | Package marker |
| `tests/test_lsg_project_sync.py` | Offline mocked API tests |

## 3. Label → Status mapping

| Label | Effect |
|---|---|
| `lsg:tracked` | Include issue in Project; Status **Backlog** (if no higher lifecycle label) |
| `lsg:doing` | Status **In Progress** (requires `lsg:tracked`) |
| `lsg:review` | Status **In Review** (requires `lsg:tracked`) |
| `lsg:blocked` | Status **Blocked** (requires `lsg:tracked`) |

Priority when multiple lifecycle labels present: **Blocked > In Review > In Progress > Backlog**.

Unrelated issues (no `lsg:tracked`) are ignored. Duplicate deliveries are idempotent (find-before-add).

## 4. Authentication approach

| Item | Value |
|---|---|
| Secret name | `LSG_PROJECT_TOKEN` |
| Why not `GITHUB_TOKEN` | User-owned Project V2 mutations typically require a PAT / fine-scoped token with Project write; default Actions token is insufficient |
| Token creation | **Owner only** — agents must not create or request the token in this milestone |
| Logging | Print audit JSON with issue number / item id / status only — never titles, bodies, or token material |

Workflow permissions: `contents: read`, `issues: read`. Project writes use the dedicated secret only.

## 5. Security boundaries

| Risk | Mitigation |
|---|---|
| GraphQL injection via title/body | Typed variables only; title/body never concatenated into query/shell |
| Untrusted PR code + Project secret | No `pull_request_target`; issues events only |
| Over-privileged automation | Cannot set Done / Approval Gate Approved |
| Treating Project Status as deploy auth | Documented as tracking metadata only ([GITHUB_PROJECT_OPERATIONS.md](../ecosystem/GITHUB_PROJECT_OPERATIONS.md)) |
| Credential leakage | Secret via Actions; never printed; fail closed on HTTP/schema errors |
| Processing unrelated issues | Require `lsg:tracked`; ignore non-`lsg:` labels |

### Future owner-controlled approval handoff (not implemented)

A later milestone may define an Owner-only path to set Approval Gate / Done (e.g. explicit Owner label or Project UI). **GOV-0E-A1 does not implement that path.**

## 6. Offline validation results

Interpreter: Python 3.13.13 (Windows). Command:

`python -m pytest tests/test_lsg_project_sync.py -q`

| Result | Count | Exit |
|---|---|---|
| Passed | **14** | **0** |

Coverage includes: new tracked; In Progress; In Review; Blocked; duplicate delivery; unknown/untracked; missing permissions; invalid/missing Status options; unauthorized Done refusal; hostile title/body not entering GraphQL variables.

**No live Project mutations or live webhook tests were run.**

## 7. Manual Owner setup (after Leader activation approval)

1. Create repository labels: `lsg:tracked`, `lsg:doing`, `lsg:review`, `lsg:blocked`.
2. Create a fine-scoped token (or GitHub App) able to read EnglishApp issues and write the user Project `LangstudyGuard` (#1).
3. Store it as Actions secret `LSG_PROJECT_TOKEN` on EnglishApp (Owner only).
4. Merge/activate the workflow only after Leader acceptance of this pilot.
5. Smoke-test on a disposable tracked issue; confirm single Project item and Status transitions.
6. Rollback: disable workflow file or delete `LSG_PROJECT_TOKEN`; Project items remain (no mass delete).

## 8. Approval gates before activation

| Gate | Required |
|---|---|
| Leader review of this design + candidate | ChatGPT System Architect |
| Owner secret creation / store | Product Owner |
| Merge of workflow to `main` | Separate explicit authorization |
| Live Project smoke test | Separate explicit authorization |
| Done / Approval Gate automation | Explicitly **out of scope** / future Owner handoff |

## 9. Test and rollback plan

- Pre-merge: keep offline suite green; no live calls.
- Post-activation (if authorized): one disposable issue through tracked → doing → review → blocked; verify no duplicates; remove labels and confirm unlabeled recomputation.
- Rollback: disable workflow; revoke token; leave Project board data intact.

## 10. Restrictions observed

No live Project mutations; no token creation; no issue label changes; no source merge; no production/VPS/Google/Web/AI/LocalAIProvider work; no automatic next milestone.

## Next decision

**ChatGPT Leader:** accept design / request corrections / authorize (or withhold) a follow-on activation brief.
