# Health monitoring

Phase 18B.8 is **CLOSED — Leader Accepted, 2026-11-10**. This closure is monitoring infrastructure and does not activate vocabulary Cloud Sync. The source is committed at `24e600b` and merged at `65b045a`. On 2026-11-09 the health socket and the health check and report timers were enabled on the VPS from `5f0c3c3`. The sync-backup timer was installed and left disabled. The sync-verify timer is enabled and operational. `setup.sh` was not used. The accounts backup timer was not changed. `STUDY_SYNC_ENABLED` stays unset. Cloud Sync stays OFF. `study_sync.db` is absent. Production deployment and the 2026-11-10 natural runs passed. The user received the scheduled Telegram and email. Healthchecks accepted the 2026-11-10 heartbeat. Commit `f57bcc6` contains the one-line `ReadOnlyPaths` hotfix: `/opt/language-guard/venv -/opt/language-guard/app /opt/language-guard/deploy/hetzner -/var/backups/language-guard/study-sync`. The natural verifier fired at `2026-11-10 07:00:00 UTC`, exited 0 at `07:00:01 UTC`, and recorded `SKIPPED` at `2026-11-10T07:00:01Z`. That result is not a successful sync backup or restore. The natural report fired at `2026-11-10 08:00:00 UTC` and finished at `08:00:07 UTC`. The latest observed 30-minute check was `2026-11-10 11:30:20 UTC`. UptimeRobot external uptime monitor: UNVERIFIED / DEFERRED. It is not configured or verified. Healthchecks is the missed-report signal and does not give immediate detection of every VPS outage. Telegram and email do not replace that external monitor.

`PROVIDER_ACCEPTED` means the provider API returned success. The 2026-11-10 report was also confirmed by the user. A finished collector process does not by itself mean every future report was delivered. If the VPS is down, neither Telegram nor email can be sent. Healthchecks.io is the operational missed-report signal. UptimeRobot external uptime monitor: UNVERIFIED / DEFERRED.

## Schedules

| Timer | Calendar | Mode |
|---|---|---|
| `language-guard-health-check.timer` | `*-*-* *:0/30:00 Europe/Amsterdam` | state-change alerts and retries of a rejected channel |
| `language-guard-health-report.timer` | `*-*-* 09:00:00 Europe/Amsterdam` | one daily report per Amsterdam civil date |
| `language-guard-sync-backup.timer` | `*-*-* 04:45:00 UTC` plus `RandomizedDelaySec=10m` | installed on the VPS; timer disabled and inactive |
| `language-guard-sync-verify.timer` | `*-*-* 08:00:00 Europe/Amsterdam` | enabled; first natural run `2026-11-10 07:00:00 UTC`, result `SKIPPED` |
| `language-guard-backup.timer` | unchanged `03:15` plus up to 20 minutes | accounts backups only |

No unit contains a `Timezone=` directive. The zone is part of the calendar expression. `systemd-analyze calendar` was run on the VPS on 2026-11-09 for these expressions, including the 2026-03-29 and 2026-10-25 transitions. The 09:00 Europe/Amsterdam elapse occurred once on each of those days.

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

The verifier runs as `lg-verify`, group `lg-health`. Its state directory is `/var/lib/language-guard-verify`, mode `0750`. The collector's supplementary group `lg-health` can read the published result and cannot write the directory or the verifier lock. The collector does not need write access to read `result.json`. The account server is not in that group. Accounts snapshots are mode `0600` after Step A. No traverse ACL was added on `/var/backups/language-guard`. The one `SKIPPED` run did not need to read that directory because no sync backup directory or live sync database exists. Do not add a traverse grant unless a later sync-backup design still cannot expose the `0600` accounts files.

Root can still inspect any process. A process that can connect to the socket can submit a structured event, not arbitrary prose. It cannot read the bot token, the Brevo key, or the heartbeat URL. The notifier tree was created at `/opt/language-guard-notify` as root-owned files on 2026-11-09. `setup.sh` did not create it and must not chown it to `guard`.

## Operator setup, not done here

Do not create these accounts as part of repository work.

1. Telegram: create a bot with BotFather, open a chat with it, and store the token and chat id in the credential files above.
2. Brevo Free: create an account, authenticate the sender domain with SPF and DKIM, and store the API key, sender, and one recipient. The free plan's published limit is 300 emails per day, shared with campaigns, with no rollover. This design sends about one email per day plus rare alerts.
3. UptimeRobot Free remains a design option: one keyword monitor on `https://langstudyguard.com/` for `Language Guard account server is running.`, every 5 minutes, email alerts. Do not add backup details to the public health response. Status: UNVERIFIED / DEFERRED. Do not treat this step as configured.
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
- `systemd-analyze calendar` for the four expressions, including 2026-03-29 and 2026-10-25, was run on the VPS on 2026-11-09. The 09:00 expression occurred once on each transition day.
- A skipped sync backup would be reported as success.
- This work would be treated as off-box recovery (18B.9) or Sync activation (18B.11).

Phase 18B.8 source is installed on the VPS and is not a production closure. The natural health timers are not yet observed. Phase 18B.7 remains closed. Cloud Sync remains off.

The paragraph above is the pre-closure stop note. The opening paragraph is the accepted state: Phase 18B.8 is CLOSED — Leader Accepted, 2026-11-10, and the natural timers were observed.

## Phase 18B.9 off-box monitoring design, not installed

This monitoring design is accepted as of 2026-11-10. Nothing in this section is installed. No remote backup has run. No production uploader exists. Until a later reviewed change is active, the Google Drive line is **NOT CONFIGURED**. It is not SUCCESS. Cloud Sync stays OFF.

The 09:00 Europe/Amsterdam report is the daily place for that status. The future lines are fixed phrases for local VPS backup, Google Drive, last attempt, last successful remote backup, age of the last valid backup, remote artifact check, last successful restore drill, and Cloud Sync. An upload is not a remote checksum match. A checksum match is not a restore. A restore drill decrypts one artifact onto a new path and passes SQLite `integrity_check`.

The current socket still accepts only `check`, `report`, `backup-incident`, and `recovery`, at most 12 check lines, and no free text, path, token, or extra field. Fitting the new lines into that closed request is a later review. The collector and the notifier do not receive the age identity or the OAuth refresh token. The word "age" in the incident rules above means elapsed time. The encryptor named age is a separate tool and is not installed.

When a later off-box job is active, it reports failure at the time of the failure through `backup-incident`. The 30-minute check retries a channel that has not reached `PROVIDER_ACCEPTED`. A missed run uses a new Healthchecks.io check with its own grace. That ping is not the 09:00 report ping. The 26-hour figure is not an approved stale threshold. Stale alerting starts only after a threshold is approved.

The conditions that alert are backup failure, upload failure, OAuth or permission failure, remote checksum mismatch, age past the approved threshold, a failed restore drill, a missing scheduled result, and insufficient remote space. The message names the condition. It contains no token, encryption key, database content, or personal data.

The same incident fingerprint is not sent again after both Telegram and email accept it. A different condition is a new incident. The change back to a healthy condition sends `recovery` once.
