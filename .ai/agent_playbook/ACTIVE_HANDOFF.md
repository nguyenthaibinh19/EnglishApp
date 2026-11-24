# Active handoff

Rolling coordination checkpoint. See [current_state.md](../current_state.md) and [PHASE-18C.4-two-device-sync-acceptance.md](../plans/PHASE-18C.4-two-device-sync-acceptance.md).

## 1. Checkpoint metadata

- Written: 2026-11-24.
- Tag: `APP_18C4P_R5_PROGRESS_SYNC_READY_FOR_ARCHITECT_REVIEW`.
- Source baseline: `60b967d98917edfa7014aba2f5a72f8855385394`.
- Active priority: **Same-machine R5 is ready for review.** Bidirectional vocabulary and one learning attempt passed on this computer. Conflict, offline, and production replay remain open.
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

- Shared source: `D:\EnglishApp\.local\clients\18c4p-r3`. Client A data: `.local\data\18c4p-r3`. Client B data: `.local\data\18c4p-r3-b`. Launcher: `.local\labs\18c4p-r3\launch_client.py`.
- Both clients are `syncpilot_18c4p`, user id 3, with distinct device ids and separate data roots. `syncprobe` is revision 4, meaning `lab-marker-a`, on both clients and the server. One exact attempt is acked on both, with matching SRS. Details: [PHASE-18C.4P-R5-progress-sync.md](../plans/PHASE-18C.4P-R5-progress-sync.md).
- Localhost idempotent replay passed again and stays a separate category from the production result.

## 3. Next

1. Architect reviews the same-machine vocabulary and progress result.
2. Leave the open Client B quiz unanswered. A second submission would be a new event.

## 4. STOP

- Do not paste the synthetic password into chat.
- Do not follow the historical LAN, SSH, or staging-lab steps in the 18C.4 acceptance plan.
- Do not enable the sync backup timer.
- Do not upload the preserved 114-word account.
- Do not resume 18B.9 or implement 18B.10B–E.
- Put disposable artifacts in `D:\EnglishApp\.local`. Do not create a new `D:\lg-*` directory. See [LOCAL_WORKSPACE_POLICY.md](../procedures/LOCAL_WORKSPACE_POLICY.md).
