# Active handoff

Rolling coordination checkpoint. See [current_state.md](../current_state.md) and [PHASE-18C.4-two-device-sync-acceptance.md](../plans/PHASE-18C.4-two-device-sync-acceptance.md).

## 1. Checkpoint metadata

- Written: 2026-11-23.
- Tag: `APP_18C4P_R1_UPGRADE_CANDIDATE_READY_FOR_ARCHITECT_REVIEW`.
- Source baseline: `3332dc5d018b1d03b49bcd372dff6dc360afcc3f`.
- Active priority: **Phase 18C.4 — direct production Cloud Sync.** The upgrade candidate is not deployed. Production Sync stays off.
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
- 18C.4P-R1 synthetic upgrade passed: schema 2 migrates to 3, accounts schema unchanged, seven routes answer only when the flag is on. Details: [PHASE-18C.4P-R1-upgrade-candidate.md](../plans/PHASE-18C.4P-R1-upgrade-candidate.md).
- Desktop candidate `D:\lg-18c4p-r1-candidate\dist\langstudyguard.exe` is not installed. The 2026-11-08 production EXE and the RC database were not modified.
- `client-a` holds the synthetic staging session and bundled starter files. It is outside production, RC, recovery, and the repository.

## 3. Next

1. Architect review of the four-file server copy before any deploy.
2. Owner connects the second Windows computer, then two synthetic clients. Do not use the real account.

## 4. STOP

- Do not deploy the four server files or set production `STUDY_SYNC_ENABLED` from this handoff.
- Do not install the desktop candidate.
- Do not resume 18B.9 or implement 18B.10B–E.
- Do not upload the preserved 114-word account.
