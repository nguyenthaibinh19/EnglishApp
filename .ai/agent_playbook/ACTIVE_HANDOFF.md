# Active handoff

Rolling coordination checkpoint. Product position is [current_state.md](../current_state.md). This file is coordination, not a second source of truth.

## 1. Checkpoint metadata

- Written: 2026-11-28.
- Tag: `APP_19D5A_CLOSED_SENTENCE_PRACTICE`. Phase 19.5A Sentence Practice and Grammar Companion is closed. Merge PR [#40](https://github.com/nguyenthaibinh19/EnglishApp/pull/40) at `5812be03feb507e4656c78e5c157f80f12f42a96`. Closeout tip `4b76083c5d276f19a26c590f051bad3e9bda027e`. R1 accepted checkpoint `ad169f871181a0525f0e1145ed115c200272ddb1`. Architect: `APP_19D5A_R1_ACCEPTED_FOR_CLOSEOUT`.
- Prior closed: `APP_19D4C_ARCHITECT_ACCEPTED_CLOSED` / Phase 19.4C merge PR [#38](https://github.com/nguyenthaibinh19/EnglishApp/pull/38).
- Public release remains v1.5.0. Phase 19 UI/audio/adaptive/practice/19.5A are not in that download.
- 18C.1–18C.3B remain CLOSED. 18B.10A **AUDIT ACCEPTED, IMPLEMENTATION DEFERRED.** 18B.9 **PAUSED.** Staging **NOT STARTED.**
- Taste Skill and AI Memory remain **PROPOSED — NOT AUTHORIZED FOR INSTALLATION.**

## 2. Evidence

- Phase 19.5A: [PHASE-19.5A-sentence-practice.md](../plans/PHASE-19.5A-sentence-practice.md). Activation: `LG_ADAPTIVE_STUDY=1` + isolated `LG_DATA_DIR` + `LOCK_SCREEN=0`. Demo root `D:\EnglishApp\.local\19d5a-preview`. Focused tests: `tests/test_sentence_practice.py` (**26 passed**). Adjacent adaptive suite (**40 passed**). Combined **66 passed**.
- Phase 19.4C: [PHASE-19.4C-adaptive-study-integration.md](../plans/PHASE-19.4C-adaptive-study-integration.md).

## 3. Next authorized action

1. Wait for the Phase 19.5B Structured AI Feedback and Sentence Skill Architect brief. Do not start 19.5B from this checkpoint.
2. Do not expose sentence practice or Adaptive Study on the installed Study button. Do not rebuild or publish an executable for 19.5A.
3. Do not introduce persistent SentenceSkillRecord, schema migration, Cloud Sync sentence events, or a Grammar Library browser without a new brief.
4. Do not install Taste Skill or AI Memory. Leave Phase 18 safety decisions closed.

## 4. STOP

- Do not paste secrets, session tokens, or learner records into chat.
- Do not resume 18B.9 or implement 18B.10B–E.
- Put disposable artifacts in `D:\EnglishApp\.local`. See [LOCAL_WORKSPACE_POLICY.md](../procedures/LOCAL_WORKSPACE_POLICY.md).
