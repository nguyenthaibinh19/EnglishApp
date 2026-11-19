# Phase 18C.2 — Signed-in GUI account sync (acceptance / demo)

**Status:** ACTIVE — Under Review (Architect R1 corrections applied; not merged, not deployed).  
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

### F1 Preferences
- Remote apply uses `from_remote=True` so settings mutators do **not** call `mark_preferences_dirty()`.
- Unsynced local dirty prefs are preserved; remote is not applied over them silently.
- Concurrent tip → deterministic `_prefs_conflict`; status is not Synced while dirty/conflict.
- Empty-server seed uses neutral defaults (not previous account machine settings).
- Unchanged clean sync does not bump server revision.

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
- **Daily activity / streak:** account day buckets from distinct attempt ids; `account_day_streak()`.
- **Conflict UX:** Keep server / Keep local / Save local as new word (tombstone case).
- **Legacy import:** consent-gated guest **vocabulary** copy only; guest files never rewritten; no auto-import on login.

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
