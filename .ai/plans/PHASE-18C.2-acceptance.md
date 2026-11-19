# Phase 18C.2 — Signed-in GUI account sync (acceptance / demo)

**Status:** CLOSED — Architect Accepted (merged via PR #21).  
**Baseline:** main `8e94f77491cc2f318c93fc511e258d0299ff4d03` (18C.1 CLOSED).  
**Preserve:** 18C.1 CLOSED — Architect Accepted · 18C.2 CLOSED — Architect Accepted · 18B.9 PAUSED, NOT CLOSED · Cloud Sync production OFF.

## Implemented (actual GUI data path)

When a session token and `account_user_id` are present, these Tkinter flows use `study_data.open_study_data()` → `AccountLocalStore` (not guest `languages/{code}/` files):

| Screen / flow | Read | Write / notify |
|---|---|---|
| Vocabulary Library / Word Detail | Account vocab + progress + attempts | Add/edit/delete → outbox + notify |
| Quiz / StudySession | Account vocab + provisional progress | Attempts → progress outbox + notify |
| Progress / SRS / Today | Provisional + confirmed + UTC day buckets | Reading done → device-local daily_activity |
| Mistake Book | Account attempts | Practice opens account-backed quiz |
| Daily Study / Home | Account plan inputs | Sync status + conflict/import entry points |
| Reading / Listening add-word | Account vocab when signed in | `store.add` + notify |

Guest mode continues to use `vocab.json` / `progress.json` / `attempts.jsonl` with **device-local** `today_key()`.

## Accepted UTC-day semantics (signed-in)

- Account-wide day buckets, streak, signed-in `AccountProgress.today()`, and in-memory `record()` day projection use the **UTC calendar day**.
- Attempts are attributed by UTC `occurred_at` (offline Day-1 uploaded Day-3 stays on Day-1).
- ADR-022 SRS fold / `due_at` remain anchored to server `received_at` (unchanged).
- `reading_done` is **device-local** (stored in the account SQLite `daily_activity` table, not synced across devices). Its day key uses UTC only so signed-in Today() is consistent; it is not a cross-device claim.

## Supporting features

- Preferences contract v1 with base-revision optimistic concurrency + explicit Keep local/server.
- Vocabulary conflict UX including tombstone-safe `local_as_new`.
- In-flight late-ack rebase for newer local edits.
- Consent-gated guest **vocabulary** import only; guest AttemptHistory ledger import **deferred**.

## Evidence

- Facade demo: `tools/demo_18c2_signed_in_gui_sync.py`
- GUI walkthrough: `tools/gui_18c2_walkthrough.py` + `qa-evidence/phase18c2-gui-sync/`
- Tests: `tests/test_study_data_signed_in.py`, `tests/test_18c2_r1_corrections.py`, `tests/test_account_learning_sync.py`

## Production unchanged

No production `STUDY_SYNC_ENABLED=1`, no VPS activation, no Drive/OAuth as part of this closeout.
