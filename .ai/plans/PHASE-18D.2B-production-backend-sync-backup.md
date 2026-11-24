# Phase 18D.2B — Production backend and automatic Sync backup

Status: ready for architect review. Baseline `ee2ae7a67da5536f62bcdd94e7a0846fbf909c27`. Architect decision `APP_18D2A_ARCHITECT_ACCEPTED_CLOSED`. This is not a public release and not a real-account migration.

## Production preflight

Checked before any file was replaced. `language-guard.service` was active, started `2026-11-23T16:43:33Z`, with `STUDY_SYNC_ENABLED` exactly `1`. Local and public health were HTTP 200. Port 8765 listened on `127.0.0.1` only. Caddy proxies to that port and its file contains no timeout directive.

Deployed `sync_http.py` was `aa88f693764912f589a5945d7b3f154b587363311130b01295127cb600ddd5d1`. `study_sync.db` was 151,552 bytes, mode `0600`, integrity `ok`, schema 3. Account id 1 had 92 vocabulary entities, 0 learning attempts, and 0 progress rows. The newest vocabulary timestamp was `2026-11-24 13:04:40`. The protected local database file was not opened. Its size and mtime were still 221,184 bytes and `2026-11-24T13:04:32.9355334Z`, the same file that held 23 pending vocabulary operations and 6 pending progress events.

`language-guard-sync-backup.timer` was disabled and inactive. Its installed schedule was `04:45:00 UTC`, `Persistent=true`, `RandomizedDelaySec=10m`. `language-guard-sync-verify.timer` was enabled for `08:00:00 Europe/Amsterdam`, which is 07:00 UTC in November. The accounts backup timer stayed on its own `03:15` schedule with a 20-minute random delay. The verifier service runs as `guard` and reads the backup directory through the read-only bind at `/var/lib/language-guard-sync-view`. The host backup directory stayed mode `0700`.

The verified pre-deployment backup `study-sync-20261124-141131-698592.db` remained in place, 151,552 bytes, SHA-256 `fc76ffe479424deb77150e96d461bfa7710220c4ced3e244a6bd2416f32bf2d9`. The previous code rollback at `pre-18c4p-code/sync_http.py` was left untouched (`7b50069d9c42ab0aa3236959d4cbb0f8995ed1748f6582897d9b319bc8344d0f`). The files that were actually running were copied to `/var/backups/language-guard/pre-18d2b-code/` before replacement.

## Backend correction

A declared `Content-Length` only limits how many bytes are read. Caddy has no read timeout, and the account server socket blocks while those bytes arrive. `sync_http.py` now waits at most 15 seconds for a normal-sized body. A stall returns HTTP 408 `Sync request timed out.` and the connection is closed. The database is not opened for that stall.

Preserved: disabled Sync still returns 404, a missing token still returns 401, an oversized `Content-Length` still returns 413 before the database opens, authentication still happens before database access, the same seven Sync routes remain, and the schema and learning rows were not changed.

Focused regression: `tests/test_sync_api.py`, 17 passed. The new cases cover a stalled socket and a disabled-Sync stall. Both return within the shortened test deadline and do not open the Sync database.

Deployed LF files, then one restart of `language-guard.service`:

| File | SHA-256 |
|---|---|
| `sync_http.py` | `d173ad179ca9039a13489df0ce8ca81473ddfd711897fd803af96f60920f0dd2` |
| `account_server.py` | `dde08a9d2be6039947390437a05579325f20cfb93689f2a45506ebed77163e35` |

The service came back active at `2026-11-24T17:39:58Z` with zero restarts recorded. Local health and `https://langstudyguard.com/` returned HTTP 200. The Sync flag stayed exactly `1`. Port 8765 stayed on `127.0.0.1`. All seven Sync routes returned 401 `Authentication required.` without a token. An unknown login was rejected and the session count stayed 17. An oversized request returned 413. The existing desktop session received HTTP 200 for an empty vocabulary-changes page. Account id 1 stayed at 92 vocabulary entities, 0 attempts, and 0 progress rows. The live database stayed 151,552 bytes.

## Recurring backup

`language-guard-sync-backup.timer` is enabled and active. Its next elapse is `2026-11-25 04:47:46 UTC`, which is the 04:45 UTC schedule plus a delay inside the 10-minute random window. The verifier's next elapse is `2026-11-25 07:00:00 UTC`. The backup window ends before the verifier. The accounts backup timer was not edited. It remains enabled, and its next displayed elapse stayed inside the existing 03:15 plus 20-minute window. `LastTriggerUSec` for the Sync backup service is empty. The timer has not executed the backup.

One manual backup was run as `guard` through the existing script. It is not a scheduled timer run.

| Field | Value |
|---|---|
| File | `study-sync-20261124-174104-409289.db` |
| Size | 151,552 bytes |
| Mode | `0600`, directory `0700` |
| SHA-256 | `fc76ffe479424deb77150e96d461bfa7710220c4ced3e244a6bd2416f32bf2d9` |
| Integrity | `ok` |
| Schema | 3 |
| Account id 1 | 92 vocabulary entities, 0 attempts |

The checksum matches the 14:11 pre-deployment backup because the live database bytes did not change. Retention stayed at the existing limit of 14. Six Sync backup files are present. The verifier service returned `study_sync restore verification verified` at `2026-11-24T17:41:14Z` for this file. The live database size and mtime were unchanged. `result.json` is mode `0640` and is the record the existing health collector reads. Today's health report was already written before the timer was enabled, and `health-state.json` has no new Sync backup notice. The next scheduled report has not run.

## Still closed

- The already-built v1.5.0 candidate was not rebuilt. It still contains the synthetic emergency password and must not be published.
- A public ZIP must be named `langstudyguard.zip` and contain `langstudyguard.exe`.
- The 23 pending vocabulary operations and 6 pending progress events were not uploaded.
- No new production account and no new learning attempt were created.
- Phase 18B.9 stays paused. Google Drive was not enabled.
- Phase 18B.10B–E were not implemented.
- The other account routes were not given this read deadline. Only the Sync body read was bounded.
- The first natural 04:45 UTC timer execution has not occurred.
