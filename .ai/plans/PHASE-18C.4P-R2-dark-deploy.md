# Phase 18C.4P-R2 — Production dark deploy

Status: **READY FOR ARCHITECT REVIEW** (`APP_18C4P_R2_DARK_DEPLOY_READY_FOR_ARCHITECT_REVIEW`)  
Date: 2026-11-23  
Checkpoint: `8760c9fbd532420005cfa268b93ef07fa1738be3`

Cloud Sync stays **OFF**. `study_sync.db` was not created. The desktop EXE was not launched.

## Hashes

| File | Saved original | Installed LF |
|------|----------------|--------------|
| `sync_http.py` | `7b50069d9c42ab0aa3236959d4cbb0f8995ed1748f6582897d9b319bc8344d0f` | `aa88f693764912f589a5945d7b3f154b587363311130b01295127cb600ddd5d1` |
| `sync_store.py` | `879f41b198b9c99321781b88e22f33ff327dad47c9aaff544c9c2faaba323f88` | `385f4971b9587eb03079bf769e4e6c75d275c752e8d98d203ad7ed55328fc865` |
| `srs.py` | absent | `25e9db7769b3ff15483c055cb03036199477395c358dfa317733acd892ea8a57` |
| `sync_restore_verify.py` | `813a1b0d5809775bd6cd4499f9112a5323c142769680b348885e5f7ed1dad455` | `d1ebd3e4a78e0e9f000495fbc3baa1b9c708dbc7ea7d197a58dc3490a2e26477` |

The three originals are in `/var/backups/language-guard/pre-18c4p-code/` with their previous mode and owner. `sync_http.py` and `sync_store.py` are `guard:guard` mode `0644`. `sync_restore_verify.py` is `root:root` mode `0644`. New `srs.py` matches the guard-owned sync modules.

## Snapshot

`accounts-20261123-154201.db`  
20,480 bytes, mode `0600`, owner `guard:guard`  
Integrity `ok`, 2 accounts, same count as the live file.  
SHA-256 `2b75e93830dbb4ef010eaedbe9a7cd19f4b9a00752fa3b00d01405e6e7bcf470`

The accounts backup timer stayed enabled. No database contents were copied here.

## Runtime

The production venv, Python 3.14.4, imported the four modules. Schema version is 3 and seven sync routes are present. That import did not change `accounts.db` and did not create `study_sync.db`.

`language-guard.service` was restarted and is active. Local health is HTTP 200 from Python 3.14.4. `https://langstudyguard.com/` returns 200. All seven sync routes return 404. The process environment has no `STUDY_SYNC_ENABLED`, and `.env` has no such line. No new public listener appeared.

Timers: accounts backup enabled, sync backup disabled, sync verifier enabled. A verifier run printed `study_sync restore verification skipped`.

The first restart probe raced the listen socket and restored the old files. The service was healthy on that previous code. The same four files were installed again, and the checks above are from that second restart. The final files are the approved LF hashes. No further rollback is in effect.

Sync flag: **unset**. Do not set `STUDY_SYNC_ENABLED=1` from this result.
