# Active handoff

Rolling coordination checkpoint. See [current_state.md](../current_state.md) and [PHASE-18C.4-two-device-sync-acceptance.md](../plans/PHASE-18C.4-two-device-sync-acceptance.md).

## 1. Checkpoint metadata

- Written: 2026-11-23.
- Tag: `APP_18C4P_R2_DARK_DEPLOY_READY_FOR_ARCHITECT_REVIEW`.
- Source baseline: `8760c9fbd532420005cfa268b93ef07fa1738be3`.
- Active priority: **Phase 18C.4 — direct production Cloud Sync.** The four-file dark deploy is installed. Production Sync stays off.
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
- Dark deploy: [PHASE-18C.4P-R2-dark-deploy.md](../plans/PHASE-18C.4P-R2-dark-deploy.md). Accounts snapshot `accounts-20261123-154201.db` integrity `ok`. Original modules saved under `/var/backups/language-guard/pre-18c4p-code/`.
- Service is active on Python 3.14.4. Seven sync routes return 404. `study_sync.db` is absent. Sync backup timer stays disabled. Verifier run skipped.
- `client-a` holds the synthetic staging session and bundled starter files. It is outside production, RC, recovery, and the repository.

## 3. Next

1. Architect review of the dark deploy before anyone sets `STUDY_SYNC_ENABLED=1`.
2. A release desktop build and the second Windows computer are still required before a two-client test.

## 4. STOP

- Do not set production `STUDY_SYNC_ENABLED`.
- Do not enable the sync backup timer.
- Do not launch or install the desktop candidate.
- Do not resume 18B.9 or implement 18B.10B–E.
- Do not upload the preserved 114-word account.
