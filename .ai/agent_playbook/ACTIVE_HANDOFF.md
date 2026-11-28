# Active handoff

Rolling coordination checkpoint. Product position is [current_state.md](../current_state.md). This file is coordination, not a second source of truth.

## 1. Checkpoint metadata

- Written: 2026-11-28.
- Tag: `APP_19D5B_STRUCTURED_FEEDBACK_SENTENCE_SKILL_READY_FOR_REVIEW`. Phase 19.5B Structured AI Feedback and Persistent Sentence Skill is ready for review on `phase19.5b/structured-feedback-sentence-skill` at `036bc4ee963afb06a108142dc0cfbd722e842d68`. Base main `e37fea87cedb38466d804e2294d3eb1b0a4136c7`. Architect prior closeout: `APP_19D5A_ARCHITECT_ACCEPTED_CLOSED`. Do not merge until Architect accepts.
- Prior closed: `APP_19D5A_CLOSED_SENTENCE_PRACTICE` / Phase 19.5A merge PR [#40](https://github.com/nguyenthaibinh19/EnglishApp/pull/40) at `5812be03feb507e4656c78e5c157f80f12f42a96`.
- Public release remains v1.5.0. Phase 19 UI/audio/adaptive/practice/19.5A are not in that download. 19.5B is review-branch only.
- 18C.1–18C.3B remain CLOSED. 18B.10A **AUDIT ACCEPTED, IMPLEMENTATION DEFERRED.** 18B.9 **PAUSED.** Staging **NOT STARTED.**
- Taste Skill and AI Memory remain **PROPOSED — NOT AUTHORIZED FOR INSTALLATION.**
- Ecosystem: `C-APP-AI-001` v0.2.0 unchanged. Deployed `/api/grade` unchanged. No private AI repo changes. No Reading/Listening/Vocabulary Enrichment contract changes. `LocalAIProvider` still **NOT AUTHORIZED**.

## 2. Evidence

- Phase 19.5B: [PHASE-19.5B-structured-feedback-sentence-skill.md](../plans/PHASE-19.5B-structured-feedback-sentence-skill.md). ADR: [ADR-027](../decisions/ADR-027-structured-sentence-feedback-and-skill.md).
- Activation: `LG_ADAPTIVE_STUDY=1` + isolated `LG_DATA_DIR` + `LOCK_SCREEN=0`. Demo root `D:\EnglishApp\.local\19d5b-preview`.
- Focused: `tests/test_sentence_skill_feedback.py` (**14 passed**). Adjacent: `tests/test_sentence_practice.py` (**26 passed**) + `tests/test_practice_records.py` (**8 passed**). Combined verification **48 passed**.
- Phase 19.5A: [PHASE-19.5A-sentence-practice.md](../plans/PHASE-19.5A-sentence-practice.md).

## 3. Next authorized action

1. Architect review of Phase 19.5B. Do not merge without acceptance.
2. Do not expose sentence practice or Adaptive Study on the installed Study button. Do not rebuild or publish an executable for 19.5B.
3. Do not sync SentenceSkillRecord, migrate `account_study.db`, change deployed `/api/grade`, or open a Grammar Library browser without a new brief.
4. Do not install Taste Skill or AI Memory. Leave Phase 18 safety decisions closed.

## 4. STOP

- Do not paste secrets, session tokens, or learner records into chat.
- Do not resume 18B.9 or implement 18B.10B–E.
- Put disposable artifacts in `D:\EnglishApp\.local`. See [LOCAL_WORKSPACE_POLICY.md](../procedures/LOCAL_WORKSPACE_POLICY.md).
