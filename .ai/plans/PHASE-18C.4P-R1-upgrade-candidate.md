# Phase 18C.4P-R1 — Production sync upgrade candidate

Status: **READY FOR ARCHITECT REVIEW** (`APP_18C4P_R1_UPGRADE_CANDIDATE_READY_FOR_ARCHITECT_REVIEW`)  
Date: 2026-11-23  
Source: `3332dc5d018b1d03b49bcd372dff6dc360afcc3f`  
Decision: direct production Cloud Sync stays the path. This run prepared the upgrade. It did not deploy it.

18B.9 remains **PAUSED**. 18B.10B–E remain **NOT AUTHORIZED**. No staging host. No product launch.

## 1. What to copy

The account service stays `/opt/language-guard`, user `guard`, `account_server.py serve`, bind `127.0.0.1:8765`. `account_server.py` already matches source and is not copied. The whole repository is not copied.

Ten of the fourteen modules are the same text as source once Windows CRLF is ignored. Replacing them would only change line endings. Leave these deployed files in place:

`account_store.py`, `sync_backup.py`, `vocab_identity.py`, `vocabulary_model.py`, `languages.py`, `text_utils.py`, `ai_teacher.py`, `listening.py`, `listening_content.py`, `reading_schema.py`.

`ai_teacher.py` is newline-only. The upgraded server imported successfully while the four deployed `ai/` modules stayed in place. Those four files still differ from source and are not in this copy.

Real content changes:

| File | Deployed SHA-256 | Source SHA-256 | Action |
|------|------------------|----------------|--------|
| `sync_http.py` | `7b50069d9c42ab0aa3236959d4cbb0f8995ed1748f6582897d9b319bc8344d0f` | `a3970550cc0cfb58124804135ed49ea0004e14b8a8de51c5d027b200bb3a5222` | Replace, write LF |
| `sync_store.py` | `879f41b198b9c99321781b88e22f33ff327dad47c9aaff544c9c2faaba323f88` | `3fc2292cc2a6d78dedd5e8e1f4e7edbb26e722278f34f3b0bfb35999d43e2985` | Replace, write LF |
| `srs.py` | absent | `eca45912b04de8747339c3b3e552ab728d8bc53fa5d5beaba2487e36592eb867` | Add, write LF |
| `sync_restore_verify.py` | `813a1b0d5809775bd6cd4499f9112a5323c142769680b348885e5f7ed1dad455` | `ff3639b8be4757c810f4ed41733eea5ac5ddc8b2259026319595c5b6e1c2621a` | Replace, write LF |

`sync_restore_verify.py` is outside the original fourteen. The enabled verifier on the server still requires schema 2. A schema-3 file would make that timer fail. The source verifier accepts the migrated synthetic file.

Held back, and included in the review diff so the change is visible:

| File | Reason |
|------|--------|
| `config.py` | Desktop environment identity. The deployed `config.py` imports the new sync modules. |
| `app_environment.py` | Absent on the server. Required only if `config.py` is replaced. |

No new third-party package. The new code uses the standard library. `python-dotenv` is already imported by the running server.

Exact text: untracked `diff/phase18c4p-r1-upgrade-allowlist.diff`.

## 2. Synthetic upgrade

Databases lived under `D:\lg-18c4p-r1-lab`. Production was not opened.

| Check | Result |
|-------|--------|
| Old modules create `accounts.db` and schema-2 `study_sync.db` | PASS, integrity `ok`, 1 synthetic user, vocabulary revision 1 |
| New `account_store.py` opens that accounts file | PASS, schema SQL unchanged, integrity `ok`, login returns that user |
| New `sync_store.connect` on the schema-2 file | PASS, version 3, same vocabulary row kept, integrity `ok` |
| First-time sync database | PASS, version 3 |
| Sync flag unset, all seven routes | PASS, HTTP 404, no sync file created, existing file mtime and size unchanged |
| Flag on: vocabulary put, changes, delete | PASS, 200 |
| Flag on: progress accept twice with one `event_id` | PASS, 200, same change, `server_seq` 1 |
| Flag on: progress changes, preferences get, preferences put | PASS, 200 |
| Source verifier on the migrated file | PASS |
| Deployed verifier on the migrated file | `unsupported schema` |
| New `config.py` without `app_environment.py` | Import fails |
| Deployed `config.py` with the new sync modules | Import succeeds, seven routes, schema 3 |

## 3. Desktop candidate

The existing production spec is `DutchGuard.spec`, invoked with PyInstaller 6.22.3. `build_exe.bat` was not used: it reads the developer `.env` and writes `dist\langstudyguard.exe` in the repository.

Candidate, not installed:

`D:\lg-18c4p-r1-candidate\dist\langstudyguard.exe`  
36,227,913 bytes  
SHA-256 `2d59cbaeca36cef7d0a56c8d0e86aa61aa66a0e1646663b2a152669eec64c540`

The packaged archive contains `build_manifest.json` with channel `production`, version `1.4.0`, and commit `3332dc5d018b1d03b49bcd372dff6dc360afcc3f`. It contains `bundled_secrets.json` with the production HTTPS account host and a placeholder emergency password that is not the owner password. The `.env` API key, emergency password, and account URL are not that bundled document. Packaged `sync_http` contains all seven `/api/sync/` routes, plus `account_sync_engine`, `account_sync_client`, and `account_local_store`.

The EXE was not launched. Production and RC metadata are unchanged: the installed EXE is still the 2026-11-08 file of 36,050,859 bytes, and the RC `account_study.db` is still 196,608 bytes from 2026-11-22. No outbox was imported, deleted, or reset.

## 4. Activation sequence, not executed

1. Run the existing accounts backup once more. Check `PRAGMA integrity_check` and keep the file mode `0600` in the `0700` backup directory. Record the name. Do not copy it off the VPS into git or the lab.
2. Save the current `sync_http.py`, `sync_store.py`, and `sync_restore_verify.py` under `/var/backups/language-guard/pre-18c4p-code/` mode `0600`. Copy only the four LF files above into `/opt/language-guard` as `guard`. Do not copy the rest of the repository.
3. Restart `language-guard.service` with `STUDY_SYNC_ENABLED` still unset. Health must stay 200. All seven sync routes must stay 404. `study_sync.db` must stay absent. Login on the existing accounts must still answer.
4. Confirm the running process environment still has no `STUDY_SYNC_ENABLED=1`, and that unrelated listeners were not added.
5. Only after that: set `STUDY_SYNC_ENABLED=1` in the service environment, restart, and confirm the process environment. This flag is server-wide. Any client that already speaks sync can use it, including a future client signed into the real account.
6. Create one new synthetic production account. Test two desktop candidates against `https://langstudyguard.com`. Do not use the preserved real account.
7. Stop before any real-account upload, import, or outbox change.

## 5. Rollback

Code rollback: restore the three saved files, remove `srs.py`, restart `language-guard.service`. Confirm the sync routes are 404.

Flag rollback: remove `STUDY_SYNC_ENABLED`, restart, and confirm the process environment. Leave any created `study_sync.db` in place. Do not delete client outboxes.

Database rollback is separate. Do not restore `accounts.db` until writes since the fresh backup are reviewed. Do not restore a sync backup onto the live path.

## 6. Still required from the Owner

Cursor access to the second Windows computer, then the two synthetic clients. The real 114-word account stays untouched.
