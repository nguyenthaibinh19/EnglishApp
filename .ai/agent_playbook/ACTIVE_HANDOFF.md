# Active handoff

Rolling coordination checkpoint. See [current_state.md](../current_state.md) and [PHASE-18C.4-two-device-sync-acceptance.md](../plans/PHASE-18C.4-two-device-sync-acceptance.md).

## 1. Checkpoint metadata

- Written: 2026-11-24.
- Tag: `APP_18C4P_R5_BLOCKED_OWNER_GUI`.
- Source baseline: `39fc564ea8867fb7a76bb474d8abcce5eb6bcbe9`.
- Active priority: **Phase 18C.4P-R5.** Vocabulary A → VPS → B remains **PASS — Owner confirmed**. Bidirectional edits, attempts, and replay are waiting on the Owner.
- Application source baseline: `d6578c0f579d7ee9bd02aec855193339a7d8c124`.
- Remote main at start: `2ef0552d6cda58ff94dc02c680b2dd391b77aaef`.
- 18C.1, 18C.2, and 18C.3B remain CLOSED. The Sync Engine was not rebuilt.
- Phase 18B.10A: **AUDIT ACCEPTED, IMPLEMENTATION DEFERRED.** 18B.10B–E are **NOT AUTHORIZED.**
- Phase 18B.9: **PAUSED, NOT CLOSED.**
- Cloud Sync production: **ON**, supervised pilot. The verifier service completed `VERIFIED`.
- Staging deployment: **NOT STARTED.**
- Real two-PC vocabulary A → VPS → B: **PASS — Owner confirmed**. No separate Machine B log is stored. Scenarios 2a, 2b, 3, 4, 5, and 6 are open.
- Sync pilot: vocabulary milestone recorded. Full acceptance is not complete.
- RC account id 1, the 114 Dutch words, the 114 pending outbox rows, and recovery backups were not opened.

## 2. Evidence

- Machine A client: `D:\EnglishApp\.local\clients\18c4p-r3`. Data: `D:\EnglishApp\.local\data\18c4p-r3`. The old lab is archival at `D:\EnglishApp\.local\labs\18c4a`.
- Baseline: `syncprobe` revision 1, meaning `lab-marker`, 0 attempts, 0 progress rows, 0 conflicts. Details: [PHASE-18C.4P-R5-progress-sync.md](../plans/PHASE-18C.4P-R5-progress-sync.md).
- The sync backup timer stays disabled. Production Sync stays on. The post-test backup waits until the Owner finishes the GUI scenarios.

## 3. Next

1. Owner edits `syncprobe` on B to `lab-marker-b`, then on A to `lab-marker-a`, and reports both Synced states.
2. Owner submits exactly one quiz answer on B. Replay stays unverified until that accepted event exists.

## 4. STOP

- Do not paste the synthetic password into chat.
- Do not follow the historical LAN, SSH, or staging-lab steps in the 18C.4 acceptance plan.
- Do not enable the sync backup timer.
- Do not upload the preserved 114-word account.
- Do not resume 18B.9 or implement 18B.10B–E.
- Put disposable artifacts in `D:\EnglishApp\.local`. Do not create a new `D:\lg-*` directory. See [LOCAL_WORKSPACE_POLICY.md](../procedures/LOCAL_WORKSPACE_POLICY.md).
