# Active handoff

Rolling coordination checkpoint. See [current_state.md](../current_state.md) and [PHASE-18C.4-two-device-sync-acceptance.md](../plans/PHASE-18C.4-two-device-sync-acceptance.md).

## 1. Checkpoint metadata

- Written: 2026-11-23.
- Tag: `APP_18C4A_R1_MERGED_READY_FOR_18C4B_AUTHORIZATION`.
- PR #29 merged. Approved source HEAD `be7df9a7b5d38d2ffc61766511d5affae491cd4c`. Merge and `origin/main`: `e5763ff08097c6bb62901f6a858eda355b26f97c`.
- Active priority: **Phase 18C.4 — Real Two-Device Sync.** 18C.4A is the offline preflight. It is not the live test.
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
- Nineteen copied modules match their source SHA-256. `accounts.db` and `study_sync.db` are absent.
- Imported `account_store.__file__` is the lab copy. Sync path resolves under `lab\sync` and was not opened.
- Original junction probe: **FAIL**. `os.path.islink` missed it and the guard accepted the path.
- Junction detection remains in the review: a fresh `junction-probe` was rejected with `symlink`, then removed. `os.path.islink` on it was false.
- Final correction: `os.lstat` replaces `os.path.lexists` in the component walk. Only `FileNotFoundError` means missing. An unreadable existing component is rejected. Focused tests: **22 passed, 3 skipped**. The skips are file or directory symlink creation, **UNVERIFIED**.
- Lab revalidation of the ordinary directories returned PASS. `staging_server.py` was not run. Port `18765` was not listening. Both database files remain absent.
- `client-a` is empty and outside production, RC, recovery, and the repository.

## 3. Next

1. 18C.4B requires a separate authorization before the server starts, before accounts are created, and before SSH or computer B is used.

## 4. STOP

- Do not start the lab server.
- Do not create test accounts.
- Do not open an SSH tunnel.
- Do not run the two-computer scenarios.
- Do not enable production `STUDY_SYNC_ENABLED`, resume 18B.9, or implement 18B.10B–E.
