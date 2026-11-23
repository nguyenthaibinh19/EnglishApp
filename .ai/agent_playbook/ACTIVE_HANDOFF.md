# Active handoff

Rolling coordination checkpoint. See [current_state.md](../current_state.md) and [PHASE-18C.4-two-device-sync-acceptance.md](../plans/PHASE-18C.4-two-device-sync-acceptance.md).

## 1. Checkpoint metadata

- Written: 2026-11-23.
- Tag: `APP_18C4P_R4_BLOCKED`.
- Source baseline: `17365b084d8f92fa13a446592f1c68c0a41302c6`.
- Active priority: **Phase 18C.4 — direct production Cloud Sync.** Preflight passed. The synthetic account and Sync flag were not changed.
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
- R4 preflight: service healthy, four hashes match, flag unset, snapshot and code rollback present. Details: [PHASE-18C.4P-R4-sync-activation.md](../plans/PHASE-18C.4P-R4-sync-activation.md).
- Account creation stopped because `account_server.py add` needs a private `getpass` prompt. No password was generated or entered.
- `client-a` holds the synthetic staging session and bundled starter files. It is outside production, RC, recovery, and the repository.

## 3. Next

1. Owner creates `syncpilot_18c4p` on a private terminal and does not paste the password into chat.
2. Repeat activation only after that account exists. Do not set the flag before then.

## 4. STOP

- Do not set `STUDY_SYNC_ENABLED` until the synthetic account exists.
- Do not invent a password entry path around `getpass`.
- Do not enable the sync backup timer or launch the production EXE.
- Do not resume 18B.9 or implement 18B.10B–E.
- Do not upload the preserved 114-word account.
