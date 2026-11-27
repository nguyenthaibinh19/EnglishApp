# Active handoff

Rolling coordination checkpoint. Product position is [current_state.md](../current_state.md). This file is coordination, not a second source of truth.

## 1. Checkpoint metadata

- Written: 2026-11-27.
- Tag: `APP_19D4A_UX_POLISHED_READY_FOR_REVIEW`. UX polish: `98d7bc09f44cdecaa838caa4721d504107555721`. UX parent: `0f0925616f1baac1109a4839966056732473f266`. Functional correction: `c5f17c5020d72d931b8b2f7022ecd1a57db2e96a`. Foundation parent: `5087b33f1b56d5ec47e47f4b1db19b0ed930ee7d`. Branch: `phase19.4a/adaptive-vocabulary`. Not merged. Main baseline for the branch remains `445d62c986b83393a2ba1702c7c108c52aa3f096`.
- Previous milestone: `APP_19D3_ARCHITECT_ACCEPTED_CLOSED`. Phase 19.3 remains merged at `7aedf7a423d2ef244ce37b5d3f348c7f75ed0241`.
- Accepted audio source: `3d983331c5d967c8cbe883f6881547eb4ff6ae72` on `phase19.3/multilingual-audio`.
- Phase 19.3 merge: PR #32, merge `7aedf7a423d2ef244ce37b5d3f348c7f75ed0241`. Remote main before that merge was `5f8f3c0ad175a82ad61866e23eac64af1bfe47ed` (PR #31, accepted UI `fd18a1d849d3898cdbff4bd517b22cfff1f4bdbc`).
- Public release remains v1.5.0, built from `154bf03c6856667cf1322cfe4e6f31996e05e09f`. Release checkpoint: 978 passed, 24 skipped, 0 failed. Phase 19 UI and multilingual audio are merged source and are not in that download.
- Tkinter fallback: `phase19.2a/ui-foundation-today` at `7c566027d393ae6753592b67a17c83ddb1b08c3d`. Visual trial remains `baf501351dc0b326df1a286ea64b5572bfa2f7bb`. Neither is the merged UI.
- Closed audio behavior: one local Windows provider. System.Speech is preferred. WinRT speaks the same language only when System.Speech cannot, or when that WinRT voice was explicitly saved. Voice preferences stay on the device. Normal rate is 0 and Slow rate is -4. One playback slot covers Listening, Voice Settings, Vocabulary Library, Word Detail, and Study Feedback. A missing voice uses the existing unavailable path. English, Dutch, Spanish, German, and Portuguese played on the Owner PC. French and Italian remain unavailable on that PC and are not a closeout blocker. 78 focused simulated tests passed. No cloud speech fallback, no new Python speech package, no registry edits, and no frozen-executable verification.
- 18C.1, 18C.2, and 18C.3B remain CLOSED. The Sync Engine was not rebuilt.
- Phase 18B.10A: **AUDIT ACCEPTED, IMPLEMENTATION DEFERRED.** 18B.10B–E are **NOT AUTHORIZED.**
- Phase 18B.9: **PAUSED, NOT CLOSED.** Google Drive is **NOT CONFIGURED.**
- Cloud Sync production pilot was **ON** as of 2026-11-24. That observation was not rechecked on 2026-11-27. The November 25 backup-timer elapse in the previous handoff is historical. Do not treat it as the current schedule.
- Staging deployment: **NOT STARTED.**
- `C-APP-AI-001` v0.2.0 is accepted. `LocalAIProvider` is **NOT AUTHORIZED.** The website is not deployed.
- Taste Skill and AI Memory are **PROPOSED — NOT AUDITED — NOT AUTHORIZED FOR INSTALLATION.** See [AI-TOOLCHAIN-SECURITY-AND-LOCAL-MEMORY.md](../plans/AI-TOOLCHAIN-SECURITY-AND-LOCAL-MEMORY.md).

## 2. Evidence

- Phase 19.4A plan, counters, and limits: [PHASE-19.4A-adaptive-vocabulary.md](../plans/PHASE-19.4A-adaptive-vocabulary.md). Functional R1 is accepted. The UX pass uses inline missing letters, a visual spelling prefix, choice colors, and a completion counter of finished planned words. The ladder and the SRS write boundary are unchanged. Domain tests are simulated. Five GUI tests open the real preview window.
- Phase 19.3 audible matrix and historical probes: [PHASE-19.3-multilingual-audio.md](../plans/PHASE-19.3-multilingual-audio.md). Decision: [ADR-016](../decisions/ADR-016-listening-local-tts.md).
- Earlier two-device lab evidence remains in [PHASE-18C.4-two-device-sync-acceptance.md](../plans/PHASE-18C.4-two-device-sync-acceptance.md). That evidence is separate from production.
- The full application suite after the screen-lock guard correction: **970 passed, 25 skipped, 0 failed**. The v1.5.0 release checkpoint is **978 passed, 24 skipped, 0 failed**. Details: [PHASE-18D.2A-emergency-exit-security.md](../plans/PHASE-18D.2A-emergency-exit-security.md) and [PROJECT_OVERVIEW.md](../../docs/PROJECT_OVERVIEW.md).

## 3. Next authorized action

1. Review the polished `phase19.4a/adaptive-vocabulary`. Do not merge it. The plan is [PHASE-19.4A-adaptive-vocabulary.md](../plans/PHASE-19.4A-adaptive-vocabulary.md). Do not start Grammar Companion, sentence exercises, or a practice-record schema from this handoff.
2. Do not install, build, or execute Taste Skill or AI Memory.
3. Do not rebuild or publish an executable. Do not describe Phase 19 UI or audio as publicly released.
4. Leave Phase 18 safety decisions closed. Do not resume 18B.9. Do not implement 18B.10B–E. Do not launch the protected RC database.

## 4. STOP

- Do not paste secrets, session tokens, or learner records into chat.
- Do not follow the historical LAN, SSH, or staging-lab steps in the 18C.4 acceptance plan.
- Do not disable the Sync backup timer, and do not treat a manual snapshot as the first natural timer run. The 2026-11-25 next-elapse time was not rechecked on 2026-11-27.
- Do not upload a preserved learner account.
- Do not resume 18B.9 or implement 18B.10B–E.
- Put disposable artifacts in `D:\EnglishApp\.local`. Do not create a new `D:\lg-*` directory. See [LOCAL_WORKSPACE_POLICY.md](../procedures/LOCAL_WORKSPACE_POLICY.md).
