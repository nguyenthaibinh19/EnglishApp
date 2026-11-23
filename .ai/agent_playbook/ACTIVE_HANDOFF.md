# Active handoff

Rolling coordination checkpoint. See [current_state.md](../current_state.md) and [PHASE-18C.4-two-device-sync-acceptance.md](../plans/PHASE-18C.4-two-device-sync-acceptance.md).

## 1. Checkpoint metadata

- Written: 2026-11-23.
- Tag: `APP_18C4P_VOCAB_SYNC_MILESTONE_RECORDED`.
- Source baseline: `709bb78`.
- Active priority: **Phase 18C.4 — supervised production Cloud Sync.** Vocabulary A → VPS → B is **PASS — Owner confirmed**. Remaining scenarios are open.
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

- Lab root `D:\lg-18c4a-lab` holds `package`, `sync`, `backup`, `verify`, `proof`, and `client-a`.
- Nineteen copied modules matched their source SHA-256 before startup. The lab now keeps `package\accounts.db` and `sync\study_sync.db` for the next authorized phase.
- The Owner confirmed both Windows computers showed `syncprobe` / `lab-marker` for `syncpilot_18c4p`. Backup `study-sync-20261123-171338-651159.db` is mode `0600`, schema 3, integrity `ok`, and the verifier returned `VERIFIED`. Details: [PHASE-18C.4-two-device-sync-acceptance.md](../plans/PHASE-18C.4-two-device-sync-acceptance.md).
- The sync backup timer stays disabled. Production Sync stays on.
- `client-a` holds the synthetic staging session and bundled starter files. It is outside production, RC, recovery, and the repository.

## 3. Next

1. Bidirectional vocabulary updates for `syncprobe`.
2. One new attempt, then a replay that must not duplicate it. Confirm Progress and SRS on the other computer.
3. Offline change and reconnect.
4. Explicit conflict resolution.
5. A second synthetic account must not see the first account's word.
6. Quit and reopen both apps. The same word stays Synced and no new attempt appears.

## 4. STOP

- Do not paste the synthetic password into chat.
- Do not enable the sync backup timer.
- Do not upload the preserved 114-word account.
- Do not resume 18B.9 or implement 18B.10B–E.
