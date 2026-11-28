# Phase 19.4C adaptive study integration

Status: **closed / merged** (after Architect closeout corrections).  
Architect decisions: `APP_19D4B_ARCHITECT_ACCEPTED_CLOSED` → review `APP_19D4C_ADAPTIVE_STUDY_INTEGRATION_READY_FOR_REVIEW` → closeout `APP_19D4C_INTEGRATION_ACCEPTED_CLOSEOUT_CORRECTIONS_REQUIRED` → `APP_19D4C_CLOSED_ADAPTIVE_STUDY_INTEGRATION`.  
Review checkpoint: `23cdf1c9de2c1c8c756dd57ea18507fdbcb9a058`.  
Merge: PR #38, `55a1efc9b6b9d76f621b2e4f7740c3470ac77192`. Closeout commit: `327f44bb3446e96461cd155596be8676ec6d1478`.

## What this is

Wire Adaptive Vocabulary, PracticeStore, and StudyBundle into the real FreeHome → StudyMaster workflow for **explicitly opted-in isolated development sessions only**.

This is **not** a public-release change. Frozen installs and locked ScreenGuard sessions keep the legacy quiz.

## Integrated development vs released behavior

| Surface | Development (opt-in) | Released / frozen |
|---------|----------------------|-------------------|
| FreeHome **Start learning** | StudyMaster; Vocabulary → locked `VocabQuizApp` | Same |
| FreeHome **Adaptive Study (dev)** | Only when `LG_ADAPTIVE_STUDY=1` + validated isolated `LG_DATA_DIR` | Hidden |
| StudyMaster **Adaptive** | Unlocked `AdaptiveVocabularyApp` when ScreenGuard is not locking | Hidden |
| Practice records | Guest/account `practice_records.db` under the isolated root | Not written from Home |

## Activation

```powershell
$env:LG_DATA_DIR='D:\EnglishApp\.local\19d4c-preview'
$env:LG_ADAPTIVE_STUDY='1'
$env:LOCK_SCREEN='0'
& "$env:USERPROFILE\miniconda3\python.exe" -m main
# then Home → Adaptive Study (dev)
```

Demo (rewrites only that isolated root):

```powershell
& "$env:USERPROFILE\miniconda3\python.exe" -u scripts\adaptive_study_integration_demo.py
```

Source Python alone does **not** enable the route. Production AppData, protected RC, and recovery directories are refused.

## Target reconciliation

`DailyStudyPlan.planned_vocab_count` remains `min(vocab_total, QUIZ_TARGET_CORRECT)`.

Adaptive selection uses **due/new only** (no future-review fill). Unique valid vocabulary UUIDs must equal that planned N. If only 3 due/new words exist for a planned target of 10, Adaptive Study refuses, explains the limit, leaves vocabulary unresolved, and Legacy Quiz remains available. Duplicates and invalid ids do not pad the plan.

Recognition and assisted success never count toward completion. Vocabulary completion does not auto-complete Reading or Listening.

## Lifecycle

- Same account/language repeated clicks lift the existing window.
- Language changes close the previous bound vocab window.
- Bindings capture account generation, language, data root, and store handles.
- Stale callbacks after A→B→A do not complete activities or write stores.
- Independent answers without an authoritative write do not complete the session.
- Practice `unavailable` is distinct from intentionally `disabled`; failures are never reported as saved.

## Remaining production activation requirements

1. Architect-approved product decision to expose Adaptive Study on the installed Study button.
2. Authorized production practice storage (AppData allowlist, retention, deletion).
3. Frozen EXE rebuild / release packaging.
4. No PracticeRecord cloud sync until separately designed.
5. `LG_ADAPTIVE_STUDY` must not be the production activation mechanism.

## Next product priority

**Phase 19.5 Sentence Practice and Grammar Companion** — pending a separate Architect brief. Not started here.
