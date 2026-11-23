# Active handoff

Rolling coordination checkpoint. See [current_state.md](../current_state.md) and [PHASE-18C.4-two-device-sync-acceptance.md](../plans/PHASE-18C.4-two-device-sync-acceptance.md).

## 1. Checkpoint metadata

- Written: 2026-11-23.
- Tag: `APP_18C4P_R1_FINAL_DEPLOYMENT_PACKAGE_READY_FOR_REVIEW`.
- Source baseline: `1ffb7cb4047ca40167446d4f878b13af8585f68b`.
- Active priority: **Phase 18C.4 — direct production Cloud Sync.** The four-file package is not deployed. Production Sync stays off.
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
- Final package: [PHASE-18C.4P-R1-final-deployment-package.md](../plans/PHASE-18C.4P-R1-final-deployment-package.md). Accounts timer stays enabled. Sync backup timer stays disabled. Verifier timer stays enabled and skips while `study_sync.db` is absent.
- Desktop candidate SHA matches and was not launched. Installed EXE and Startup shortcut are present, so this production build cannot run in place.
- `client-a` holds the synthetic staging session and bundled starter files. It is outside production, RC, recovery, and the repository.

## 3. Next

1. Architect review of the four LF hashes before any copy.
2. A release build with the owner emergency password, on a machine where in-place execution does not meet the installed production EXE. Then connect the second computer.

## 4. STOP

- Do not deploy the four files, enable the sync backup timer, or set `STUDY_SYNC_ENABLED`.
- Do not launch or install the desktop candidate.
- Do not resume 18B.9 or implement 18B.10B–E.
- Do not upload the preserved 114-word account.
