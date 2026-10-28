# Phase 18B.3 — Production readiness plan

Status: **Accepted** planning document (`97f7b25`). Acceptance of this plan does not authorize implementation of later milestones, a VPS change, a timer, flag activation, a database write, or Windows client work. Phase 18B.4 may add repository units only. Installing them is Phase 18B.8 and is not started automatically.

Accepted baseline: Phase 18B.2 commit `5f4251a9e88b434621c8f0ac7eb281de6d4ee174` (`5f4251a`).

Related decisions, still Accepted and unchanged by this plan:

- [ADR-018](../decisions/ADR-018-account-cloud-sync.md) — isolated `study_sync.db` (`94f1bf7`)
- [ADR-019](../decisions/ADR-019-vocabulary-sync-http.md) — default-off vocabulary HTTP (`599e473`)
- [ADR-020](../decisions/ADR-020-sync-database-backup.md) — source backup/restore only; no production schedule
- [SYNC_DB_OPERATIONS.md](../procedures/SYNC_DB_OPERATIONS.md) — operator notes; production steps stay unexecuted

## Current facts this plan relies on

- The account server is one process: user `guard`, bind `127.0.0.1:8765`, Caddy in front, `WorkingDirectory=/opt/language-guard`. `config` calls `load_dotenv()` because the server is not a frozen executable, so `/opt/language-guard/.env` can set `STUDY_SYNC_ENABLED`.
- Sync turns on only when that variable is exactly `1` after trim. Unset, empty, `true`, `yes`, and `0` stay off. While off, the three POST sync paths return 404 and do not open or create `study_sync.db`.
- The live file, when the flag is on and `STUDY_SYNC_DIR` is unset, is `study_sync.db` beside the server modules (`/opt/language-guard/study_sync.db` on the VPS layout). `STUDY_SYNC_DIR` moves only that file. It does not move `accounts.db`.
- `backup_accounts.py` remains the daily timer (`language-guard-backup.timer`, 03:15, `Persistent=true`, `RandomizedDelaySec=20m`). Prefix `accounts-`, keep 14. `setup.sh` enables that timer and also copies `backup_sync.py` without a unit for it.
- `backup_sync.py` defaults to `/opt/language-guard/study_sync.db` and `/var/backups/language-guard`. A missing source exits 0 and creates nothing. `SyncBackupError` prints `study_sync backup failed` and exits 1. A retention failure after a good publish prints `Retention cleanup failed; the new backup was kept.` and exits 0. Keep default is 14. Prefix is `study-sync-` only.
- On POSIX the backup directory must be mode `0700` or the sync backup publishes nothing. That chmod applies to the directory the tool is given. Today that default directory is the same directory the accounts backups use.
- Publish and restore use `os.link` inside the destination directory, so the destination directory has to be on one filesystem. The SQLite copy itself can read a source on another filesystem. Restore refuses an existing destination and does not delete the source or the backup.
- There is no `OnFailure=` unit, no off-box copy, and no restore probe. A retention warning is invisible to `systemctl` because the process exits 0.
- Windows Startup stays deferred. AI Local Reading/Listening stays the next major product priority after sync readiness. No desktop sync client exists.

## 1. Separate sync backup schedule, retention, and monitoring

Add a **new** oneshot service and timer in a later authorized milestone. Leave `language-guard-backup.service` and `.timer` pointed at `backup_accounts.py`.

Recommended shape, for review only:

| Item | Recommendation |
|------|----------------|
| Unit names | `language-guard-sync-backup.service` and `.timer` |
| User | `guard` / `guard`, same as the accounts backup |
| Command | existing `backup_sync.py` via the venv Python |
| Clock | a different `OnCalendar` from 03:15, with its own `Persistent=true` and a bounded random delay |
| Source | the same path the server will open: unset `STUDY_SYNC_DIR` and `STUDY_SYNC_DB` together, or set both to that one file |
| Destination | a dedicated directory, proposed `/var/backups/language-guard/study-sync`, mode `0700`, owner `guard` |
| Retention | keep 14 `study-sync-*.db` files, matching `DEFAULT_KEEP`, until Leader chooses a longer window |
| Install | a later milestone copies the units and enables only the sync timer. `setup.sh` must not gain that `enable` in the same change as a code deploy |

The dedicated directory matters because a POSIX sync backup chmods its destination to `0700`. Using the accounts directory would change the mode of the directory that already holds `accounts-*.db`.

Monitoring that can ship with the timer:

- `systemd` result of the oneshot (`success` / `failed`), visible with the unit status.
- A timestamp file or journal line that names the published `study-sync-*.db` path on success. The path is operator data; it must not include secrets.
- A check that the newest `study-sync-*.db` is younger than the timer interval plus the random delay, once a live `study_sync.db` exists. Before that file exists, a missing source exiting 0 is the accepted behavior.
- Disk space on the backup filesystem before the run is considered healthy.
- The accounts timer still succeeds on its own calendar. A sync failure must leave that unit enabled.

On-VPS retention is a local convenience only. Fourteen copies on the VPS disk are the same failure domain as the live databases. That retention is not a recovery copy. See the mandatory off-box gate below.

## 2. Backup failure and retention-warning alerting

Two outcomes need different signals. ADR-020 already fixes the exit codes; this plan does not change them.

| Outcome | Process result | Required alert |
|---------|----------------|----------------|
| `SyncBackupError` (integrity, permissions, publish refused, private-file failure) | exit 1, stderr `study_sync backup failed` | page on oneshot failure |
| Retention cleanup fails after a good publish | exit 0, stderr `Retention cleanup failed; the new backup was kept.` | page even though the unit is success |
| Source file absent | exit 0, no new file | quiet only before the live database has ever existed; after first creation, a persistent check pages when `study_sync.db` is gone |
| Success | exit 0, no warning | no page; record the new filename |

`OnFailure=` can cover exit 1 only. The retention warning needs a second watcher: a journal match for that exact sentence, or a later status file written by the operator script. Changing the warning into exit 1 would contradict ADR-020 and would have to be a new ADR.

The accounts backup has the same gap (no `OnFailure=`). Fixing that is worthwhile and separate. It is not a reason to point the accounts unit at `backup_sync.py`.

An alert destination has to be named before either timer is installed. Until Leader names one, the only signal is a human reading `systemctl` and the journal, and that misses the exit-0 warning.

A test of the alert belongs in the milestone that adds it: force a permission failure and confirm exit 1 alerts; force a retention error and confirm the new backup remains while the warning alerts. Use temporary directories. Do not run that drill against `/var/backups/language-guard` or a live database.

## 3. Periodic restore verification without touching live databases

Add a later verification job that:

1. Selects the newest `study-sync-*.db` in the sync backup directory.
2. Restores it with `restore_database` to a new path under a verify directory, never to `/opt/language-guard/study_sync.db` and never to `accounts.db`.
3. Opens the restored copy read-only and requires `PRAGMA integrity_check` = `ok`.
4. Checks the restored schema is the supported version (currently 2) and that the expected vocabulary tables exist.
5. Deletes the restored copy when the check finishes.
6. Exits non-zero on a missing backup after the live database exists, on a restore error, or on a failed integrity check.

The job uses a new path each run because restore refuses an existing destination. It does not delete the backup it read. It does not run `VACUUM`, migrate, or write the source.

Run it on a different calendar from both backup timers, as `guard`, with the verify directory mode `0700` and empty at the start of the run. Skip the run while no `study-sync-*.db` exists and the live database has never existed. After activation, a week without a successful verify is a failed gate, not a quiet skip.

Local pytest remains the rehearsal. A production verify timer is a later install.

## 4. Staging environment isolation

Staging is a separate process with separate files. It is not the production unit with the flag flipped.

Required isolation:

- Separate tree, proposed `/opt/language-guard-staging`, and a separate backup directory. Separate systemd unit names.
- Synthetic accounts created there. Staging does not use production databases or production backups: no copy of production `accounts.db`, `study_sync.db`, or `/var/backups/language-guard`.
- Its own `.env` and its own credentials. Staging does not use the production API key, account database, session tokens, or backup storage credentials. `STUDY_SYNC_ENABLED=1` may exist only in that staging environment, and only during the drill that needs it. Production `.env` stays without that assignment.
- Bind only to localhost, on a port other than `8765`. Staging has no Caddy site, no public listener, and no public name on `langstudyguard.com`.
- AI calls in the staging drill use mocks. Staging does not call the production provider with the production key.
- `STUDY_SYNC_DIR` and `STUDY_SYNC_DB` inside staging point only at the staging tree.

Same-machine staging is the residual risk: a wrong path in the staging unit can open the production file. The pre-start check for the staging unit refuses to start when its database paths, `.env`, or backup directory resolve inside `/opt/language-guard` or `/var/backups/language-guard`. A separate host removes that class of mistake and is preferable when one is available. This plan does not provision a host.

Staging drill, when later authorized: package import with the flag unset creates no `study_sync.db`; login and a mocked AI route still answer; sync routes are 404 while the flag is off; with the flag on, a synthetic user can put, delete, and page changes; backup and restore of that staging file succeed; turning the flag off again returns 404 and leaves the staging database in place. Production paths are not arguments to that drill.

## 5. Safe server deployment sequence with the flag unset

`setup.sh` is the wrong tool for this step. It enables the account service and the accounts backup timer, reloads Caddy, and can rewrite `.env` when the API key check fails. A later dark deploy is a reviewed file copy plus a restart, after Leader authorizes that restart.

Sequence for that later milestone:

1. Record the running commit and confirm the tree to install contains `5f4251a` (or a descendant that still has this backup/restore behavior).
2. Read the effective flag from all three sources: `/opt/language-guard/.env`, the systemd unit `Environment=` lines, and drop-in overrides (`systemctl show language-guard.service -p Environment -p EnvironmentFiles` plus `systemctl cat`). `STUDY_SYNC_ENABLED` is absent or commented in every source. `STUDY_SYNC_DIR` is unset unless an earlier accepted decision chose a directory.
3. Run the existing accounts backup once and confirm a new `accounts-*.db` exists. Leave the accounts timer as it is.
4. Copy the server modules, including the sync import closure and `backup_sync.py`. Do not copy a new timer into `/etc/systemd/system` in this step. Do not replace `.env`.
5. Restart only `language-guard.service`.
6. Confirm the effective runtime flag. The process environment has no `STUDY_SYNC_ENABLED=1`, and the same is true of `.env`, the unit, and any override. `GET /` returns the usual health JSON, login and one existing AI route still answer, and each sync POST returns 404 `Không có chức năng này.`
7. Confirm `/opt/language-guard/study_sync.db` was not created by the restart.
8. Confirm `language-guard-backup.timer` is still the accounts unit and that no sync timer is enabled.

Stop the sequence if any check fails. Roll back by restoring the previous server files and restarting with the same `.env`. Do not delete a database to roll back a dark deploy. If `study_sync.db` does not exist, code rollback is file-only. If it ever exists, stay on a build that understands schema v2 (`94f1bf7` or later) so an older opener cannot treat the file as a new database.

## 6. Authentication, permissions, database path, and backup storage checks

Run these as read-only checks in the dark-deploy milestone and again immediately before any activation. This planning phase does not SSH to the VPS.

Authentication, from ADR-019, re-checked on the deployed code:

- Sync routes accept `Authorization: Bearer` only. Body `token` is not a sync credential.
- `user_id` comes from `account_store.user_for_token(token)` with no directory argument. JSON `user_id` does not choose the row owner.
- Missing, invalid, expired, and inactive sessions return 401 and do not open `study_sync.db`.
- Paths match exactly. A query string does not select a sync route.
- Error bodies stay the fixed strings. Logs stay exception type names, without paths, tokens, or provider keys.

Permissions and paths:

| Check | Pass condition |
|------|----------------|
| Service user | `guard`, system account, `nologin` |
| App tree | owned by `guard`, not writable by other users |
| `.env` file | mode `0600`, owner `guard` |
| Effective flag | `.env`, systemd `Environment=`, and drop-in overrides agree. No source sets `STUDY_SYNC_ENABLED` to `1`. The running process environment matches that result |
| `accounts.db` | owner `guard`, not world-readable, path still the accounts store |
| Sync path | server path and `backup_sync.py` source are the same file |
| Sync path location | under the app tree or an explicitly accepted data directory; not `/tmp`; not `accounts.db` |
| Backup directory | exists before the first timed run, owner `guard`, mode `0700`, dedicated to `study-sync-` files, same filesystem for the hard link |
| Backup contents | `study-sync-*` and `accounts-*` are in different directories after the dedicated-dir change; retention of one prefix cannot see the other directory |
| Live and backup | the live database path and the backup directory are different directories |
| Public edge | Caddy still proxies to `127.0.0.1:8765`. Activation would publish sync on the existing public HTTPS host, behind Bearer auth. There is no separate private port. |

## Mandatory off-box recovery gate

On-VPS retention alone is insufficient. `study-sync-*.db` files under `/var/backups/language-guard` are the same disk and the same machine as the live databases. They do not count as the recovery copy.

Before `STUDY_SYNC_ENABLED=1` on production, a later ops milestone must:

- Store a backup of `study_sync.db` (and the accounts backup taken with that activation) in a separate location from the VPS disk.
- Keep that copy access-controlled and encrypted.
- Complete a restore drill from that off-box copy onto a new path. The drill does not write the live `study_sync.db` or `accounts.db`.
- Show `PRAGMA integrity_check` = `ok` on the restored file and the supported schema version.

This planning document does not choose the store, the cipher, or the transport. The ops milestone that builds the gate resolves these decisions before activation:

| Decision | Resolve in the ops milestone |
|----------|------------------------------|
| Ownership | Who owns the off-box copies and who can approve a restore |
| Credential handling | Where the encryption and storage credentials live, who can read them, and how they stay out of the repo, the desktop app, and the account-server `.env` |
| Restoration responsibilities | Who runs a restore, which copy they start from, and who confirms the restored file before it is used |

Until that drill has succeeded, production sync stays off.

## First activation and cold start

If production `study_sync.db` does not exist yet, rehearse the full path on a synthetic schema-v2 database in an isolated environment: backup, then encrypted off-box copy, then restore onto a new path. That rehearsal is the cold-start proof. It uses no production vocabulary and no staging vocabulary.

After the first live sync database is created, its first on-box backup and its first off-box backup are both required within the approved RPO.

Staging vocabulary is never copied into the live database.

## Public API abuse-resistance gate

Activation would expose the sync POST routes on the public HTTPS host. Bearer authentication does not by itself bound request rate, stored vocabulary, or change history.

Before `STUDY_SYNC_ENABLED=1`, milestone 18B.10 must have implemented, tested, dark-deployed, and verified as effective:

- Per-account request limits on the sync routes.
- Per-account storage and change-history quotas.
- Disk exhaustion handling that fails a write cleanly, leaves `accounts.db` and the last good `study_sync.db` usable, and does not report a partial mutation as success.
- Safe HTTP monitoring: request counts, status codes, and payload sizes only. Monitoring does not record tokens, passwords, API keys, vocabulary text, or SQLite paths.

An accepted design alone is insufficient. The dark deploy of these controls needs its own Leader authorization and keeps `STUDY_SYNC_ENABLED` unset. Verification has to show the controls are effective on that deploy. This 18B.3 plan does not implement them. Milestone 18B.11 cannot start until that verification has passed.

## Operational health and effective-config gates

These are required before activation and are re-checked on every dark deploy.

**Recovery objectives.** Before activation, Leader chooses an RPO and an RTO for `study_sync.db`. The backup timer interval, the off-box copy interval, and the restore drill have to fit those numbers. Backup freshness is a health check: the newest on-VPS `study-sync-*.db` and the newest off-box copy are each younger than the chosen RPO once a live database exists. A stale copy is a failed gate.

**Disappearance.** After `study_sync.db` has been created once, a persistent check keeps noticing if that file is gone. The check survives a process restart and a timer gap. A missing file before first creation stays quiet. A missing file after first creation pages, including when `backup_sync.py` exits 0 because the source is absent.

**Retention warning.** Alert on the exact sentence `Retention cleanup failed; the new backup was kept.` even though the process exits 0. A unit in `success` state is not proof that retention ran.

**Effective flag.** The value that matters is the value the running process has. Check all of:

- `/opt/language-guard/.env` (loaded by `load_dotenv()`)
- `Environment=` in `language-guard.service`
- Drop-in overrides under the service's systemd override directory

Those sources and the process environment must agree. For a dark deploy they agree on unset. For a later activation they agree on exactly `1`, and rollback is not finished until every source and the process agree on unset again.

**Staging.** Staging binds only to localhost. It does not use production credentials, production databases, production backups, or public routing.

## 7. Feature activation prerequisites, rollback, and acceptance gates

`STUDY_SYNC_ENABLED=1` on production is its own later milestone. All of the following are true before that assignment:

1. Leader has accepted this plan and a separate authorization to activate.
2. The sync backup timer is installed, uses the dedicated directory, and has completed a soak with the flag still unset.
3. Alerting is proven for exit 1 and for the retention-warning sentence while the process still exits 0.
4. The restore-verification job has succeeded against a backup copy, with the live files untouched.
5. The staging drill in section 4 has passed on synthetic data. Staging bound only to localhost and used no production credentials, databases, backups, or public routing.
6. A fresh `accounts-*.db` backup exists, and the accounts timer is still healthy.
7. Dark deploy checks in sections 5 and 6 passed on the build that will stay running, including the effective flag across `.env`, systemd `Environment=`, and drop-in overrides.
8. The off-box recovery gate has passed: a separately stored, access-controlled, encrypted backup exists, and a restore drill from that copy succeeded onto a new path. On-VPS retention does not satisfy this gate. Ownership, credential handling, and restoration responsibilities were decided in that ops milestone. If production `study_sync.db` does not exist yet, that drill used a synthetic schema-v2 database in an isolated environment. Staging vocabulary was not copied into the live database.
9. Leader has chosen the RPO and RTO. Once a live `study_sync.db` exists, its first on-box backup and its first off-box backup are both inside that RPO, and later copies stay inside it. Persistent detection of a missing `study_sync.db` after first creation is in place.
10. Public API rate limits, per-account storage and change-history quotas, and disk-exhaustion protection are implemented, tested, dark-deployed under a separate Leader authorization, and verified effective. Safe HTTP monitoring meets the rule above. An accepted design alone does not satisfy this gate.
11. Desktop sync is still absent. Activation does not require a client, and a client is not turned on in the same change.
12. Windows Startup remains deferred and is not bundled into the activation.

Rollback after activation, when that milestone exists:

1. Remove `STUDY_SYNC_ENABLED=1` from `.env`, from systemd `Environment=`, and from every drop-in override. Restart `language-guard.service`.
2. Confirm the effective flag is unset in all of those sources and in the process environment, and that sync POSTs return 404.
3. Leave `study_sync.db` on disk. Rollback does not delete it, vacuum it, or restore over it.
4. Leave the sync backup timer running so the file keeps getting copied.
5. Login and AI routes keep using `accounts.db`. The accounts timer stays on `backup_accounts.py`.
6. History inspection restores a `study-sync-*.db` into a new path and opens that copy.

Acceptance gates before any Windows client milestone:

- Sections 1 through 3 are installed and have passed one soak interval on production with the flag still off, or Leader has accepted a written exception.
- Staging activation and the rollback restart have been exercised.
- Production activation has either completed and stayed healthy through one backup interval, or Leader has ordered client work against staging only.
- The client milestone has its own brief. It is not implied by closing 18B.3.
- Conflict behavior stays server-authoritative: stale `expected_revision` conflicts, tombstones stay deleted, `operation_id` retries match the whole mutation. The client brief has to honor that before upload code is written.
- Local study keeps working with the network absent.

## 8. Risks and recommended milestone breakdown

| Risk | Why it matters | When it is handled |
|------|----------------|--------------------|
| Retention warning exits 0 | systemd reports success while old backups accumulate | alerting milestone, without changing ADR-020 |
| Missing source also exits 0 | a deleted live file looks like “not created yet” | alert only after the live file has been observed |
| Shared backup directory | sync backup would chmod the accounts backup directory to `0700` | dedicated directory before any sync timer |
| Same-disk copies | VPS retention is the same disk as the live files | mandatory encrypted off-box copy and restore drill before activation |
| Unbounded public sync | a flagged-on route can exhaust requests, history, or disk | 18B.10 implements, tests, dark-deploys, and verifies the controls before 18B.11 |
| Flag hidden in an override | `.env` can look unset while a drop-in sets `STUDY_SYNC_ENABLED=1` | effective-config check across `.env`, the unit, overrides, and the process |
| Stale backup | a timer in `success` can still miss the RPO | RPO/RTO chosen before activation; freshness checked against them |
| `setup.sh` restarts production | a routine install enables units and can replace `.env` | dark deploy uses a reviewed copy, not `setup.sh` |
| `load_dotenv()` | one uncommented line in `.env`, or a systemd drop-in, activates public sync | effective flag across `.env`, the unit, overrides, and the process |
| Public HTTPS | the flag exposes sync on `langstudyguard.com`, not on a private port | activation is a separate authorization |
| Same-host staging | a bad path opens production `accounts.db` | path refusal in the staging unit; prefer another host |
| Hard link across filesystems | publish fails if the backup directory is a different volume from its own files | keep the temp file and the final name in one directory |
| Client before backups | vocabulary writes would have no restore point | Windows client stays after the gates in section 7 |
| Schema rollback | a pre-`94f1bf7` server must not open a v2 `study_sync.db` | roll back code only to a v2-capable build once the file exists |

Recommended milestones. Each one needs its own Leader authorization. None of them starts from this document.

| Milestone | Scope | Still true at the end |
|-----------|--------|------------------------|
| 18B.3 | Accepted planning document | No code, no VPS change. Does not authorize 18B.4 |
| 18B.4 | Repo-only sync timer, dedicated backup directory, failure and retention-warning alerts. Tests use `tmp_path`. | Flag unset. Units not installed on the VPS |
| 18B.5 | Repo-only restore verification into a new path. Tests prove the live path is never the destination | No production job |
| 18B.6 | Staging tree and synthetic-account drill. Localhost only. No production credentials, databases, backups, or public routing | Production `.env` and databases untouched |
| 18B.7 | Authorized dark deploy of a `5f4251a` descendant | Flag unset, sync 404, no sync timer, accounts timer unchanged |
| 18B.8 | Authorized install of the sync backup timer and the verify job, flag still unset, then a soak. Includes persistent disappearance detection, retention-warning alerting despite exit 0, and backup freshness once an RPO is chosen | No client, flag still off |
| 18B.9 | Off-box recovery ops. Separately stored, access-controlled, encrypted backup and a successful restore drill. If no live `study_sync.db` exists, the drill uses a synthetic schema-v2 database in isolation. Resolves ownership, credential handling, and restoration responsibilities. On-VPS retention does not pass this milestone | Flag still unset. No production activation. No staging data copied to production |
| 18B.10 | Implement, test, and dark-deploy public API rate limits, per-account storage and change-history quotas, disk-exhaustion protection, and safe HTTP monitoring. Dark deploy needs its own Leader authorization. Verify the controls are effective | Flag still unset. An accepted design alone does not finish this milestone |
| 18B.11 | Authorized `STUDY_SYNC_ENABLED=1` only after 18B.9 and after 18B.10 is verified effective. Cold start follows the first-activation rule. Rollback in section 7 is rehearsed first on staging | No Windows client in that change |
| Later | Windows sync client | Its own brief, after the section 7 gates |

AI Local Reading/Listening remains the next major product priority after this sync sequence. It is not pulled forward into 18B.4–18B.11. Milestone 18B.4 is the next possible repo-only step and is not automatically authorized. Milestones 18B.4, 18B.5, and 18B.7 keep the reviewed scope. 18B.6 states the localhost and production-isolation rules. 18B.8 adds the health checks (freshness, disappearance, retention-warning alert). 18B.9 includes the cold-start rehearsal. 18B.10 must be implemented and verified effective before 18B.11.

## Out of scope for 18B.3

- Deploying, restarting the VPS, editing production `.env`, creating timers, or enabling units.
- Setting `STUDY_SYNC_ENABLED`.
- Implementing request limits, quotas, disk-exhaustion handling, off-box transfer, or monitoring in this planning phase. Those belong to later milestones, and 18B.10 must finish them before activation.
- Running backup or restore against production or developer AppData.
- Building a desktop client, an installer, or an executable.
- Changing `accounts.db`, ScreenGuard, or the deferred Windows Startup issue.
- Rewriting ADR-018, ADR-019, or ADR-020. A change to the exit-0 retention contract would be a new ADR.
