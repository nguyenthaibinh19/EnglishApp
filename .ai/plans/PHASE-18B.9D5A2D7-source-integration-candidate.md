# Phase 18B.9D5A2D7 — Source integration candidate & regression tests

Status:

- **D5A2D7-R2 CLOSED — LEADER ACCEPTED**
- **D5A2D7-P1 SOURCE COMMITTED AND PUSHED TO REVIEW BRANCH — NOT MERGED**

Not a merge. Not production. **PR NOT CREATED.**

## P1 source commit

| Field | Value |
|---|---|
| Review branch | `phase18b9/d5a2d7-source-candidate` |
| Source commit | `e2160e77c4849606cad5e614dedfd2f79d8088dc` |
| Parent | `182a4a7681255b5932130744c98a4ad6732f0156` |
| Remote | `origin/phase18b9/d5a2d7-source-candidate` @ same SHA |
| Files | Exact 23 (17 offbox + 6 tests/support) |
| Module hashes | Committed Git blob bytes **15/15 MATCH** accepted D5A2D0-P1 inventory |
| `origin/main` | Docs only; **no** `deploy/hetzner/offbox/` |

## R1 → R2 → P1

- **R1 Leader finding:** NEEDS MINOR CORRECTIONS (tests only; frozen modules accepted).
- **R2 corrections:** `__pycache__` tolerance; pinned D5A2D0-P1 SHA-256 inventory; stronger E1 state-history + encrypt/upload spies; tighter setup.sh enable assertion. Leader Accepted.
- **P1:** Candidate fast-forwarded to docs main `182a4a7`; one source commit; non-force push to review branch only.

## Baselines

| Ref | SHA |
|---|---|
| Expected main before Stage 0 | `108bf068735081cc15d4c96c03154dad5a9f2b4f` |
| Stage 0 docs (D5A2D6 CLOSED) | `1ee179e8397903ea167597b16d9dcb335566bfaa` |
| Docs main at P1 commit parent | `182a4a7681255b5932130744c98a4ad6732f0156` |
| Source commit (review branch) | `e2160e77c4849606cad5e614dedfd2f79d8088dc` |
| Approved import authority | `98b590ef5707e0c84bf68175ed59cdc17d8753c5` |

## Candidate location

| Field | Value |
|---|---|
| Worktree | `D:\EnglishApp-worktrees\phase18b9-d5a2d7-source-candidate` |
| Branch | `phase18b9/d5a2d7-source-candidate` |
| State | Source committed and pushed to review branch; **not** on main |

## Leader context

- D5A2D6 **CLOSED — Leader Accepted: READY_FOR_SOURCE_INTEGRATION_REVIEW** (not merge approval).
- D5A2D5 revised WSL gate remains CLOSED — Leader Accepted.
- Historical D5A2D2/D5A2D3 FAIL unchanged.
- Phase 18B.9 OPEN; production NOT READY; Drive NOT CONFIGURED; Cloud Sync OFF.

## Exact 17-file import inventory

Under `deploy/hetzner/offbox/` (bytes from `98b590e`):

```text
age_encrypt.py
attempt_store.py
backup_worker.py
credential.py
drive_upload.py
framing.py
https_transport.py
logutil.py
monitoring.py
oauth_exchange.py
peer_auth.py
provenance.py
restore_check.py
snapshot_copy.py
snapshot_helper.py
SHA256SUMS
SOURCE_AUTHORITY.md
```

**15/15 SHA-256 MATCH** against accepted pinned inventory for working-tree, staged, and committed Git blob bytes.

No units, keys, tokens, binaries, fake Drive servers, or lab-only scripts imported.

## New test inventory

| File | Group |
|---|---|
| `tests/offbox_support.py` | Shared helpers (not a test module) |
| `tests/test_offbox_integrity.py` | A — frozen integrity |
| `tests/test_offbox_framing.py` | B — framing |
| `tests/test_offbox_interrupt_fail_closed.py` | C — E1/E2 |
| `tests/test_offbox_import_smoke.py` | D — import smoke |
| `tests/test_offbox_setup_boundary.py` | E — setup.sh boundary |

Canonical offbox Python modules were **not** modified to make tests pass.

## Test results

Interpreter: **Python 3.13.13** (Windows win32), pytest 9.1.1. Runtime assumption: **Python ≥ 3.10**.

| Suite | Result | Exit |
|---|---|---|
| R1 focused offbox A–E | **37 passed** | 0 |
| R1 adjacent `tests/test_hetzner_package.py` | **1 passed** | 0 |
| R2 focused + adjacent | **39 passed** | 0 |
| P1 pre-commit focused + adjacent | **39 passed** (0 skipped) | 0 |
| Full pytest (historical) | **626 passed**, **14 skipped**, **8 errors** | 1 |

Full-suite errors are **pre-existing** `tests/test_offbox_recovery_poc.py` setup failures (`restic is not installed. Refusing to download or install`). Not introduced by the offbox allowlist or D5A2D7 tests. Skips left as skips.

## Setup.sh boundary

Static inspection (setup.sh **not** executed):

- `FILES=(…)` excludes all offbox modules.
- No `offbox` string / copy / install path.
- No offbox systemd units enabled; enable lines remain `language-guard.service`, backup timer, caddy only.
- Account-server packaging unchanged.

## Risks and remaining blockers

### Before merge / PR acceptance

- Separate Leader brief required before PR creation or merge into main.
- Full-suite restic POC errors remain an environment caveat (optional skip/mark or install restic in CI — out of scope here).

### Production (unchanged)

- No merge yet; no units; Python on VPS unread; journal mode unread; StateDirectory risk; Drive NOT CONFIGURED; monitoring/drill absent; Cloud Sync OFF.
- Historical D5A2D2/D5A2D3 FAIL preserved.

## Next approval needed

**ChatGPT Leader:** authorize PR creation and/or merge separately. P1 does **not** authorize merge or production.

## Authorization confirmation

Source commit and review-branch push completed under D5A2D7-P1. **PR NOT CREATED. NOT MERGED. NOT DEPLOYED.** No VPS/SSH, setup.sh execution, Google/OAuth, Web/AI changes, Cloud Sync, or production operations.
