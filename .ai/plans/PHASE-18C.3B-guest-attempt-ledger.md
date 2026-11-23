# Phase 18C.3B — Guest AttemptHistory import ledger

Status: **18C.3B CLOSED — Architect Accepted** (`APP_18C3B_PR28_ARCHITECT_MERGE_APPROVED`)  
Authorization: `APP_18C3B_LOCAL_IMPLEMENTATION_AUTHORIZED`  
Decision accepted: `APP_18C3A_ARCHITECT_ACCEPTED`  
Merge decision: `APP_18C3B_PR28_ARCHITECT_MERGE_APPROVED`  
PR: [#28](https://github.com/nguyenthaibinh19/EnglishApp/pull/28) merged  
Merge SHA: `610d979434f8ff10274e8000916563e1e2f57126`  
Approved source HEAD: `867700198665edb80ba5b96fbf72a5bd0ae96fa2`  
Reviewed base: `2cea161f5453909f2503ee1bc3cb41c153603010`  
Date: 2026-11-23  
Cloud Sync: **OFF** · 18B.9: **PAUSED, NOT CLOSED** · Staging: **RESERVED** · Sync pilot: **NO-GO**

Sections 1–9 below are the preserved pre-merge review snapshot. The closure is section 10.

## 1. Baseline and worktree

| Check | Result |
|-------|--------|
| `git rev-parse HEAD` | `2cea161f5453909f2503ee1bc3cb41c153603010` |
| Branch | `main`, tracking `origin/main` |
| Commit | `docs(18c3a): record Account Sync reliability gap audit` |
| Worktree | Local 18C.3B edits only. No commit. |

Review diff: `diff/phase18c3b-guest-attempt-ledger.diff`.

## 2. What landed

Signed-in attempt import is a separate action from vocabulary import.

- `legacy_attempt_consent` binds one account to one file identity. Vocabulary consent does not satisfy it. Granting consent does not enqueue attempts. Revoking consent stops further imports and does not delete accepted attempts.
- `legacy_import_source` stores the canonical path and a byte-offset high-water mark per language and file identity. A replacement identity does not overwrite the previous high-water mark.
- `legacy_import_ledger` uses primary key `(file_identity, offset)`. `line_sha256` covers the raw line bytes, including the terminating newline. Dispositions are `imported`, `skipped_no_vocab_id`, `unreadable`, `source_conflict`, `overlap_pending`, and `skipped_overlap`.
- `app/legacy_attempt_import.py` opens the guest file read-only. Production identity is `win:{volume serial}:{file index}` from `GetFileInformationByHandle`. A reparse point, a missing identity, or a source larger than 32 MiB imports nothing.
- Each complete line commits the ledger row, any new attempt, its pending outbox row, and the high-water update in one SQLite transaction. A failure before commit rolls all of them back.
- The same identity, offset, and hash reuses the original `event_id`. Identical lines at different offsets in the same file become two attempts.
- A rewritten line at an existing offset becomes `source_conflict`. The original event stays. The high-water mark does not move.
- A shorter file keeps accepted rows and stops. Nothing is deleted to match the shorter file.
- A new file identity imports nothing until this account consents to that identity. Before any outbox row for the new identity, each complete line is compared with ledger hashes from other identities. A match stays `overlap_pending` until the learner chooses. Skip writes `skipped_overlap` and no outbox event. Import-as-distinct writes one new event and leaves the original. There is no silent last-write-wins.
- `occurred_at` keeps the guest timestamp for evidence, the Mistake Book, and UTC day buckets. Import does not write `progress_confirmed` and does not copy `progress.json`.
- Provisional scheduling: a batch with no guest import still folds by `occurred_at` and uses that device clock. A batch that contains a guest import folds in outbox id order, which is the upload order. The import’s provisional `due_at` uses the outbox `created_at`, not the guest timestamp. Confirmed SRS still changes only from a server snapshot.
- The Import attempt history button is separate from Import vocabulary. Login, startup, account switch, and vocabulary import do not call it.

`SCHEMA_VERSION` stays 1. The new tables are `CREATE TABLE IF NOT EXISTS` inside the existing schema transaction.

## 3. Migration and rollback

Opening an existing account database adds the three tables and leaves vocabulary consent, outbox, cursors, attempts, and SRS rows in place. A second open does not recreate them.

A crash before `COMMIT` leaves no ledger row, no new attempt, no new outbox row, and the previous high-water mark. That path is covered by `test_failure_before_commit_leaves_no_partial_row`.

Rollback of this feature is to stop calling the importer. The extra tables can remain. There is no down migration that deletes imported attempts. Removing the tables by hand would be a separate, destructive operation and is not part of this change.

## 4. Tests

Command, from `D:\EnglishApp-worktrees\env-isolation`, with `PYTHONPATH` set to the `app` directory:

```text
pytest tests/test_legacy_attempt_ledger.py tests/test_18c3a_progress_cursor_rules.py tests/test_account_learning_sync.py tests/test_account_ux_two_device.py tests/test_18c2_r1_corrections.py tests/test_study_data_signed_in.py tests/test_sync_unavailable_status.py tests/test_app_environment_isolation.py tests/test_account_add_word_save.py
```

Result: **94 passed, 0 failed, 1 skipped**, exit 0, 28.94s.

| Suite | Role |
|-------|------|
| `tests/test_legacy_attempt_ledger.py` | 21 passed, 1 skipped |
| `tests/test_18c3a_progress_cursor_rules.py` | 4 existing untracked cursor rules |
| Adjacent account, sync, environment, and Add Word suites | 69 already on `main` |

Windows execution:

| Test | Result |
|------|--------|
| `test_windows_file_identity_is_stable_across_append` | PASS. Two real files have different identities. Appending keeps the identity and the read bytes match the file. |
| `test_windows_ancestor_junction_file_fails_closed` | PASS. `junction/attempts.jsonl` is refused. The junction directory is an ancestor of the file the app opens. |
| `test_windows_file_symlink_fails_closed` | **SKIP / UNVERIFIED**. Pytest skip reason: `file symlink creation not permitted`. This is not a pass. |

`tests/test_18c3a_progress_cursor_rules.py` uses a temporary `AccountLocalStore`, no network, and no Owner data. It is safe to keep as a proposed test. It is included in the review diff and is not committed.

## 5. Security

- Guest JSONL is not opened for writing. The byte-for-byte test covers the fake-identity path.
- Identity failure and reparse points import nothing and record a short conflict code. The code does not include answer text, prompts, or vocabulary words.
- Attempt consent is per account and per file identity. Account B does not see account A's consent or attempts.
- Missing or invalid `vocab_id` is not repaired from spelling.
- Overlap is not uploaded until an explicit skip or distinct choice.
- No production flag, credential, token, or AppData path is read or written by these tests.

## 6. R1 provisional correction

The first candidate called `_rebuild_provisional_unlocked()` after each imported line. That helper ordered every uncovered attempt by `occurred_at` and passed that timestamp to `apply_review_to_stats`. A guest line from 2020 or 2099 could therefore sort ahead of a newer pending answer and set the provisional due date.

R1 keeps the helper’s local-only path. When an uncovered attempt is a guest import (`source = legacy_import`, or still listed in `legacy_import_ledger` after acknowledgement changes the source to `server`):

- the pending fold is sorted by outbox id, matching `pending_outbox()` upload order;
- that import’s provisional clock is the outbox `created_at`;
- `occurred_at` on the attempt row is not changed;
- `progress_confirmed` is not written by the import.

A normal signed-in attempt, with no import in the uncovered set, still schedules from its own `occurred_at`. Server acknowledgement still applies `progress_after`, whose `due_at` was computed from `received_at` in `sync_store.accept_learning_attempt`. The acknowledgement does not advance the download cursor and does not drop the stored attempt.

The original review diff was 1,954 lines. This R1 package replaces it. The source change is the provisional fold in `app/account_local_store.py`, plus four tests in `tests/test_legacy_attempt_ledger.py`.

## 6b. R2 validation and path safety

R1’s provisional rule is unchanged. `occurred_at` is still the guest timestamp after it passes the same ISO check the server uses (`parse_utc`, then the canonical form `to_utc_iso` returns). An invalid timestamp is `unreadable`. It is not replaced with the current time.

Before an outbox row is created, the translated line is passed through `sync_store._validate_progress_event`. That rejects a non-ISO timestamp, text longer than 500 characters, an empty `expected_answer`, and a non-boolean, non-0/1 `hint_used` such as the string `"false"`. Guest JSON booleans are translated to 0/1 because that is the server’s stored type. A missing or invalid `vocab_id` stays `skipped_no_vocab_id`. Those rows have no `event_id` and no outbox event. A later valid line in the same file can still import.

Windows identity still comes from the volume serial and file index. `read_windows_attempt_source` now rejects `FILE_ATTRIBUTE_REPARSE_POINT` on the file and on each ancestor. A directory junction that only appears as the parent of `attempts.jsonl` is refused before the file is read. The file-symlink case did not run.

## 6c. R3 identity recovery and invalid overlap

R1 and R2 stay in place. After a source identity has been read and its existing ledger prefix has been verified, that pass resolves `identity_unavailable` for the same language. A consent refusal, a failed identity read, or a different language’s conflict does not clear it.

A replacement line whose hash matches an earlier `unreadable` or `skipped_no_vocab_id` row is not an importable overlap. It keeps that disposition, gets no event, and does not enter Import-as-distinct. A later valid line in the same file can still import. A real valid overlap still waits for skip or an explicit distinct choice.

## 7. Known limitations

- File-symlink creation returned "insufficient privilege." `test_windows_file_symlink_fails_closed` is **SKIPPED / UNVERIFIED**, not PASS. The ancestor-junction test did run and passed.
- The importer does not update signed-in day buckets and does not copy `progress.json`. UTC activity history still reads `occurred_at` from the attempt row.
- Sources larger than 32 MiB are refused.
- The dialog explains a blocked import without quoting the file. It does not offer a per-line overlap picker; Skip and Import as distinct apply to the pending overlap offsets from that pass. Closing the chooser leaves the lines pending.
- ADR-022's historical "not implemented" heading is unchanged. This review is the implementation record.

## 8. File inventory

| Path | Change |
|------|--------|
| `app/account_local_store.py` | Additive tables and ledger transactions |
| `app/legacy_attempt_import.py` | New read-only importer |
| `app/legacy_import_app.py` | Separate attempt-history consent and action |
| `tests/test_legacy_attempt_ledger.py` | New regression tests |
| `tests/test_18c3a_progress_cursor_rules.py` | Existing untracked probe, reviewed, not committed |
| `.ai/plans/PHASE-18C.3B-guest-attempt-ledger.md` | This review |
| `.ai/current_state.md` | Checkpoint |
| `.ai/agent_playbook/ACTIVE_HANDOFF.md` | Checkpoint |
| `.ai/invariants.md` | Ledger sentence now points at this local review |
| `diff/phase18c3b-guest-attempt-ledger.diff` | Review diff, not for commit |

## 9. Safety confirmation

- Cloud Sync production remains OFF. `STUDY_SYNC_ENABLED` was not set.
- Phase 18B.9 remains PAUSED, NOT CLOSED. No staging or production pilot.
- No VPS, SSH, systemd, credential, network migration, or deployment.
- No production EXE modification and no release publication.
- No genuine AppData access. RC account id 1, 114 Dutch words, 114 pending outbox rows, and recovery backups were not opened.
- The Owner's 114-word import was not rerun.
- Web and Local AI repositories were not modified.
- No answer text, vocabulary content, tokens, or credentials were logged.

## 10. Closure

**18C.3B CLOSED — Architect Accepted.** PR #28 is merged at `610d979434f8ff10274e8000916563e1e2f57126`. Focused tests: **94 passed, 0 failed, 1 skipped** (Cursor-reported). `test_windows_file_symlink_fails_closed` remains **UNVERIFIED**. Production Cloud Sync **OFF**. Phase 18B.9 **PAUSED, NOT CLOSED**. Staging **RESERVED**. Sync pilot **NO-GO**.

`APP_18C3B_CLOSED_OWNER_HANDOFF_READY`

Do not activate Cloud Sync. Do not start another milestone.
