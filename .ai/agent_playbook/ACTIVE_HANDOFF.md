# Active handoff

Rolling coordination checkpoint. See [current_state.md](../current_state.md) and [PHASE-18C.4-two-device-sync-acceptance.md](../plans/PHASE-18C.4-two-device-sync-acceptance.md).

## 1. Checkpoint metadata

- Written: 2026-11-23.
- Tag: `APP_18C4_READY_FOR_ARCHITECT_REVIEW`.
- Active priority: **Phase 18C.4 — Real Two-Device Sync: ACTIVE PRIORITY, planning/verification only.**
- Phase 18B.10A: **AUDIT ACCEPTED, IMPLEMENTATION DEFERRED** (`APP_18B10A_ARCHITECT_AUDIT_ACCEPTED_DEFERRED`). Do not implement 18B.10B, 18B.10C, 18B.10D, or 18B.10E. The proposed numerical limits stay unapproved.
- Phase 18B.9: **PAUSED, NOT CLOSED.**
- Cloud Sync production: **OFF.**
- Staging: **RESERVED, not deployed.**
- Sync pilot: **NO-GO** until explicitly authorized.
- Application source baseline: `d6578c0f579d7ee9bd02aec855193339a7d8c124`. Architect named docs baseline `46e84f869aae1501f16a5b05116fbb81112939bf`.
- 18C.1, 18C.2, and 18C.3B remain CLOSED. Do not rebuild the Sync Engine.
- RC account id 1, the 114 Dutch words, the 114 pending outbox rows, and recovery backups were not opened or modified.

## 2. Last results

- Planning only. No application source edit. No lab process. No public port. No VPS change.
- The sync engine, conflict UI, offline retry, restart, and account switch already exist.
- A real pair of computers still needs an authorized copied lab package, `staging_server.py`, and an SSH forward. Launching `account_server.py` from the live source tree would put `accounts.db` beside the repository.

## 3. Next

1. Architect review of the 18C.4 plan. Do not start the lab or the second computer from this handoff.
2. Do not enable production `STUDY_SYNC_ENABLED`, resume 18B.9, implement 18B.10B–E, deploy, or publish a release.

## 4. STOP / boundaries

- STOP for Architect review — no infrastructure, no source change, and no second-machine test.
