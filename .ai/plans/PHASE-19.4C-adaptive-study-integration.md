# Phase 19.4C adaptive study integration

Status: **ready for review** on `phase19.4c/adaptive-study-integration`.  
Architect decision for prior close: `APP_19D4B_ARCHITECT_ACCEPTED_CLOSED`.  
Baseline: `d223413dc558c46699ae565d946cfe4485fe4583`.

## What this is

Wire Adaptive Vocabulary, PracticeStore, and StudyBundle into the real FreeHome → StudyMaster workflow for **unlocked development / synthetic sessions only**.

This is **not** a public-release change. Frozen installs and locked ScreenGuard sessions keep the legacy quiz.

## Integrated development behavior

| Surface | Behavior |
|---------|----------|
| FreeHome **Start learning** | Unchanged StudyMaster entry. Required Vocabulary button opens locked `VocabQuizApp`. |
| FreeHome **Adaptive Study (dev)** | Visible only when `adaptive_integration_enabled()` (source, not frozen). Opens `StudyMasterApp(prefer_adaptive=True)` and routes to unlocked `AdaptiveVocabularyApp`. |
| StudyMaster **Vocabulary** | Required locked route preserved: `open_vocab_section` → `VocabQuizApp(locked=True)`. |
| StudyMaster **Adaptive** | Shown only when ScreenGuard is not locking. Opens `open_adaptive_vocab_section`. |
| Installed / frozen EXE | No Adaptive Study button. Study stays on legacy quiz. |

## Target reconciliation

`DailyStudyPlan.planned_vocab_count` remains `min(vocab_total, QUIZ_TARGET_CORRECT)` — the same N the locked legacy session uses.

Adaptive completion requires independent exact/near success on up to N **distinct** planned words. Recognition and assisted success do not count. That is a stricter unique-word rule for the same planned count, not a reduced target.

Vocabulary completion does not auto-complete Reading or Listening. Existing StudySession orchestration and Home refresh stay in place.

## Data paths

- Guest: language files under `LG_DATA_DIR` / `languages/<code>/` plus guest `practice_records.db`.
- Signed-in: `StudyBundle` → `AccountAttemptHistory.record` / provisional `AccountProgress`; account `practice_records.db` under `accounts/<user_id>/`.
- Practice rows: zero learning attempts, zero SRS reviews, zero sync-outbox events.
- Independent recall: exactly one authoritative attempt + expected progress event.
- PracticeStore refuses production AppData, protected RC, and recovery directories (ADR-026).
- Integrated app does **not** use the 19.4B standalone preview database path as its store.

## Account / language lifecycle

- Each adaptive window captures `AdaptiveStudyIdentity` (account, language, data root, binding id).
- Late writes and completion callbacks no-op when `still_current()` is false.
- Account switch closes account-bound windows, bumps `_account_generation`, and rebuilds StudySession flags (no completed flags carried across identities).
- Language activate closes an open vocab child before rebinding stores.
- Duplicate Home clicks lift the existing adaptive window.

## Production practice storage (future)

`production_practice_storage_requirements()` documents what a future release would need before writing practice rows under production AppData. No production AppData activation in this phase.

## Demo

Isolated root: `D:\EnglishApp\.local\19d4c-preview`

```powershell
$env:LG_DATA_DIR='D:\EnglishApp\.local\19d4c-preview'
$env:LOCK_SCREEN='0'
$env:QUIZ_TARGET_CORRECT='2'
& "$env:USERPROFILE\miniconda3\python.exe" -u scripts\adaptive_study_integration_demo.py
```

Interactive (same env):

```powershell
& "$env:USERPROFILE\miniconda3\python.exe" -m main
```

Then Home → **Adaptive Study (dev)**.

Evidence: `integration-evidence.json`, screenshots under `screenshots/`.

## Focused tests

```powershell
& "$env:USERPROFILE\miniconda3\python.exe" -m pytest tests/test_adaptive_study_integration.py -q
```

## Remaining production-readiness requirements

1. Architect acceptance of this integration review branch (do not merge until accepted).
2. Explicit product decision to expose Adaptive Study on the installed Study button.
3. Authorized production practice storage (see requirements helper) — retention, deletion, AppData allowlist.
4. Frozen EXE rebuild / release packaging (out of scope here).
5. No Cloud Sync protocol for PracticeRecord until separately designed.
6. Sentence Practice / Grammar Companion remain unauthorized.

## Out of scope (unchanged)

No production host/token/account. No adaptive locked-session activation. No account_study.db schema change. No new SRS formula. No Home redesign. No EXE rebuild.
