# Active handoff

Rolling coordination checkpoint. See [current_state.md](../current_state.md) and [PHASE-18C.4-two-device-sync-acceptance.md](../plans/PHASE-18C.4-two-device-sync-acceptance.md).

## 1. Checkpoint metadata

- Written: 2026-11-23.
- Tag: `APP_18C4P_R4B_VERIFIER_AND_PERMISSIONS_PASS`.
- Source baseline: `8a2a2f1d0c8e8697630a632407c17696af05f3ad`.
- Active priority: **Phase 18C.4 — supervised production Cloud Sync.** Verifier and live database permissions passed. Machine B is still open.
- Application source baseline: `d6578c0f579d7ee9bd02aec855193339a7d8c124`.
- Remote main at start: `2ef0552d6cda58ff94dc02c680b2dd391b77aaef`.
- 18C.1, 18C.2, and 18C.3B remain CLOSED. The Sync Engine was not rebuilt.
- Phase 18B.10A: **AUDIT ACCEPTED, IMPLEMENTATION DEFERRED.** 18B.10B–E are **NOT AUTHORIZED.**
- Phase 18B.9: **PAUSED, NOT CLOSED.**
- Cloud Sync production: **ON**, supervised pilot. The verifier service completed `VERIFIED`.
- Staging deployment: **NOT STARTED.**
- Real two-PC acceptance: **NOT TESTED.**
- Sync pilot: **NO-GO.**
- RC account id 1, the 114 Dutch words, the 114 pending outbox rows, and recovery backups were not opened.

## 2. Evidence

- Lab root `D:\lg-18c4a-lab` holds `package`, `sync`, `backup`, `verify`, `proof`, and `client-a`.
- Nineteen copied modules matched their source SHA-256 before startup. The lab now keeps `package\accounts.db` and `sync\study_sync.db` for the next authorized phase.
- Sync is on. The verifier drop-in runs as `guard`, hides account backups, and bind-mounts only the sync backup read-only. The service result is `VERIFIED`. `study_sync.db` is mode `0600` and the account service umask is `0077`. Details: [PHASE-18C.4P-R4-sync-activation.md](../plans/PHASE-18C.4P-R4-sync-activation.md).
- The sync backup timer stays disabled. Machine B is **UNVERIFIED**.
- `client-a` holds the synthetic staging session and bundled starter files. It is outside production, RC, recovery, and the repository.

## 3. Next

1. Machine B repeats the R3 client, signs in as `syncpilot_18c4p`, and waits 90 seconds for `syncprobe` / `lab-marker`.

## 4. STOP

- Do not paste the synthetic password into chat.
- Do not enable the sync backup timer.
- Do not upload the preserved 114-word account.
- Do not resume 18B.9 or implement 18B.10B–E.
