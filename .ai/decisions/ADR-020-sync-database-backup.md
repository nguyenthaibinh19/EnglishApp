# ADR-020 Sync Database Backup and Restore

Status: Accepted (source backup/restore architecture only — **not** production scheduling or activation; sync flag stays off; nothing deployed; no desktop client)

## Context

`study_sync.db` is separate from `accounts.db` ([ADR-018](ADR-018-account-cloud-sync.md)). The daily timer runs `backup_accounts.py` only. Phase 18B.1 ([ADR-019](ADR-019-vocabulary-sync-http.md), accepted commit `599e473`) can write vocabulary once `STUDY_SYNC_ENABLED=1`, but that flag stays unset. Turning it on without a sync backup would make vocabulary history unrecoverable.

## Decision

- Sync backup is a **separate** tool (`app/sync_backup.py`, operator script `deploy/hetzner/backup_sync.py`). It does not change `backup_accounts.py` retention or filenames.
- Use SQLite's online backup API. Do not copy the file with a raw filesystem copy.
- If `study_sync.db` is absent, the backup **returns without creating it**.
- Write a private temporary file (created with mode `0600` before SQLite writes it), require `PRAGMA integrity_check` = `ok`, then publish with `os.link` so an existing name is not replaced. Delete the temporary name after a successful link, and delete it on failure. There is no `os.replace` fallback. A failed copy must not leave a finished `study-sync-*.db`.
- Source paths are opened through `Path.as_uri()` plus `?mode=ro`, so reserved characters such as a literal `%` are encoded and the connection stays read-only.
- Filename prefix `study-sync-` is distinct from `accounts-`. Retention deletes only that prefix, and never `accounts-*.db`.
- On POSIX, the backup directory must be mode `0700`. If that cannot be enforced, the backup fails and nothing is published. Windows does not enforce Unix directory modes; the backup still runs there.
- Never delete the source database.
- Restore publishes into a new path with the same no-clobber link. A destination that already exists, including a dangling symlink or a file created while the copy is running, is left unchanged.
- Retention runs only after the new backup is published. If cleanup then fails, the function still returns that backup and sets `SyncBackupResult.retention_warning`. The operator script prints that warning and exits 0. An unfinished backup is never reported as success.
- The sync backup script is **not** on the systemd timer. `setup.sh` may copy it, but it does not enable a schedule. Scheduling waits for a later ops review.
- Tests and local drills pass explicit source and backup paths. They use `tmp_path` only.

Activation prerequisites and rollback steps live in [SYNC_DB_OPERATIONS.md](../procedures/SYNC_DB_OPERATIONS.md). This phase does not perform them.

## Why

Account backups must keep working even if sync backup is absent or failing. Publishing only after an integrity check avoids treating a truncated file as a restore point.

## Consequences

Easier: a future operator can drill backup and restore on copies before anyone sets the flag. Harder: until the timer is deliberately enabled, production `study_sync.db` is still unscheduled. Windows does not enforce Unix `0600` / `0700`; POSIX does, and a POSIX directory that cannot be made private fails the backup. A retention warning means the new backup is valid and old `study-sync-` files may still be present.

## Do not

- Do not point the accounts timer at `backup_sync.py` in this phase.
- Do not set `STUDY_SYNC_ENABLED=1` on the VPS.
- Do not restore over a live `study_sync.db` or `accounts.db`.
- Do not delete `accounts-*.db` files from the sync retention pass.
