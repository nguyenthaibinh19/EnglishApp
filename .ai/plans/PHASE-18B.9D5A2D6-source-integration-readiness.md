# Phase 18B.9D5A2D6 — Source integration readiness audit

Status: **CLOSED — LEADER ACCEPTED: `READY_FOR_SOURCE_INTEGRATION_REVIEW`** (2026-11-17).

Leader acceptance means the import is technically suitable for preparing an integration candidate. It is **not** approval to merge source into main. Import remains **unmerged**. The 17-file frozen import is unchanged. In-repo regression tests are required before integration acceptance. No source commit/push/PR is authorized by this acceptance alone.

Follow-on: D5A2D7 prepares a local source candidate and in-repo tests without merge authorization.

Audit baseline `origin/main`: `e80ce2e7cb9fa4f17b8b7466d8ade2d8bf019ea0` (includes D5A2D5 Leader acceptance docs).  
D5A2D5 acceptance checkpoint (Stage 0 of this task): same `e80ce2e…` after Stage 0 push from parent `5ce081c…`.

## Context already decided

- D5A2D5 **CLOSED — Leader Accepted: revised WSL isolation safety gate** (A/B/C/D/E1/E2/F/G/H).
- Historical D5A2D2 / D5A2D3 remain **OVERALL FAIL**.
- Phase 18B.9 **OPEN**; production **NOT READY**; Drive **NOT CONFIGURED**; Cloud Sync **OFF**.

## Exact SHAs

| Ref | SHA |
|---|---|
| `origin/main` (audit start after Stage 0) | `e80ce2e7cb9fa4f17b8b7466d8ade2d8bf019ea0` |
| Import branch tip `origin/phase18b9/d5a2d0-p1-source-import` | `98b590ef5707e0c84bf68175ed59cdc17d8753c5` |
| Merge-base | `3463971b7255696ceea205215392315868d8ae91` |

Divergence (`git rev-list --left-right --count origin/main...98b590e`):

- **main ahead:** 11 commits (documentation / governance only since merge-base; sibling path does **not** include the import tree).
- **import ahead:** 1 commit — `98b590e chore(offbox): import D5A2D0 canonical Python modules`.

Parent of both `f845632` (docs on main lineage) and `98b590e` (source) is `3463971` — **sibling commits**, not a stacked merge.

## A. Git divergence / merge risk

| Check | Result |
|---|---|
| File-level change on import vs merge-base | **17 files added**, all under `deploy/hetzner/offbox/` |
| Allowlist unchanged | **Yes** — exactly the accepted 15 `.py` + `SHA256SUMS` + `SOURCE_AUTHORITY.md` |
| `deploy/hetzner/offbox` on current main | **Absent** |
| `git merge-tree` dry conflict markers | **None** observed (`NO_CONFLICT_MARKERS`) |
| Real merge / rebase / cherry-pick | **Not executed** |

Merge risk: **Low** for a future explicitly authorized merge (additive new directory). Still requires Leader/Owner authorization; do not treat this audit as merge permission.

## B. Source integrity

| Check | Result |
|---|---|
| SHA-256 of 15 modules vs import `SHA256SUMS` | **15/15 MATCH** |
| Same hashes vs D5A2D0 inventory table | **15/15 MATCH** |
| Module bytes modified in this audit | **No** |
| Embedded live secrets | **No** — markers such as `AGE-SECRET`, `refresh_token`, `client_secret`, `ya29.` appear as **rejection/redaction/parameter names**, not credential material (spot-checked) |

### Module inventory (import `98b590e`)

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

## C. Repository compatibility

| Topic | Finding | Class |
|---|---|---|
| Packaging | No `__init__.py`; modules use `sys.path` insert when run as scripts — matches existing helper/worker design | FOLLOW-UP (document ExecStart/PYTHONPATH when packaging) |
| Deploy conventions | Lives under existing `deploy/hetzner/`; `setup.sh` `FILES=(…)` packages **app/** account-server modules only — **does not** reference `offbox/` | OK for archive landing |
| Python version | Uses `X \| Y` unions (`int \| None`, etc.) → needs **Python ≥ 3.10** at runtime | **BLOCKER FOR PRODUCTION** until VPS Python confirmed; not a tree-merge conflict |
| Entry points | `snapshot_helper.main`, `backup_worker.main` — not wired by setup.sh | OK |
| Dependencies | stdlib + external `age` binary / OAuth/HTTPS at runtime; no new pip pins in import | FOLLOW-UP for production packaging |
| Test discovery | Import adds **no** pytest modules; existing `tests/test_hetzner_package.py` only checks setup.sh app file list | See §D |
| Account-server / Cloud Sync conflict | No code path in import enables sync; separate from `backup_accounts.py` / sync timers | OK |
| Production assumptions | SOURCE_AUTHORITY states archive ≠ deploy; Drive NOT CONFIGURED; Cloud Sync OFF | OK |

## D. Test coverage inventory

| Coverage | Where today | On import branch? |
|---|---|---|
| Framing / worker / helper contract (E1/E2) | D5A2D4 lab `results-e1e2-r3` + harness | **No** |
| WSL isolation A–H | D5A2D2/D3 labs | **No** |
| Fake/loopback/live harnesses | Tools labs (`fake_drive`, `loopback_drive`, `live_synthetic_once`, `tests/run_*`) | **Intentionally absent** (SOURCE_AUTHORITY) |
| In-repo pytest for offbox | — | **Absent** |

### Minimal coverage proposed **before source integration is accepted** (same authorized PR or hard gate)

1. **Hash gate test** — fail CI/local if `deploy/hetzner/offbox` files disagree with `SHA256SUMS` / frozen inventory.
2. **Framing unit tests** — truncated/`verified`/`send_all` OSError paths (E1/E2 contract, no systemd).
3. **Import smoke** — load modules from `deploy/hetzner/offbox` without network/VPS.
4. **Boundary assertion** — `setup.sh` FILES list still excludes `offbox/` (no accidental deploy).

Class: **BLOCKER FOR SOURCE INTEGRATION ACCEPTANCE** (approval gate), not a git conflict. Landing the tree without these is discouraged; audit still marks the branch **technically mergeable** for Leader review.

## E. Deployment boundary

| Check | Result |
|---|---|
| Production systemd units in import | **None** |
| Credentials / age private identity in import | **None** |
| Implicit timers/startup | **None** |
| Cloud Sync activation | **None** |
| VPS install authorized by import | **No** |

## F. Risks classified

### BLOCKER FOR SOURCE INTEGRATION

- None that prevent a clean **additive** merge of the 17-file allowlist.
- **Acceptance gate (required before calling integration “accepted”):** minimal in-repo tests in §D — treat as corrections to land with or immediately before the authorized merge PR, not as unblocking the review itself.

### BLOCKER FOR PRODUCTION

- Import branch **unmerged** (until separately authorized).
- No approved production unit set / install plan executed.
- Production **Python version** unread (need ≥3.10 for current type syntax).
- Production SQLite **journal mode** unread.
- `StateDirectory=` ownership risk on pre-existing dirs (G is WSL disposable only).
- Worker/helper identity mapping must use real VPS uids/units (lab uids are not production).
- Google Drive **NOT CONFIGURED**; OAuth materials absent by design.
- Daily monitoring + restore drill **not installed**.
- Cloud Sync must remain **OFF**.

### DOCUMENTATION / FOLLOW-UP ONLY

- Document PYTHONPATH / ExecStart layout for offbox scripts.
- Keep lab-only harnesses out of the allowlist unless separately approved.
- Record that revised WSL gate ≠ production readiness.

## Proposed minimal safe integration sequence

1. Leader/Owner **authorize** a source-integration PR (this audit ≠ authorization).
2. Open PR: merge `98b590e` allowlist into current `main` (prefer merge commit or explicit allowlisted file bring-up — **no force**, no unrelated files).
3. In the **same** authorized change set (or blocking prerequisite): add §D minimal tests + SHA gate.
4. Verify `setup.sh` still does not ship/install offbox; confirm CI/local tests green.
5. Fast-forward/merge only after Leader review of the PR.
6. **Stop** — do not install units, enable timers, configure Drive, or touch production DB.

## Explicit approval gates

| Gate | Owner |
|---|---|
| Accept this audit verdict | ChatGPT Leader |
| Authorize merge PR | Product Owner + Leader |
| Accept in-repo offbox tests | Leader |
| Any VPS/unit/Drive step | Separate brief only |

## Recommendation

**READY_FOR_SOURCE_INTEGRATION_REVIEW**

Rationale: additive 17-file allowlist, hashes match inventory, no merge-tree conflicts, deployment boundary intact, no embedded secrets. Integration **acceptance** still requires authorized merge + minimal tests; production remains separately blocked.

## Authorization confirmation

Documentation and read-only git/object inspection only. No merge, rebase, cherry-pick, source edit, VPS/SSH, Google/OAuth, Web/AI changes, Cloud Sync, or production actions.
