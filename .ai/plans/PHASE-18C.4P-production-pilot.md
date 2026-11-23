# Phase 18C.4P — Direct production Cloud Sync pilot

Status: **BLOCKED** (`APP_18C4P_BLOCKED`)  
Date: 2026-11-23  
Decision: the blocked LAN/SSH two-PC test is replaced by a direct production pilot. This run did not activate Sync.  
Source checked: `7d21019ed970e54b6040857d61d145a06ec4a2f2`

18B.9 off-box backup stays **PAUSED**. 18B.10B–E stay **DEFERRED / NOT AUTHORIZED**. No staging host was created. No product launch is implied.

## 1. Production server readiness

The existing authorized VPS was inspected read-only. Nothing was installed, and no credential or unit file was changed.

| Check | Live result |
|-------|-------------|
| Account service | Active |
| Bind | `127.0.0.1:8765` only |
| Public health through that listener | 200, account server running |
| `STUDY_SYNC_ENABLED` in the process and in `.env` | Unset |
| `POST /api/sync/vocabulary/changes` | 404 |
| `study_sync.db` | Absent |
| Deployed git checkout | None. The application tree is a copied package |
| `account_server.py` | Matches approved source |
| Sync schema | `SCHEMA_VERSION = 2` |
| Sync routes present | Vocabulary put, delete, and changes |
| Sync routes absent | Progress accept, progress changes, preferences get, preferences put |
| `srs.py` | Absent |
| `account_sync_engine.py` | Absent, as expected on the server |

Approved source uses schema 3 and all seven routes. The deployed sync modules do not match that source. The untracked comparison is `diff/phase18c4p-production-sync-allowlist.diff`. It was not applied.

Files that differ and would have to move together: `sync_http.py`, `sync_store.py`, `account_store.py`, `sync_backup.py`, `config.py`, `vocab_identity.py`, `vocabulary_model.py`, `languages.py`, `text_utils.py`, `ai_teacher.py`, `listening.py`, `listening_content.py`, `reading_schema.py`, plus new `srs.py`. `account_server.py` already matches.

## 2. Data protection already present

`accounts.db` is 20480 bytes, integrity `ok`, 2 accounts. Today's backup `accounts-20261123-032141.db` matches that size, integrity `ok`, mode `0600`, in a `0700` backup directory. No account names or rows were copied here.

The accounts backup timer is enabled. The sync-backup timer is disabled. The sync-verify timer is enabled. There is no `study-sync-*.db` backup because the live sync database does not exist. Off-box backup remains paused, so this on-VPS accounts snapshot is not an off-box recovery copy.

Rollback if a later activation fails: unset `STUDY_SYNC_ENABLED`, restart the account service, leave any created `study_sync.db` in place, and do not restore `accounts.db` until writes since the snapshot are reviewed. That step was not needed because the flag was not set.

## 3. Why activation stopped

- The running server cannot perform progress, SRS, or preferences sync.
- Updating it is a production code deploy, including `account_store.py`, and was not applied.
- The installed production EXE at `%LOCALAPPDATA%\langstudyguard\langstudyguard.exe` is dated 2026-11-08 and does not contain the sync route strings.
- A source client in staging or development refuses `langstudyguard.com`.
- No second physical computer was available.
- The flag is server-wide. Turning it on could let a capable client upload the preserved real account. That upload was not authorized.

No deployment change was performed. Sync remains **OFF**.

## 4. Scenarios

| Scenario | Result |
|----------|--------|
| 1 Vocabulary A to B | **BLOCKED** |
| 2 Attempts, Progress, SRS, replay | **BLOCKED** |
| 3 Offline retry | **BLOCKED** |
| 4 Conflict resolution | **BLOCKED** |
| 5 Restart persistence | **BLOCKED** |
| 6 Account isolation | **BLOCKED** |

## 5. Before a later activation

1. Architect approval of the allowlisted module update, applied without copying the whole repository.
2. A fresh accounts snapshot and a plan for the new empty schema-3 sync database.
3. A production desktop build that contains the approved sync client, still pointed only at the existing HTTPS backend.
4. Two physical Windows computers and a new synthetic production account.
5. The real 114-word account and its outbox stay untouched until a separate Owner test is approved.
