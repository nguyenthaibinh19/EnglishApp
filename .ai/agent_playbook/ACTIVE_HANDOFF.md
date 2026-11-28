# Active handoff

Rolling coordination checkpoint. Product position is [current_state.md](../current_state.md). This file is coordination, not a second source of truth.

## 1. Checkpoint metadata

- Written: 2026-11-28.
- Tag: `APP_19D4C_ADAPTIVE_STUDY_INTEGRATION_READY_FOR_REVIEW`. Branch: `phase19.4c/adaptive-study-integration`. Baseline: `d223413dc558c46699ae565d946cfe4485fe4583`. Not merged.
- Prior close: `APP_19D4B_ARCHITECT_ACCEPTED_CLOSED`. Phase 19.4B merge: PR #36, `91d3c60f59c5d26d321433a9334c6af31e09c1a5`. ADR-026 is Accepted.
- Phase 19.4A remains closed. Tag `APP_19D4A_CLOSED_ADAPTIVE_VOCABULARY`. Merge PR #34, `e33373110544a1ca4fca6905b8741d47e4932fc4`.
- Previous milestone: `APP_19D3_ARCHITECT_ACCEPTED_CLOSED`. Phase 19.3 remains merged at `7aedf7a423d2ef244ce37b5d3f348c7f75ed0241`.
- Public release remains v1.5.0, built from `154bf03c6856667cf1322cfe4e6f31996e05e09f`. Phase 19 UI, audio, adaptive vocabulary, practice records, and this 19.4C review branch are not in that download.
- 18C.1, 18C.2, and 18C.3B remain CLOSED. The Sync Engine was not rebuilt.
- Phase 18B.10A: **AUDIT ACCEPTED, IMPLEMENTATION DEFERRED.** 18B.10B–E are **NOT AUTHORIZED.**
- Phase 18B.9: **PAUSED, NOT CLOSED.** Google Drive is **NOT CONFIGURED.**
- Staging deployment: **NOT STARTED.**
- `C-APP-AI-001` v0.2.0 is accepted. `LocalAIProvider` is **NOT AUTHORIZED.** The website is not deployed.
- Taste Skill and AI Memory are **PROPOSED — NOT AUDITED — NOT AUTHORIZED FOR INSTALLATION.** See [AI-TOOLCHAIN-SECURITY-AND-LOCAL-MEMORY.md](../plans/AI-TOOLCHAIN-SECURITY-AND-LOCAL-MEMORY.md).

## 2. Evidence

- Phase 19.4C plan: [PHASE-19.4C-adaptive-study-integration.md](../plans/PHASE-19.4C-adaptive-study-integration.md). FreeHome **Adaptive Study (dev)** → StudyMaster unlocked Adaptive Vocabulary. Locked Vocabulary route preserved. Demo root `D:\EnglishApp\.local\19d4c-preview`. Evidence `integration-evidence.json`. Screenshots under `screenshots/`. Focused tests: `tests/test_adaptive_study_integration.py` (12 passed) plus practice/adaptive regressions.
- Phase 19.4B plan and contract: [PHASE-19.4B-practice-records.md](../plans/PHASE-19.4B-practice-records.md) and [ADR-026](../decisions/ADR-026-practice-records.md).
- Phase 19.4A plan: [PHASE-19.4A-adaptive-vocabulary.md](../plans/PHASE-19.4A-adaptive-vocabulary.md).
- Phase 19.3 audible matrix: [PHASE-19.3-multilingual-audio.md](../plans/PHASE-19.3-multilingual-audio.md). Decision: [ADR-016](../decisions/ADR-016-listening-local-tts.md).

## 3. Next authorized action

1. Architect review of Phase 19.4C. Do not merge until accepted. Do not start Grammar Companion or sentence exercises. Do not replace the legacy quiz on the installed Study button.
2. Do not install, build, or execute Taste Skill or AI Memory.
3. Do not rebuild or publish an executable. Do not describe Phase 19 UI, audio, adaptive vocabulary, practice records, or 19.4C as part of the installed v1.5.0 release.
4. Leave Phase 18 safety decisions closed. Do not resume 18B.9. Do not implement 18B.10B–E. Do not launch the protected RC database.

## 4. STOP

- Do not paste secrets, session tokens, or learner records into chat.
- Do not follow the historical LAN, SSH, or staging-lab steps in the 18C.4 acceptance plan.
- Do not disable the Sync backup timer, and do not treat a manual snapshot as the first natural timer run.
- Do not upload a preserved learner account.
- Do not resume 18B.9 or implement 18B.10B–E.
- Put disposable artifacts in `D:\EnglishApp\.local`. Do not create a new `D:\lg-*` directory. See [LOCAL_WORKSPACE_POLICY.md](../procedures/LOCAL_WORKSPACE_POLICY.md).
