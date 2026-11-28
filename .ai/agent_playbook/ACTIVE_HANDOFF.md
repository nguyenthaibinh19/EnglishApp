# Active handoff

Rolling coordination checkpoint. Product position is [current_state.md](../current_state.md). This file is coordination, not a second source of truth.

## 1. Checkpoint metadata

- Written: 2026-11-28.
- Tag: `APP_19D5B_CLOSED_STRUCTURED_FEEDBACK_SENTENCE_SKILL`. Phase 19.5B Structured AI Feedback and Persistent Sentence Skill is closed. Merge PR [#41](https://github.com/nguyenthaibinh19/EnglishApp/pull/41) at `98cf2191a9ebbb0d6f513c14cbaedf898fefdd48`. ADR-027 Accepted. Merged, unreleased development functionality.
- Prior closed: `APP_19D5A_CLOSED_SENTENCE_PRACTICE` / Phase 19.5A merge PR [#40](https://github.com/nguyenthaibinh19/EnglishApp/pull/40).
- Public release remains v1.5.0. Phase 19 UI/audio/adaptive/practice/19.5A/19.5B are not in that download.
- 18C.1–18C.3B remain CLOSED. 18B.10A **AUDIT ACCEPTED, IMPLEMENTATION DEFERRED.** 18B.9 **PAUSED.** Staging **NOT STARTED.**
- Taste Skill and AI Memory remain **PROPOSED — NOT AUTHORIZED FOR INSTALLATION.**
- Ecosystem: `C-APP-AI-001` v0.2.0 unchanged. Deployed `/api/grade` unchanged. No private AI repo changes. `LocalAIProvider` still **NOT AUTHORIZED**.

## 2. Evidence

- Phase 19.5B: [PHASE-19.5B-structured-feedback-sentence-skill.md](../plans/PHASE-19.5B-structured-feedback-sentence-skill.md). ADR: [ADR-027](../decisions/ADR-027-structured-sentence-feedback-and-skill.md).
- Activation: `LG_ADAPTIVE_STUDY=1` + isolated `LG_DATA_DIR` + `LOCK_SCREEN=0`. Demo root `D:\EnglishApp\.local\19d5b-preview`.
- Closeout verification **88 passed** (closeout 10 + feedback 14 + practice 26 + practice_records 8 + adaptive_integration 12 + adaptive_vocabulary 18).
- Phase 19.5A: [PHASE-19.5A-sentence-practice.md](../plans/PHASE-19.5A-sentence-practice.md).

## 3. Next authorized action

1. Wait for the Phase 19.6 Library, Progress and Settings Architect brief. Do not start 19.6 from this checkpoint.
2. Do not expose sentence practice or Adaptive Study on the installed Study button. Do not rebuild or publish an executable for 19.5B.
3. Do not sync SentenceSkillRecord, migrate `account_study.db`, change deployed `/api/grade`, or open a Grammar Library browser without a new brief.
4. Do not install Taste Skill or AI Memory. Leave Phase 18 safety decisions closed.

## 4. STOP

- Do not paste secrets, session tokens, or learner records into chat.
- Do not resume 18B.9 or implement 18B.10B–E.
- Put disposable artifacts in `D:\EnglishApp\.local`. See [LOCAL_WORKSPACE_POLICY.md](../procedures/LOCAL_WORKSPACE_POLICY.md).
