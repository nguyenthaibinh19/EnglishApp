# Active handoff

Rolling coordination checkpoint. Product position is [current_state.md](../current_state.md). This file is coordination, not a second source of truth.

## 1. Checkpoint metadata

- Written: 2026-11-28.
- Tag: `APP_19D5A_SENTENCE_PRACTICE_CORRECTED_READY_FOR_REVIEW`. Phase 19.5A R1 corrections are on review branch `phase19.5a/sentence-practice`. Foundation checkpoint `9c8bfe14b7304ae659a982202d88e29a369802e1`. Architect: `APP_19D5A_FOUNDATION_ACCEPTED_CORRECTION_REQUIRED`. **Do not merge** until Architect/Leader acceptance.
- Prior closed: `APP_19D4C_ARCHITECT_ACCEPTED_CLOSED` / Phase 19.4C merge PR [#38](https://github.com/nguyenthaibinh19/EnglishApp/pull/38).
- Public release remains v1.5.0. Phase 19 UI/audio/adaptive/practice/19.5A are not in that download.
- 18C.1–18C.3B remain CLOSED. 18B.10A **AUDIT ACCEPTED, IMPLEMENTATION DEFERRED.** 18B.9 **PAUSED.** Staging **NOT STARTED.**
- Taste Skill and AI Memory remain **PROPOSED — NOT AUTHORIZED FOR INSTALLATION.**

## 2. Evidence

- Phase 19.5A R1: [PHASE-19.5A-sentence-practice.md](../plans/PHASE-19.5A-sentence-practice.md). Activation: `LG_ADAPTIVE_STUDY=1` + isolated `LG_DATA_DIR` + `LOCK_SCREEN=0`. Demo root `D:\EnglishApp\.local\19d5a-preview`. Focused tests: `tests/test_sentence_practice.py`. Demo: `scripts/sentence_practice_demo.py`.
- Phase 19.4C: [PHASE-19.4C-adaptive-study-integration.md](../plans/PHASE-19.4C-adaptive-study-integration.md).

## 3. Next authorized action

1. Architect/Leader review of Phase 19.5A R1 corrections. Do not merge without acceptance.
2. Do not expose sentence practice or Adaptive Study on the installed Study button. Do not rebuild or publish an executable for 19.5A.
3. Do not introduce persistent SentenceSkillRecord, schema migration, Cloud Sync sentence events, or a Grammar Library browser without a new brief.
4. Do not install Taste Skill or AI Memory. Leave Phase 18 safety decisions closed.

## 4. STOP

- Do not paste secrets, session tokens, or learner records into chat.
- Do not resume 18B.9 or implement 18B.10B–E.
- Put disposable artifacts in `D:\EnglishApp\.local`. See [LOCAL_WORKSPACE_POLICY.md](../procedures/LOCAL_WORKSPACE_POLICY.md).
