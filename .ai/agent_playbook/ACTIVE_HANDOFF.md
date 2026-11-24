# Active handoff

Rolling coordination checkpoint. See [current_state.md](../current_state.md) and [PHASE-18C.4-two-device-sync-acceptance.md](../plans/PHASE-18C.4-two-device-sync-acceptance.md).

## 1. Checkpoint metadata

- Written: 2026-11-24.
- Tag: `APP_LOCAL_MULTI_CLIENT_READY`.
- Source baseline: `f42bdd5`.
- Active priority: **Same-machine production clients are ready.** Client B still needs one private sign-in before the R5 GUI scenarios.
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
- Client B has no settings and no account database. A throwaway pair of stores produced two different `device_id` values. Client B's real id is created on first open after sign-in.
- `tests/test_account_ux_two_device.py` and the idempotent progress retry passed against localhost. That is not a production result. Details: [LOCAL_WORKSPACE_POLICY.md](../procedures/LOCAL_WORKSPACE_POLICY.md).

## 3. Next

1. On the right-hand Client B window, add Dutch as a study language and continue.
2. Sign in there as `syncpilot_18c4p`. Type the password only in that window.
3. Then edit `syncprobe` on B, then on A, and submit one quiz answer on B.

## 4. STOP

- Do not paste the synthetic password into chat.
- Do not follow the historical LAN, SSH, or staging-lab steps in the 18C.4 acceptance plan.
- Do not enable the sync backup timer.
- Do not upload the preserved 114-word account.
- Do not resume 18B.9 or implement 18B.10B–E.
- Put disposable artifacts in `D:\EnglishApp\.local`. Do not create a new `D:\lg-*` directory. See [LOCAL_WORKSPACE_POLICY.md](../procedures/LOCAL_WORKSPACE_POLICY.md).
