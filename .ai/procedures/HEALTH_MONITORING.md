# Health monitoring

Repository templates for Phase 18B.8. They are not installed, enabled, or started by this document. `setup.sh` copies them into the application tree and does not copy them into `/etc/systemd/system`. The accounts backup timer is unchanged. `STUDY_SYNC_ENABLED` stays unset.

`PROVIDER_ACCEPTED` means the provider API returned success. It does not prove that a person received or read the message. A finished collector process also does not mean the report was delivered. If the VPS is down, neither Telegram nor email can be sent. UptimeRobot is the public-outage signal, and Healthchecks.io is the missed-report signal.

## Schedules

| Timer | Calendar | Mode |
|---|---|---|
| `language-guard-health-check.timer` | `*-*-* *:0/30:00 Europe/Amsterdam` | state-change alerts and retries of a rejected channel |
| `language-guard-health-report.timer` | `*-*-* 09:00:00 Europe/Amsterdam` | one daily report per Amsterdam civil date |
| `language-guard-sync-backup.timer` | `*-*-* 04:45:00 UTC` plus `RandomizedDelaySec=10m` | existing sync backup template, not enabled |
| `language-guard-sync-verify.timer` | `*-*-* 08:00:00 Europe/Amsterdam` | restore verification template, not enabled |
| `language-guard-backup.timer` | unchanged `03:15` plus up to 20 minutes | accounts backups only |

No unit contains a `Timezone=` directive. The zone is part of the calendar expression. `systemd-analyze calendar` on a systemd host is still required before installation. That check was skipped where `systemd-analyze` is absent and is not a pass.

09:00 Europe/Amsterdam occurs once on the DST transition days. The overlapping hour is 02:30, not 09:00. `Persistent=true` runs one catch-up for the current civil date. It does not send a second report for that date, and it does not replay every missed day. A missed day is the Healthchecks alert.

## Statuses

`VERIFIED`, `SKIPPED`, `NOT INSTALLED`, `UNKNOWN`, `WARNING`, and `FAILED` stay distinct. Overall `OK` requires every mandatory check to be `VERIFIED` and no check to be `FAILED`, `WARNING`, `UNKNOWN`, or `NOT INSTALLED`. A recorded `SKIPPED` sync line can still leave the report overall `OK`. `SKIPPED` is not a successful sync backup and not a successful restore. `NOT INSTALLED` and `UNKNOWN` are not `OK`.

Before the sync backup timer is installed in `/etc/systemd/system`, `sync_backup` is `NOT INSTALLED`. `sync_verify` is `UNKNOWN` (`never-run`) when that timer file is present and no result file exists. It is `NOT INSTALLED` when the timer file is absent and no result file exists. The verifier writes `/var/lib/language-guard-verify/result.json` only after a real run, with status `VERIFIED`, `SKIPPED`, or `FAILED`, a UTC `checked_at` timestamp, and the backup name, size, mtime, and SHA-256. It does not write `UNKNOWN`. The write is atomic, refuses a symlink, and the file mode is `0640`. The verifier's own lock stays mode `0600` in that directory. The collector reads the published file read-only and does not create or write that lock. A published file with a bad status, timestamp, backup name, byte count, mtime, or SHA-256 is `UNKNOWN` (`unreadable`), as is a directory or other non-regular path. A missing file stays `never-run`. `VERIFIED` stays current only while `checked_at` is inside the freshness window and the name, size, mtime, and SHA-256 still match the newest valid backup. The verifier is scheduled at 08:00 Europe/Amsterdam. A check at or after that time stays current until 10:00 Europe/Amsterdam on the next civil day, two wall-clock hours after the next scheduled run. The October fall-back does not shorten that grace to one hour. A future, malformed, or older timestamp is not current. A stopped timer does not remain `VERIFIED`. Reusing the size and mtime does not keep a replaced file current. A recorded `FAILED` stays `FAILED` until a later run records `VERIFIED`. A `SKIPPED` record does not replace `FAILED` and does not become `VERIFIED`. An expired `SKIPPED` record is `UNKNOWN`, not a fresh skip.

Accounts snapshot integrity runs when the snapshot identity changes and is reused while device, inode, size, and mtime are unchanged. The collector opens that snapshot read-only. It does not open, migrate, or delete the live accounts database.

Sync backup age becomes `FAILED` only after `STUDY_SYNC_RPO_HOURS` is set. Until an RPO is approved, that threshold stays inactive.

## Witness and the polling gap

`/var/lib/language-guard/study-sync-observed` is written only after a check sees a regular `study_sync.db`. The checker never creates that database. If the witness exists and the live file is gone, the status is `FAILED` even when an old `study-sync-*.db` remains.

A check every 30 minutes cannot see a database that is created and deleted between checks. No witness is written in that case, so the next check looks like the database was never created. Before Phase 18B.11, activation is blocked until one check has recorded the witness while the live file is still present. Phase 18B.11 is not authorized by this document.

## Credentials

Root-owned mode `0400` files, read only by `language-guard-health-notify@.service` through `LoadCredential=`:

- `/etc/language-guard/telegram.token`
- `/etc/language-guard/telegram.chat`
- `/etc/language-guard/brevo.key`
- `/etc/language-guard/brevo.sender`
- `/etc/language-guard/brevo.recipient`
- `/etc/language-guard/heartbeat.url`

The sync backup unit runs as `guard` and sets `HEALTH_STATE_PATH=/var/lib/language-guard/health-state.json`. That directory is the collector `ReadWritePaths`. It must exist, be writable by `guard`, and must not be a symlink. Without that variable, a backup failure is not recorded. A missing sync database is still exit 0 and does not alert. ADR-021 stderr and exit codes are unchanged.

A backup incident has an id separate from check severity. A new failure or retention warning replaces that id and clears channel acceptance, even when another check was already `FAILED`. The notification names that incident even when the live sync database is absent. A witnessed disappearance stays a separate failure when no incident is waiting. Acceptance is recorded only for the incident id included in that notification. A newer incident created during the send keeps an empty acceptance map. `published` does not erase the incident. It is cleared only after both Telegram and Email accept it. The state lock is released when the process exits. A leftover lock file is not a held lock, and lock files are not deleted by age. Opening the lock refuses a symlink. SQLite integrity checks, backup hashing, and the other probes run outside that lock. The collector then merges them with the latest state under a short lock and does not replace a newer incident, its id, per-channel acceptance, or a newer backup notice with the stale probe. Provider calls also happen outside the lock. Delivery is at-least-once: overlapping collectors, or a crash after the provider accepts and before the state write, can send again. That is not exactly-once delivery.

The collector stays `User=guard` so it can read backups. It has no `LoadCredential=` entries. `InaccessiblePaths=-/etc/language-guard` hides the credential directory from that process. It sends one length-prefixed JSON request to `/run/language-guard/notify.sock`. The request may contain only the version, channel names, an event name (`check`, `report`, `backup-incident`, or `recovery`), up to 12 check lines, a heartbeat flag, and, for a report, the civil `report_date`. The notifier writes the provider text from that event. Free text, a path, or an extra field is rejected. A heartbeat is valid only on `report`. One connection carries one request. The notifier reserves provider attempts, including each channel's retry budget of 3, before calling a provider. The bound is 12 reserved attempts per 30 minutes, not 12 connections. A heartbeat-only retry and a schema rejection each reserve one of those attempts. Unused retries are not refunded. A corrupt ledger refuses the request and is not reset. A rejected or rate-limited request does not record acceptance and does not ping the heartbeat. `report_date` must be a real calendar date. A ping follows a provider-accepted report for the notifier's current Europe/Amsterdam civil date, or a later retry of that same date when the report was accepted and the ping failed. The ledger keeps only that current date. An older date does not authorize a ping. `ping-accepted` means the monitor URL accepted the ping. It does not mean a person received the Telegram or email message.

The socket inode is `lg-notify:lg-notify-client` mode `0660`. systemd creates `/run/language-guard` as `root:root`. `DirectoryMode=0755` lets clients traverse that directory. `0750` would not, so directory mode alone does not prove a client can connect. Connect authorization is the socket mode and group. The health units receive `lg-notify-client` through `SupplementaryGroups=`. `language-guard.service` does not. `language-guard-notify.sysusers` does not add `guard` to that group. Adding `guard` to `lg-notify-client` in `/etc/group` would let the account server connect, so install must not do that.

The notifier runs as `lg-notify`. It is the only unit that loads the credentials. Its executable is `python -I` from `/opt/language-guard-notify/venv`, and its only inserted import path is `/opt/language-guard-notify/app`. That tree is installed by a separate operations plan as `root:root` mode `0755`, with files mode `0644`, and `setup.sh` must not chown it to `guard`. The whole `/opt/language-guard` tree is inaccessible to the notifier. The process refuses to start when its own file is under `/opt/language-guard`. Its namespace also hides backups and the collector state. Attempt timestamps live in `/var/lib/language-guard-notify`, mode `0700`, owned by `lg-notify`. It does not open a path from the request. Logs still contain only the channel, result, HTTP status, and attempt.

The verifier runs as `lg-verify`, group `lg-health`. Its state directory is `/var/lib/language-guard-verify`, mode `0750`. The collector's supplementary group `lg-health` can read the published result and cannot write the directory or the verifier lock. The collector does not need write access to read `result.json`. The account server is not in that group. Before the verify unit is installed, the sync backup directory needs a traverse grant for `lg-verify` without giving it read access to the accounts backup files. Those files stay mode `0600`. This repository does not change their permissions.

Root can still inspect any process. A process that can connect to the socket can submit a structured event, not arbitrary prose. It cannot read the bot token, the Brevo key, or the heartbeat URL. The notifier tree is not created by this repository's deploy script. Until that operations plan installs it, the unit is a template only.

## Operator setup, not done here

Do not create these accounts as part of repository work.

1. Telegram: create a bot with BotFather, open a chat with it, and store the token and chat id in the credential files above.
2. Brevo Free: create an account, authenticate the sender domain with SPF and DKIM, and store the API key, sender, and one recipient. The free plan's published limit is 300 emails per day, shared with campaigns, with no rollover. This design sends about one email per day plus rare alerts.
3. UptimeRobot Free: one keyword monitor on `https://langstudyguard.com/` for `Language Guard account server is running.`, every 5 minutes, email alerts. Do not add backup details to the public health response.
4. Healthchecks.io Hobbyist: one check with cron `0 9 * * *` in `Europe/Amsterdam` and a 2-hour grace. Store the ping URL as a credential. The collector pings only after at least one provider accepts that day's report, and may retry the ping if that acceptance was stored and the ping failed. A successful ping is not proof a person received the message.

Paid Telegram broadcasts, Brevo upgrades, UptimeRobot heartbeat, SMS, and phone calls are not part of this design.

## ADR-021

Backup failure still prints `study_sync backup failed` and exits 1 when the sink accepts the event. A retention warning still prints `Retention cleanup failed; the new backup was kept.` and exits 0 when the sink accepts it. That exit 0 is the retention warning, not a normal backup with empty stderr. A missing sync database still exits 0 and creates nothing. A missing alert sink still exits 2 and prints `study_sync alert was not delivered`. The health note is best-effort. If the note cannot be written, the exit code and those fixed lines stay the same. The note does not record that an alert was delivered.

A backup failure or retention warning is visible to Telegram and email on the next health check. That check runs every 30 minutes, so the health channels can lag the backup by up to 30 minutes, plus any time the host was down. The ADR-021 sink, when one is configured, is the immediate signal. No production sink is configured. A later successful publish does not erase an incident until both Telegram and Email have returned `PROVIDER_ACCEPTED` for that incident. A health check that only displays it, or a run where either channel is rejected or not sent, leaves the incident queued. Acceptance is stored per channel. The channel that already accepted is not sent again while the fingerprint is unchanged. The rejected channel stays pending. `PROVIDER_REJECTED` and `NOT_SENT` are not stored as delivery.

The backup script does not send Telegram or email itself. A check that finds an unchanged fingerprint retries only a channel whose last result was not `PROVIDER_ACCEPTED`. Acceptance of one channel does not remove the other channel from that retry. `PROVIDER_ACCEPTED` is stored only for a provider success. `PROVIDER_REJECTED` and `NOT_SENT` are not stored as delivery.

## STOP before any production install

- The accounts timer, accounts backup script, or account service would be edited.
- A unit would be enabled or a service restarted.
- `STUDY_SYNC_ENABLED` would be set, or `study_sync.db` would be created by the checker.
- Secrets would be committed or placed in the application `.env`.
- `systemd-analyze calendar` has not been run on the target systemd for the four expressions, including the 2026-03-29 and 2026-10-25 transitions.
- A skipped sync backup would be reported as success.
- This work would be treated as off-box recovery (18B.9) or Sync activation (18B.11).

Phase 18B.8 is not closed. Phase 18B.7 remains closed.
