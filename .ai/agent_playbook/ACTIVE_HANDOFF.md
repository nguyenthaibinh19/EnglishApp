# Active handoff

Rolling coordination checkpoint. See [current_state.md](../current_state.md) and [PHASE-18C.4-two-device-sync-acceptance.md](../plans/PHASE-18C.4-two-device-sync-acceptance.md).

## 1. Checkpoint metadata

- Written: 2026-11-23.
- Tag: `APP_18C4P_BLOCKED`.
- Source baseline: `7d21019ed970e54b6040857d61d145a06ec4a2f2`.
- Active priority: **Phase 18C.4 — direct production Cloud Sync pilot.** The LAN/SSH plan is no longer the path. Production Sync was not enabled.
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
- 18C.4P inspection: production listener `127.0.0.1:8765`, flag unset, sync route 404, schema 2, three vocabulary routes, `srs.py` absent. Accounts backup from 2026-11-23 integrity `ok`. No code or flag change. Details: [PHASE-18C.4P-production-pilot.md](../plans/PHASE-18C.4P-production-pilot.md).
- Production EXE dated 2026-11-08 does not contain the sync route strings. Source staging clients refuse the production host.
- `client-a` holds the synthetic staging session and bundled starter files. It is outside production, RC, recovery, and the repository.

## 3. Next

1. Architect review of the allowlisted production sync update before any deploy.
2. A production desktop build that contains Account Sync, then two physical computers and a new synthetic production account.

## 4. STOP

- Do not deploy the allowlisted sync modules or set production `STUDY_SYNC_ENABLED` from this handoff.
- Do not resume 18B.9 or implement 18B.10B–E.
- Do not upload the preserved 114-word account.
