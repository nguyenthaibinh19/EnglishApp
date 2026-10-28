# ADR-021 Sync Backup Alert Contract

Status: Accepted (source alert contract only — production paging is **not** configured or operational; units are **not** installed or enabled; sync flag stays off)

## Context

Phase 18B.2 ([ADR-020](ADR-020-sync-database-backup.md), accepted commit `5f4251a`) backs up `study_sync.db` and exits 0 when retention cleanup fails after a good publish. systemd `OnFailure=` cannot see that exit 0. Phase 18B.3 (accepted planning commit `97f7b25`) requires an alert for that warning and a separate sync backup directory. No operator has chosen a production notification destination.

## Decision

- Repository units `language-guard-sync-backup.service` and `.timer` run `backup_sync.py` as `guard:guard`. Source `/opt/language-guard/study_sync.db`. Destination `/var/backups/language-guard/study-sync`. Schedule `04:45` with `Persistent=true` and `RandomizedDelaySec=10m`. They are not installed or enabled. `setup.sh` must not enable them. Installation remains Phase 18B.8.
- The accounts timer stays on `backup_accounts.py` at `03:15`. Sync retention does not delete `accounts-*.db`. The sync tool chmods only the dedicated directory.
- A missing source exits 0, creates nothing, and emits no alert.
- Backup failure prints `study_sync backup failed` and exits 1 when the sink accepts the event. That includes `SyncBackupError` and expected filesystem or SQLite failures before the copy starts, such as a backup directory path already occupied by a regular file. The stderr line stays fixed. Exception text, paths, credentials, and tracebacks are not printed.
- Retention failure still prints `Retention cleanup failed; the new backup was kept.` and exits 0 when the sink accepts the event. The new backup remains.
- Each of those two outcomes emits one event with only `event_type`, `timestamp`, and `status`. Event types are `sync_backup_failed` and `sync_backup_retention_warning`.
- `STUDY_SYNC_ALERT_SINK` empty means delivery is not configured. `test` writes the three fields to `STUDY_SYNC_ALERT_RECORD` for a local test. Any other name fails closed and is not copied into output. A test file is not a production page.
- If the sink is missing or rejects the event, the process prints `study_sync alert was not delivered` and exits 2. Exit 2 means the page was not delivered. It does not delete a published backup.
- Disappearance detection after first creation, RPO freshness, and a production soak are not this contract. They stay Phase 18B.8.

## Why

Exit 0 cannot be the only retention signal. A destination that has not been chosen must not be invented, and an unattended log must not be described as paging.

## Consequences

Easier: tests can record alerts in memory or in a temp file. Harder: until an authorized sink exists and the units are installed, production paging is not operational. A successful oneshot does not prove retention ran.

## Do not

- Do not install, enable, or start the sync timer in this phase.
- Do not set `STUDY_SYNC_ENABLED=1`.
- Do not add an email address, webhook, phone number, or secret as the sink.
- Do not point the accounts timer at `backup_sync.py`.
- Do not treat `OnFailure=` as the retention-warning signal.
