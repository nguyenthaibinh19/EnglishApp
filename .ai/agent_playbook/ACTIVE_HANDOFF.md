# Active handoff

Rolling coordination checkpoint. Product position is [current_state.md](../current_state.md). This file is coordination, not a second source of truth.

## 1. Checkpoint metadata

- Written: 2026-11-28.
- Tag: `APP_19D4C_CLOSED_ADAPTIVE_STUDY_INTEGRATION`. Phase 19.4C Adaptive Study Integration is closed and merged. Review checkpoint was `23cdf1c9de2c1c8c756dd57ea18507fdbcb9a058`. Closeout corrections landed on `phase19.4c/adaptive-study-integration` before merge.
- Prior: `APP_19D4B_ARCHITECT_ACCEPTED_CLOSED` / PR #36. ADR-026 is Accepted. Phase 19.4A remains closed (PR #34). Phase 19.3 remains merged at `7aedf7a423d2ef244ce37b5d3f348c7f75ed0241`.
- Public release remains v1.5.0 (`154bf03c6856667cf1322cfe4e6f31996e05e09f`). Phase 19 UI/audio/adaptive/practice/19.4C are not in that download.
- 18C.1–18C.3B remain CLOSED. 18B.10A **AUDIT ACCEPTED, IMPLEMENTATION DEFERRED.** 18B.9 **PAUSED.** Staging **NOT STARTED.**
- Taste Skill and AI Memory remain **PROPOSED — NOT AUTHORIZED FOR INSTALLATION.**

## 2. Evidence

- Phase 19.4C: [PHASE-19.4C-adaptive-study-integration.md](../plans/PHASE-19.4C-adaptive-study-integration.md). Activation: `LG_ADAPTIVE_STUDY=1` + isolated `LG_DATA_DIR` + `LOCK_SCREEN=0`. Demo root `D:\EnglishApp\.local\19d4c-preview`. Focused tests: `tests/test_adaptive_study_integration.py`.
- Phase 19.4B: [PHASE-19.4B-practice-records.md](../plans/PHASE-19.4B-practice-records.md), [ADR-026](../decisions/ADR-026-practice-records.md).
- Phase 19.4A: [PHASE-19.4A-adaptive-vocabulary.md](../plans/PHASE-19.4A-adaptive-vocabulary.md).

## 3. Next authorized action

1. Wait for the Phase 19.5 Sentence Practice and Grammar Companion Architect brief. Do not start sentence/grammar work from this checkpoint.
2. Do not expose Adaptive Study on the installed Study button. Do not rebuild or publish an executable for 19.4C.
3. Do not install Taste Skill or AI Memory. Leave Phase 18 safety decisions closed.

## 4. STOP

- Do not paste secrets, session tokens, or learner records into chat.
- Do not resume 18B.9 or implement 18B.10B–E.
- Put disposable artifacts in `D:\EnglishApp\.local`. See [LOCAL_WORKSPACE_POLICY.md](../procedures/LOCAL_WORKSPACE_POLICY.md).
