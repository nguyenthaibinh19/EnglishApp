# Sync database operations

Source procedure for Phase 18B.2. **Do not run the production steps in this phase.** The sync flag stays unset and the sync backup is not scheduled.

## What is already true

- `accounts.db` backup remains `deploy/hetzner/backup_accounts.py` on the existing daily timer. Prefix: `accounts-`.
- Sync backup code is `app/sync_backup.py`. The operator script is `deploy/hetzner/backup_sync.py`. Prefix: `study-sync-`.
- `deploy/hetzner/setup.sh` may copy `backup_sync.py`. It does **not** add a timer and does not set `STUDY_SYNC_ENABLED`.
- A missing `study_sync.db` is not created by the backup tool.
- Restore publishes with a no-clobber hard link. An existing destination, including a dangling symlink or a file created during the copy, is not modified.
- The temporary file is created mode `0600` before SQLite writes user data. On POSIX the backup directory must end up mode `0700` or the backup fails.
- SQLite paths use an encoded file URI with `mode=ro`.
- After a backup file is published, retention deletes only older `study-sync-*.db` names. If that cleanup fails, the new backup is kept, `retention_warning` is set, and the operator script exits 0 after printing `Retention cleanup failed; the new backup was kept.` It does not delete `accounts-*.db`.

## Local checklist (safe to run)

These are automated and use temporary files only:

1. `tests/test_hetzner_package.py` — packaged server imports with the sync flag unset and does not create `study_sync.db`.
2. `tests/test_sync_staging.py` — login and AI routes still answer; sync routes are 404 while the flag is off; a temporary account can sync only after the flag is set in that test process; backup and restore of that temporary database succeed.
3. `tests/test_sync_backup.py` — integrity gate, no-clobber restore, private temporary files, directory-permission failure, retention warning, literal `%` paths, restore contents, idempotent retry, and accounts files left in place.

No production secrets and no real accounts.

## Production activation prerequisites (do not execute)

All of the following have to be true before anyone sets `STUDY_SYNC_ENABLED=1` on the VPS:

1. Leader has accepted this backup design and an explicit schedule.
2. A restore drill from a `study-sync-*.db` file has succeeded on a **copy**, not on the live file.
3. `backup_accounts.py` has just produced an `accounts-*.db` backup as well.
4. The sync backup script is invoked by a **separate** timer or oneshot. Do not replace the accounts timer.
5. `STUDY_SYNC_DIR` is unset unless operations deliberately chose another directory. The default file is `study_sync.db` beside the server modules.
6. Desktop sync is still not part of this step.

## Rollback (do not execute)

1. Unset `STUDY_SYNC_ENABLED` and restart the account server. Sync routes go back to 404 and stop opening `study_sync.db`.
2. Leave the database file in place. Do not delete it as part of rollback.
3. Login and AI routes keep using `accounts.db`. The accounts backup timer stays unchanged.
4. To inspect history, restore a `study-sync-*.db` backup into a **new** path and open that copy.
