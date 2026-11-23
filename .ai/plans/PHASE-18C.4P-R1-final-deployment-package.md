# Phase 18C.4P-R1 final deployment package

Status: **READY FOR REVIEW** (`APP_18C4P_R1_FINAL_DEPLOYMENT_PACKAGE_READY_FOR_REVIEW`)  
Date: 2026-11-23  
Desktop smoke: **BLOCKED before launch**

Nothing was deployed. No timer was enabled or restarted. Production Sync stays off.

## 1. Four-file manifest

Write these LF bytes into `/opt/language-guard`. `account_server.py` stays. The accounts backup timer stays.

| Target | Current deployed SHA-256 | LF SHA-256 to install |
|--------|--------------------------|------------------------|
| `sync_http.py` | `7b50069d9c42ab0aa3236959d4cbb0f8995ed1748f6582897d9b319bc8344d0f` | `aa88f693764912f589a5945d7b3f154b587363311130b01295127cb600ddd5d1` |
| `sync_store.py` | `879f41b198b9c99321781b88e22f33ff327dad47c9aaff544c9c2faaba323f88` | `385f4971b9587eb03079bf769e4e6c75d275c752e8d98d203ad7ed55328fc865` |
| `srs.py` | absent | `25e9db7769b3ff15483c055cb03036199477395c358dfa317733acd892ea8a57` |
| `sync_restore_verify.py` | `813a1b0d5809775bd6cd4499f9112a5323c142769680b348885e5f7ed1dad455` | `d1ebd3e4a78e0e9f000495fbc3baa1b9c708dbc7ea7d197a58dc3490a2e26477` |

There is no `/opt/language-guard/app/` copy of these modules. The verifier script imports the flat file.

Dependencies, all already on the server except `srs.py`: `account_store`, `languages`, `vocab_identity`, `vocabulary_model`, and `sync_backup`. Those stay. `srs.py` uses only the standard library. No new package. The service venv is Python **3.14.4**. The synthetic upgrade earlier ran on Python **3.13.13** and was not repeated on 3.14.4.

## 2. Backup and verifier

Live units, unchanged by this task:

| Unit | State | Role |
|------|-------|------|
| `language-guard-backup.timer` | enabled, active, 03:15 | `accounts.db` only. Leave it. |
| `language-guard-sync-backup.timer` | disabled, inactive | Do not enable. |
| `language-guard-sync-verify.timer` | enabled, active, 08:00 Europe/Amsterdam | Already runs. |

`deploy/hetzner/backup_sync.py` is present. It copies an existing `study_sync.db` with SQLite's online backup, checks integrity, and publishes `study-sync-YYYYMMDD-HHMMSS-ffffff.db` under `/var/backups/language-guard/study-sync`. A missing file exits 0 and does not create one. It does not read `STUDY_SYNC_ENABLED` and does not check the schema number.

While `study_sync.db` is absent, the verifier skips. That is not a failure. After the file exists, the same timer fails if the newest named backup is missing or if the verifier still expects schema 2. Deploying the schema-3 verifier before the file exists keeps the skip. One manual run of the existing backup script, before the next 08:00 Europe/Amsterdam, is the smallest way to give that timer a backup it can verify. The backup timer stays disabled.

## 3. Activation order

1. Run the existing accounts backup once. Confirm integrity. Leave the 03:15 timer as it is.
2. Save the three current files, mode `0600`, under `/var/backups/language-guard/pre-18c4p-code/`.
3. Install the four LF files while `STUDY_SYNC_ENABLED` is unset and `study_sync.db` is absent.
4. Restart `language-guard.service`. Health stays 200. Sync routes stay 404. The verifier still skips.
5. Set `STUDY_SYNC_ENABLED=1`, restart, and confirm the process environment. The flag is server-wide.
6. Let the synthetic clients create `study_sync.db`.
7. Before 08:00 Europe/Amsterdam, as `guard`:

```text
STUDY_SYNC_DB=/opt/language-guard/study_sync.db
STUDY_SYNC_BACKUP_DIR=/var/backups/language-guard/study-sync
/opt/language-guard/venv/bin/python /opt/language-guard/deploy/hetzner/backup_sync.py
```

8. Leave both sync timers as they are now: backup disabled, verifier enabled.

Rollback: remove `STUDY_SYNC_ENABLED`, restore the three saved files, delete `srs.py`, and restart. Leave `study_sync.db` and any `study-sync-*.db` in place. Do not restore `accounts.db` until writes after the fresh backup are reviewed. Do not delete client outboxes.

## 4. Desktop smoke

Candidate SHA-256 matches `2d59cbaeca36cef7d0a56c8d0e86aa61aa66a0e1646663b2a152669eec64c540`. It was not launched.

This build's manifest forces the production runtime. `install.prepare()` installs a production EXE when it is not already the installed path. The installed EXE and `langstudyguard.lnk` are both present, so this copy would show the existing-installation notice and exit. That is not in-place execution. `LG_RC_SMOKE=1` would run in place and use the real RC data directory. `LG_APP_ENVIRONMENT` cannot turn this frozen production build into staging. Safe in-place execution is not available on this computer.

The bundled emergency password is a placeholder, not the owner password. A frozen build also needs a signed-in token before it is ready. This candidate is not a release build. The real secret stays in the existing `build_exe.bat` path and is not embedded here.

## 5. Remaining blockers

- Architect approval before the four-file copy.
- Desktop in-place smoke is blocked on this computer.
- The second Windows computer still has no Cursor session.
- The real 114-word account stays untouched.
- 18B.9 stays paused. 18B.10B–E stay unauthorized.
