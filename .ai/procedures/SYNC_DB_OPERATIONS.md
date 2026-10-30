# Sync database operations

Source procedure for the backup/restore behavior accepted in Phase 18B.2 (`5f4251a`). **Do not run the production steps.** The sync flag stays unset and the sync backup is not scheduled. The Accepted Phase 18B.3 plan is [PHASE-18B.3-production-readiness.md](../plans/PHASE-18B.3-production-readiness.md). That plan is not an authorization to execute this procedure.

## What is already true

- `accounts.db` backup remains `deploy/hetzner/backup_accounts.py` on the existing daily timer. Prefix: `accounts-`.
- Sync backup code is `app/sync_backup.py`. The operator script is `deploy/hetzner/backup_sync.py`. Prefix: `study-sync-`.
- `deploy/hetzner/setup.sh` may copy `backup_sync.py` and the sync unit files into the app tree. It does **not** install or enable the sync timer and does not set `STUDY_SYNC_ENABLED`. Production installation of that timer is Phase 18B.8.
- Alert events and the test sink are [ADR-021](../decisions/ADR-021-sync-backup-alerts.md) (Accepted for the source contract only). Production paging is not configured or operational. A test record file is not paging. Exit 0 after a retention warning does not prove the warning was paged.
- A missing `study_sync.db` is not created by the backup tool.
- Restore publishes with a no-clobber hard link. An existing destination, including a dangling symlink or a file created during the copy, is not modified.
- The temporary file is created mode `0600` before SQLite writes user data. On POSIX the backup directory must end up mode `0700` or the backup fails.
- SQLite paths use an encoded file URI with `mode=ro`.
- After a backup file is published, retention deletes only older `study-sync-*.db` names. If that cleanup fails, the new backup is kept, `retention_warning` is set, and the operator script exits 0 after printing `Retention cleanup failed; the new backup was kept.` It does not delete `accounts-*.db`.
- Phase 18B.5 adds `app/sync_restore_verify.py` and `deploy/hetzner/verify_sync_backup.py`. Status: **CLOSED**, GitHub-verified at `69307892f779e61de7b99563eb5c76ad4296cbcc`. Repository-only. **Not scheduled or installed.** `setup.sh` may copy the script into the app tree and does not install a timer. The verifier does not set `STUDY_SYNC_ENABLED`.

## Restore verification (repository only, do not schedule)

The newest name matching a real ASCII timestamp `study-sync-YYYYMMDD-HHMMSS-ffffff.db` is restored with `restore_database` into a new `run-*` directory under the verification root. Impossible dates, invalid clock values, Unicode digits, and malformed names are not candidates. The verification root is resolved before any directory is created or chmodded; a root that is the protected application directory, a descendant of it, or a symlink alias of it is refused without changes there. The copy is opened with `mode=ro`. `PRAGMA integrity_check` must be `ok`. Schema version must be **2**, with `sync_meta`, `vocabulary_entities`, and `vocabulary_changes` and their expected columns. `sync_store.connect()` is not used, so a future schema is not migrated.

| Result | Exit | Fixed output |
|--------|------|----------------|
| Verified | 0 | stdout `study_sync restore verification verified` |
| Skipped | 0 | stdout `study_sync restore verification skipped` |
| Failed | 1 | stderr `study_sync restore verification failed` |

Skip means there is no validly named backup and the live path does not exist. It does not mean the database never existed. If the live path exists as a regular file, a directory, a symlink, or any other file type, the result is failed, and nothing is created or read there. A corrupt or unsupported newest backup fails. An older file is not tried. The live database, the backup, and `accounts.db` are not written. Paths, tokens, and vocabulary contents are not printed.

Configuration is `STUDY_SYNC_BACKUP_DIR`, `STUDY_SYNC_VERIFY_DIR`, and `STUDY_SYNC_DB` (the live path, used only to see whether a file is present). Tests pass temporary paths and do not call the script against production paths.

A production schedule, alert integration, disappearance detection, and freshness monitoring remain Phase 18B.8.

## Local staging (repository only, do not deploy)

Phase 18B.6 is **Leader-approved source, pending GitHub commit verification**. It is not GitHub-verified yet. It is an isolated local drill. It does not create `/opt/language-guard-staging` on the server, install `language-guard-staging.service`, or change production `.env`. `accounts.db` follows the directory of the copied `account_store.py`. `STUDY_SYNC_DIR` is a different staging directory. The guard in `deploy/hetzner/staging_guard.py` runs before any database is created. It allows only `ACCOUNT_BIND=127.0.0.1`, refuses port `8765`, and refuses paths that resolve into `/opt/language-guard` or `/var/backups/language-guard`. Before the process listens, the staging `.env` must exist and contain only the staging allowlist. The pre-materialization guard may run while that file is absent. Status proof is a new non-overwriting file under the staging proof directory and is not allowed to replace a database, backup, or `.env`. The provider key in that process is `staging-fake-not-a-provider-key` and the AI routes are mocked. On Windows, symlink tests skipped because `os.symlink` is unavailable, including the POSIX proof-partial regression. Follow-up QA: `tests/test_sync_api.py::test_excessive_request_size_does_not_open_sync_db` once raised `ConnectionAbortedError` (WinError 10053) after a 413 response; an isolated rerun passed and the full suite did not reproduce it. A passing local drill is not authorization to run staging on the VPS. Phase 18B.7 is not authorized.

## Local checklist (safe to run)

These are automated and use temporary files only:

1. `tests/test_hetzner_package.py` — packaged server imports with the sync flag unset and does not create `study_sync.db`.
2. `tests/test_sync_staging.py` — login and AI routes still answer; sync routes are 404 while the flag is off; a temporary account can sync only after the flag is set in that test process; backup and restore of that temporary database succeed.
3. `tests/test_sync_backup.py` — integrity gate, no-clobber restore, private temporary files, directory-permission failure, retention warning, literal `%` paths, restore contents, idempotent retry, and accounts files left in place.
4. `tests/test_sync_restore_verify.py` — newest-backup restore verification in temporary directories. It does not restore a production path.
5. `tests/test_sync_staging_isolation.py` — staging guard and the synthetic localhost drill. Temporary trees only. It does not deploy staging. On this Windows host the symlink cases skipped, including the POSIX proof-partial regression. The database-byte and marker cases ran.

No production secrets and no real accounts.

## Production activation prerequisites (do not execute)

All of the following have to be true before anyone sets `STUDY_SYNC_ENABLED=1` on the VPS:

1. Leader has accepted this backup design and an explicit schedule.
2. A restore drill from a `study-sync-*.db` file has succeeded on a **copy**, not on the live file.
3. `backup_accounts.py` has just produced an `accounts-*.db` backup as well.
4. The sync backup script is invoked by a **separate** timer or oneshot. Do not replace the accounts timer.
5. `STUDY_SYNC_DIR` is unset unless operations deliberately chose another directory. The default file is `study_sync.db` beside the server modules.
6. Desktop sync is still not part of this step.
7. An off-box copy is access-controlled and encrypted, and a restore drill from that copy has succeeded onto a new path. On-VPS retention does not satisfy this item. Ownership, credential handling, and who restores are decided in that ops milestone, not here. If production `study_sync.db` does not exist yet, the rehearsal uses a synthetic schema-v2 database in an isolated environment. Staging vocabulary is never copied into the live database. After the first live sync database exists, its first on-box and off-box backups are both required within the approved RPO.
8. Public API rate limits, per-account storage and change-history quotas, and disk-exhaustion protection are implemented, tested, dark-deployed under a separate Leader authorization, and verified effective. Safe HTTP monitoring is in place. An accepted design alone does not satisfy this item.
9. RPO and RTO have been chosen. Backup freshness meets the RPO. A `study_sync.db` that disappears after first creation is detected persistently. The retention warning alerts even when the backup process exits 0.
10. The effective flag matches across `.env`, systemd `Environment=`, drop-in overrides, and the running process.

## Rollback (do not execute)

1. Unset `STUDY_SYNC_ENABLED` in `.env`, the systemd unit, and drop-in overrides, then restart the account server. Confirm the process environment matches. Sync routes go back to 404 and stop opening `study_sync.db`.
2. Leave the database file in place. Do not delete it as part of rollback.
3. Login and AI routes keep using `accounts.db`. The accounts backup timer stays unchanged.
4. To inspect history, restore a `study-sync-*.db` backup into a **new** path and open that copy.
