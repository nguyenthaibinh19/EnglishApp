# Active handoff

Rolling coordination checkpoint. See [current_state.md](../current_state.md) and [PHASE-18C.4-two-device-sync-acceptance.md](../plans/PHASE-18C.4-two-device-sync-acceptance.md).

## 1. Checkpoint metadata

- Written: 2026-11-23.
- Tag: `APP_18C4B_MACHINE_A_READY_FOR_ARCHITECT_REVIEW`.
- Source baseline: `24089334db501bacc5e87bfc1615e0dc5b5254a7`. PR #29 merge `e5763ff08097c6bb62901f6a858eda355b26f97c`.
- Active priority: **Phase 18C.4 — Real Two-Device Sync.** Machine A smoke is complete and waiting for Architect review. It is not the two-PC test.
- Application source baseline: `d6578c0f579d7ee9bd02aec855193339a7d8c124`.
- Remote main at start: `2ef0552d6cda58ff94dc02c680b2dd391b77aaef`.
- 18C.1, 18C.2, and 18C.3B remain CLOSED. The Sync Engine was not rebuilt.
- Phase 18B.10A: **AUDIT ACCEPTED, IMPLEMENTATION DEFERRED.** 18B.10B–E are **NOT AUTHORIZED.**
- Phase 18B.9: **PAUSED, NOT CLOSED.**
- Cloud Sync production: **OFF.**
- Staging deployment: **NOT STARTED.**
- Real two-PC acceptance: **NOT TESTED.**
- Sync pilot: **NO-GO.**
- RC account id 1, the 114 Dutch words, the 114 pending outbox rows, and recovery backups were not opened.

## 2. Evidence

- Lab root `D:\lg-18c4a-lab` holds `package`, `sync`, `backup`, `verify`, `proof`, and `client-a`.
- Nineteen copied modules matched their source SHA-256 before startup. The lab now keeps `package\accounts.db` and `sync\study_sync.db` for the next authorized phase.
- Machine A smoke: guard PASS, listener `127.0.0.1:18765` only, two synthetic accounts, loopback Sync API passed, client A signed in as `lab18c4_user_a` id 1 with Cloud Sync Synced. The server is stopped and port `18765` is closed. Details: [PHASE-18C.4B-machine-a-lab-smoke.md](../plans/PHASE-18C.4B-machine-a-lab-smoke.md).
- Original junction probe: **FAIL**. The corrected guard was the one used for this startup.
- `client-a` holds the synthetic staging session and bundled starter files. It is outside production, RC, recovery, and the repository.

## 3. Next

1. Architect review of the machine A smoke. Computer B still needs a separate authorization.

## 4. STOP

- Do not start the lab server again without a new authorization.
- Do not open an SSH tunnel or connect computer B.
- Do not run the two-computer scenarios.
- Do not enable production `STUDY_SYNC_ENABLED`, resume 18B.9, or implement 18B.10B–E.
