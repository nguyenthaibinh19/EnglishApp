# Phase 18C.3A — Account Sync reliability and gap audit

Status: **Ready for Architect review** (`APP_18C3A_READY_FOR_ARCHITECT_REVIEW`)  
Authorization: `APP_18C3A_LOCAL_READINESS_AUDIT_AUTHORIZED`  
Baseline: `main` `dc6dc8a0b51a3a258598c2b7735c9d6e9e059987` (clean, tracking `origin/main`)  
Date: 2026-11-22  
Cloud Sync: **OFF** · 18B.9: **PAUSED, NOT CLOSED** · Staging: **RESERVED** · Sync pilot: **NO-GO**

Production activation is not authorized. No VPS, EXE, RC account, or `STUDY_SYNC_ENABLED` change was made.

## 1. Baseline

| Check | Result |
|-------|--------|
| `git rev-parse HEAD` | `dc6dc8a0b51a3a258598c2b7735c9d6e9e059987` |
| `git status` at start | Clean `main...origin/main` |
| PR #27 | Merged; Owner GUI smoke closed in `dc6dc8a` |
| 18C.1 / 18C.2 | CLOSED — Architect Accepted. Per-account SQLite, outbox, background worker, progress HTTP, and signed-in GUI paths already exist. This audit does not treat the ADR-022 milestone table's "18C.3 = build the worker" row as remaining work. |
| Stale doc | `.ai/invariants.md` still opened the ADR-022 bullet with "architecture only and is not implemented." That sentence is superseded for the 18C.1/18C.2 slice. The ledger rules in the same bullet are still unimplemented. |

## 2. Coverage matrix

Labels mean the requirement has both code and a passing synthetic test (`IMPLEMENTED_AND_TESTED`), code without a committed test (`IMPLEMENTED_UNVERIFIED`), an incomplete slice (`PARTIAL`), no implementation (`MISSING`), or an accepted deferral (`DEFERRED_BY_DESIGN`).

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Two devices, same account: vocabulary add/edit converges | `IMPLEMENTED_AND_TESTED` | `test_two_device_vocab_and_progress_convergence`, `test_scenario_b_same_account_sync_two_devices` drive `sync_once` (the worker's cycle) in one process. Not a separate OS-process soak. |
| Progress and attempt text propagate | `IMPLEMENTED_AND_TESTED` | Same tests plus `test_scenario_b_learning_attempts_progress_srs_mistake_book`. Device 2 sees `event_id`, `seen`, and streak. |
| Offline answer commits; outbox survives restart; reconnect is idempotent | `IMPLEMENTED_AND_TESTED` | `test_idempotent_progress_retry_and_outbox_durability`, `test_interrupted_transfer_leaves_pending_and_retries`, offline block in the two-device test. Restart checks cursors after `close()`. |
| Server accept before local ack retries the same `event_id` | `IMPLEMENTED_AND_TESTED` | `test_interrupted_transfer_leaves_pending_and_retries`; server `UNIQUE (user_id, event_id)` plus client ack. |
| Download cursor advances only after the page transaction commits | `IMPLEMENTED_AND_TESTED` | Code: `apply_progress_changes_page` commits cursor and rows together and rolls back on conflict. Local probe `tests/test_18c3a_progress_cursor_rules.py` (4 passed). **Not committed** — this authorization forbids an application-source commit. |
| Older snapshot does not regress confirmed; new attempt is kept | `IMPLEMENTED_AND_TESTED` | `_apply_confirmed_snapshot_unlocked` returns when `incoming_version` is lower. Same local probe. |
| Equal `state_version` with different content writes nothing and does not move the cursor | `IMPLEMENTED_AND_TESTED` | Raises `AccountLocalConflict` inside the page transaction. Same local probe. |
| Provisional keeps uncovered pending attempts after a page | `IMPLEMENTED_AND_TESTED` | `_rebuild_provisional_unlocked` folds pending outbox rows onto confirmed. Same local probe: confirmed `seen=1`, provisional `seen=2`, streak reset by the pending wrong answer. |
| OS kill before/after the local answer commit | `IMPLEMENTED_UNVERIFIED` | `record_learning_attempt` is one SQLite transaction. No test kills the process. Exception rollback of a bad page is tested. |
| Upload ack must not move the download cursor | `IMPLEMENTED_UNVERIFIED` | `acknowledge_progress_upload` stores confirmed progress and does not set `progress_cursor`. No direct assertion in the committed suite. |
| Account A/B isolation | `IMPLEMENTED_AND_TESTED` | `test_account_isolation_and_guest_preservation`, `test_scenario_a_account_isolation_no_leakage`. |
| Guest `vocab.json` is not silently uploaded | `IMPLEMENTED_AND_TESTED` | Guest preservation test; `test_legacy_import_requires_consent`. Vocabulary consent import exists. Attempt JSONL import does not. |
| Staging/dev cannot write production; credentialed redirects refused | `IMPLEMENTED_AND_TESTED` | `test_app_environment_isolation.py` (18), including `test_f2_account_client_refuses_redirect_to_production`. Staging guard: `test_sync_staging_isolation.py` (not re-run in this pass; existing suite, no code change). |
| UI: Synced, Pending, Offline, Conflict | `IMPLEMENTED_AND_TESTED` | Learning-sync status assertions and `test_offline_and_auth_remain_distinct`, `test_conflict_409_not_treated_as_unavailable`. |
| UI: Unavailable when Sync routes 404 | `IMPLEMENTED_AND_TESTED` | `test_sync_unavailable_status.py` (8). This state is newer than the ADR-022 table and is required while production Sync stays off. |
| Skewed `occurred_at` must not set `due_at` | `IMPLEMENTED_UNVERIFIED` | `sync_store` folds SRS with server `received_at`. Day buckets correctly keep `occurred_at` (`test_account_day_buckets_use_occurred_at_not_received_at`). No test submits a years-off `occurred_at` and asserts `due_at`. |
| Guest AttemptHistory ledger: consent, high-water, offset identity | `DEFERRED_BY_DESIGN` | 18C.2 acceptance: vocabulary consent only. No `legacy_import_ledger` table or importer. `attempts.jsonl` stays outside the account DB. |
| Replacement, truncation, overlap preflight, `skipped_overlap` | `DEFERRED_BY_DESIGN` | Specified in ADR-022. No implementation and no tests. |
| Quotas, rate limits, off-box restore drill, production flag | `DEFERRED_BY_DESIGN` | ADR-022 security gates and 18B.9. Not this audit's implementation scope. |

No material source defect was reproduced. The cursor probe matched the ADR rules on a temporary database.

## 3. Tests actually run

Command, from `D:\EnglishApp-worktrees\env-isolation`, with `PYTHONPATH` set to `app`:

```text
python -m pytest tests/test_18c3a_progress_cursor_rules.py tests/test_account_learning_sync.py tests/test_account_ux_two_device.py tests/test_18c2_r1_corrections.py tests/test_study_data_signed_in.py tests/test_sync_unavailable_status.py tests/test_app_environment_isolation.py tests/test_account_add_word_save.py -q --tb=line
```

Result: **73 passed, 0 failed, 0 skipped** (exit 0, about 34s). Collected counts: 18c2 R1 7, cursor probe 4, add-word 6, learning sync 13, two-device UX 9, environment isolation 18, signed-in study data 8, sync unavailable 8.

All fixtures use `tmp_path` or the in-test staging lab. Owner RC account id 1 was not opened.

## 4. Gaps, by severity

1. **High, deferred product scope.** Guest `attempts.jsonl` never becomes account events. There is no ledger, so truncation, replacement, and overlap cannot be safe. New signed-in answers are unaffected.
2. **Medium, evidence gap.** The four cursor/snapshot tests pass locally but are not on `main`. A future edit can break rollback without CI noticing.
3. **Medium, unverified rule.** Server `due_at` is computed from `received_at`, but no test holds a skewed `occurred_at` constant and checks the schedule.
4. **Low.** No process-kill test around the local answer transaction. The code uses one `BEGIN IMMEDIATE` / `COMMIT`.
5. **Low, docs.** `.ai/invariants.md` still says ADR-022 "is not implemented," which would send a later agent to rebuild the worker.

## 5. One next implementation task

**18C.3B — Guest AttemptHistory import ledger, local only.**

**Problem.** After sign-in, new answers sync through the account outbox, but the guest JSONL history cannot move into that account without the ADR-022 ledger. Doing it without offset identity, consent, and overlap preflight would duplicate or drop history.

**User value.** An explicit consent import can bring past attempts into the account once each, leave `attempts.jsonl` unchanged, and refuse a replacement file's duplicate lines until the learner chooses.

**File scope.**

- `app/account_local_store.py` — additive `legacy_import_source` and `legacy_import_ledger` tables only.
- `app/legacy_attempt_import.py` — new read-only pass.
- `app/legacy_import_app.py` — call the pass only after the existing explicit consent action. No login-time import.
- `tests/test_legacy_attempt_ledger.py` — new.
- Commit the already-passing `tests/test_18c3a_progress_cursor_rules.py` in the same change so the cursor rules stay locked. Do not expand into quotas, VPS, or Sync activation.

**Acceptance.** On synthetic temp files only:

- Import does not modify `attempts.jsonl`.
- Two identical lines at different offsets become two events.
- A second pass at the same offset and hash allocates no new `event_id`.
- A line with no `vocab_id` is not uploaded.
- A partial last line gets no ledger row.
- Truncation keeps the imported event. A hash change at an existing offset does not create a second event and does not delete the first.
- A new file identity does not import until a new consent.
- Overlap preflight runs before any outbox insert. A matching hash is skipped. Import-as-distinct happens only after an explicit choice and does not delete the original.
- A crash before commit does not move `high_water`.

**Safety.** Additive SQLite tables. Opening an account DB later would create empty tables, not rewrite vocabulary, outbox, or guest JSONL. Do not point tests or the importer at `%APPDATA%\langstudyguard-rc`. No `STUDY_SYNC_ENABLED`. No production EXE.

**Dependencies.** None on 18B.9 or 18B.3 gates. Blocked only by Architect authorization to edit application source. Can be completed entirely on a local synthetic server and temp directories.

## 6. Files and safety

Committed from this audit: this plan, the current-state checkpoint, the handoff, and the invariants clarification.

Not committed: `tests/test_18c3a_progress_cursor_rules.py` (local probe, 4 passed).

Not touched: application runtime code, `dist/`, `dist-rc/`, RC account id 1, recovery backups, VPS, Web repo, Local AI repo.

## Boundaries

Cloud Sync production **OFF**. 18B.9 **PAUSED, NOT CLOSED**. Staging **RESERVED**. No public Release. No new milestone starts until the Architect accepts this audit.
