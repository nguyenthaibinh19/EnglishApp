# Phase 18B.9D5A2D7 — Source integration candidate & regression tests

Status: **CANDIDATE READY FOR LEADER REVIEW — `READY_FOR_SOURCE_COMMIT_REVIEW`.**  
Source remains **uncommitted / unpushed / no PR**. Not a merge. Not production.

## Baselines

| Ref | SHA |
|---|---|
| Expected main before Stage 0 | `108bf068735081cc15d4c96c03154dad5a9f2b4f` |
| Stage 0 docs (D5A2D6 CLOSED) | `1ee179e8397903ea167597b16d9dcb335566bfaa` |
| Candidate branch HEAD (docs base; **no source commit**) | `1ee179e8397903ea167597b16d9dcb335566bfaa` |
| Approved import | `98b590ef5707e0c84bf68175ed59cdc17d8753c5` |

## Candidate location

| Field | Value |
|---|---|
| Worktree | `D:\EnglishApp-worktrees\phase18b9-d5a2d7-source-candidate` |
| Branch | `phase18b9/d5a2d7-source-candidate` |
| Working tree | Uncommitted allowlist + new tests only |
| Review diff | `diff/d5a2d7-source-candidate.diff` (local; **not** committed) |

**Divergence note:** Documentation checkpoints continue on the docs worktree → `main`. The candidate branch stays at Stage 0 SHA with local uncommitted source/tests. Reconcile (bring docs + candidate together) before any later authorized PR — do **not** silently rebase/merge.

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

**15/15 SHA-256 MATCH** against `SHA256SUMS` after materialization (rechecked after git autocrlf warnings; working-tree hashes still match).

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
| Focused offbox groups A–E | **37 passed** | 0 |
| Adjacent `tests/test_hetzner_package.py` | **1 passed** | 0 |
| Full pytest | **626 passed**, **14 skipped**, **8 errors** | 1 |

Full-suite errors are **pre-existing** `tests/test_offbox_recovery_poc.py` setup failures (`restic is not installed. Refusing to download or install`). Not introduced by the offbox allowlist or new D5A2D7 tests. Skips left as skips.

## Setup.sh boundary

Static inspection (setup.sh **not** executed):

- `FILES=(…)` excludes all offbox modules.
- No `offbox` string / copy / install path.
- No offbox systemd units enabled; enable lines remain `language-guard.service`, backup timer, caddy only.
- Account-server packaging unchanged.

## Risks and remaining blockers

### Before source commit/PR acceptance

- Leader must authorize source commit / PR (this milestone does not).
- Reconcile candidate uncommitted tree with post-D5A2D7 docs on `main` before PR.
- Full-suite restic POC errors remain an environment caveat (optional skip/mark or install restic in CI — out of scope here).

### Production (unchanged)

- No merge yet; no units; Python on VPS unread; journal mode unread; StateDirectory risk; Drive NOT CONFIGURED; monitoring/drill absent; Cloud Sync OFF.

## Next approval needed

**ChatGPT Leader:** accept `READY_FOR_SOURCE_COMMIT_REVIEW` and issue a **separate** brief if/when source may be committed, pushed, or PR’d.

## Authorization confirmation

No source commit, push, PR, merge, VPS/SSH, setup.sh execution, Google/OAuth, Web/AI changes, Cloud Sync, or production operations.
