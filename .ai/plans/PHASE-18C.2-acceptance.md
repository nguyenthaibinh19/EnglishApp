# Phase 18C.2 — Signed-in GUI account sync (acceptance / demo)

**Status:** ACTIVE — Under Review (final data-correctness corrections applied; not merged, not deployed).  
**Baseline:** main `8e94f77491cc2f318c93fc511e258d0299ff4d03` (18C.1 CLOSED).  
**Preserve:** 18C.1 CLOSED — Architect Accepted · 18C.2 ACTIVE — Under Review · 18B.9 PAUSED, NOT CLOSED · Cloud Sync production OFF.

## Implemented (actual GUI data path)

When a session token and `account_user_id` are present, these Tkinter flows use `study_data.open_study_data()` → `AccountLocalStore` (not guest `languages/{code}/` files):

| Screen / flow | Read | Write / notify |
|---|---|---|
| Vocabulary Library / Word Detail (`vocabulary_app`, `vocabulary_library`) | Account vocab + progress + attempts | Add/edit/delete → outbox + `notify_local_change` |
| Quiz / StudySession (`quiz_app` → `QuizEngine`) | Account vocab + provisional progress | Attempts → progress outbox + notify |
| Progress / SRS (`learning_progress`, `AccountProgress`) | Provisional + confirmed + day buckets | Reading done → local daily_activity |
| Mistake Book (`mistake_book`, `mistake_book_app`) | Account attempts | Practice opens account-backed quiz |
| Daily Study / Home (`daily_study`, `main.StudyMasterApp`) | Account plan inputs | Sync status + conflict/import entry points |
| Reading / Listening add-word | Account vocab when signed in | `store.add` + notify |

Guest mode continues to use `vocab.json` / `progress.json` / `attempts.jsonl`.

## Architect R1 corrections

### F1 Preferences (optimistic concurrency)
- Local edits lock `_prefs_base_revision` to the last accepted server tip.
- Sync compares the live remote tip to that base. If the tip moved, local dirty values are preserved and a persistent `_prefs_conflict` is set — **no auto-PUT against the new tip**.
- Unresolved conflicts survive retry cycles until explicit `resolve_preferences_conflict(keep=local|server)` (StudyMaster “Preference conflict” dialog).
- Remote apply uses `from_remote=True` (no dirty loop). Empty-server seed uses neutral defaults (no account-A→B leakage). Clean sync does not bump revision.

### F2 Tombstones
- `keep=server` preserves remote deletion.
- `keep=local` against a tombstone is rejected (no resurrection upload).
- `keep=local_as_new` saves frozen local PUT body under a **new UUID**; original tombstone and history remain.

### F3 In-flight race
- Late HTTP acceptance of superseded OpX calls `note_accepted_vocab_upload`, rebases pending Y, does not invent a false conflict, and does not drop Y.
- Deterministic delayed-HTTP regression in `tests/test_18c2_r1_corrections.py`.

### F4 Real GUI
- `tools/gui_18c2_walkthrough.py` launches real `VocabularyLibraryApp`, `VocabQuizApp`, `MistakeBookApp`, `ProgressApp` on two isolated profiles.
- Evidence: `qa-evidence/phase18c2-gui-sync/gui-walkthrough/` (PNG + `WALKTHROUGH_REPORT.json`).

## Supporting account-data features

- **Preferences (contract v1):** `study_languages`, `reading_level`, `native`, `activities` via `/api/sync/preferences/{get,put}` in server `sync_meta` (no schema bump).
- **Daily activity / streak (UTC `occurred_at`):** Account-wide buckets and streak use the UTC calendar day of each attempt’s `occurred_at` (device study time). Offline Day-1 answers uploaded on Day-3 stay on Day-1. `received_at` is not used for activity bucketing. Event ids are counted once. ADR-022 SRS / `due_at` remain anchored to server `received_at`. `reading_done` in `daily_activity` is **device-local** and is not claimed as cross-device sync. Clock-skewed `occurred_at` is trusted for activity display only.
- **Conflict UX:** Vocabulary Keep server / Keep local / Save local as new word; preferences Keep local / Keep server.
- **Legacy import:** consent-gated guest **vocabulary** copy only; guest files never rewritten; no auto-import on login. Guest AttemptHistory ledger import remains deferred.

## Demo evidence

- Facade demo: `tools/demo_18c2_signed_in_gui_sync.py` → `APP_18C2_DEMO_OK`
- GUI walkthrough: `tools/gui_18c2_walkthrough.py` → `APP_18C2_GUI_WALKTHROUGH_OK`
- Evidence roots: `qa-evidence/phase18c2-gui-sync/`

## Tests

- `tests/test_18c2_r1_corrections.py` (F1/F2/F3)
- `tests/test_study_data_signed_in.py`
- `tests/test_account_learning_sync.py` (18C.1 regressions)

## Outstanding ADR-022 limitations (not claimed complete)

- Full guest **AttemptHistory** consent/overlap ledger import (JSONL identity + high-water + replacement preflight) remains deferred.
- Vocab-only legacy import with explicit consent is implemented; do not mark full ADR-022 completion.

## Production unchanged

No VPS/SSH, no production DB, no production flag, no Drive/OAuth, no merge/deploy in this milestone.
