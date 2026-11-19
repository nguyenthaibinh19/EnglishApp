# Phase 18C.2 — Signed-in GUI account sync (acceptance / demo)

**Status:** Ready for Architect review (not merged, not deployed).  
**Baseline:** main `8e94f77491cc2f318c93fc511e258d0299ff4d03` (18C.1 CLOSED).  
**Preserve:** 18C.1 CLOSED · 18C.2 ACTIVE · 18B.9 PAUSED, NOT CLOSED · Cloud Sync production OFF.

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

## Supporting account-data features

- **Preferences (contract v1):** `study_languages`, `reading_level`, `native`, `activities` via `/api/sync/preferences/{get,put}` stored in server `sync_meta` (no schema bump). Machine paths, ScreenGuard, TTS, Startup stay local.
- **Daily activity / streak:** `account_day_buckets` from distinct attempt `vocab_id`s per UTC day; `AccountProgress.account_day_streak()`. Does not sum guest `progress.json`.
- **Conflict UX:** `sync_conflict_app` lists local vs server versions; explicit Keep local / Keep server; blocked until resolved (`OUTBOX_CONFLICT`).
- **Legacy import:** `legacy_import_app` preview + checkbox consent; vocabulary copy only; guest files never rewritten; no auto-import on login. Full ADR-022 attempt-history ledger import remains deferred (documented in UI).
- **Reliability (engine reuse from 18C.1):** in-flight coalesce, lost-ack idempotent pull, offline catch-up, pending outbox, logout/`clear_account` stops engine, account switch replaces engine/store.

## Demo evidence

- Script: `tools/demo_18c2_signed_in_gui_sync.py`
- Evidence: `qa-evidence/phase18c2-gui-sync/` (`demo_18c2_results.json`, `DEMO_CHECKLIST.md`)
- Exercises the same `open_study_data()` facade as the wired Tkinter screens with two device roots + account B isolation.

## Tests

- `tests/test_study_data_signed_in.py` (signed-in vs guest, consent import, prefs contract, day buckets)
- Existing `tests/test_account_learning_sync.py` (18C.1 conflict/lost-ack regressions) still green

## Explicitly not done / limitations

- Full ADR-022 guest attempt JSONL ledger + overlap preflight import (vocab consent import only in 18C.2).
- Interactive on-screen screenshot capture of two live Windows profiles is not attached; demo proves the GUI data facade + sync with isolated roots. Manual PO walkthrough uses StudyMaster sync row + Vocabulary/Quiz screens on staging.
- Production `STUDY_SYNC_ENABLED=1` remains unset; VPS unchanged.
- Preferences LWW uses revision; concurrent pref edits may require a follow-up sync cycle after 409.

## Production unchanged

No VPS/SSH, no production DB, no production flag, no Drive/OAuth, no merge/deploy in this milestone.
