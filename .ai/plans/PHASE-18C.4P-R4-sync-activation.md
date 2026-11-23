# Phase 18C.4P-R4 — Production sync activation

Status: **SYNC ON, vocabulary A → VPS → B PASS — Owner confirmed** (`APP_18C4P_VOCAB_SYNC_MILESTONE_RECORDED`)  
Date: 2026-11-23  
Baseline: `59f0b4bfe218da895b3fbf218d1728a0ad28889f`

The flag is server-wide. This is a supervised pilot, not a public release.

## Account and service

`syncpilot_18c4p` is present and active. The password was not read. Live `accounts.db` integrity is `ok`. The account count is 3, unchanged by the restart.

`STUDY_SYNC_ENABLED=1` is set in `/etc/systemd/system/language-guard.service.d/10-sync.conf` and in the service `.env`. `language-guard.service` was restarted. The process environment contains `STUDY_SYNC_ENABLED=1`.

Local health and `https://langstudyguard.com/` return 200. All seven sync routes return 401 without a token. Port 8765 is not public. No new listener appeared. The accounts backup timer stays enabled. The sync backup timer stays disabled.

## First server row and backup

`study_sync.db` exists, schema 3, integrity `ok`. The synthetic account has one vocabulary row: Dutch `syncprobe` / `lab-marker`, revision 1, not deleted. No other account has vocabulary or change rows. The account count is still 3.

One-shot `backup_sync.py` as `guard` published `study-sync-20261123-163213-072149.db`, 86016 bytes, mode `0600`, directory mode `0700`. Backup integrity is `ok` and its schema is 3. The same restore verifier, run as `guard`, returned `VERIFIED`.

`language-guard-sync-verify.service` now runs as `guard` with primary group `lg-health`. A drop-in hides `/var/backups/language-guard` and bind-mounts only `study-sync` read-only at `/var/lib/language-guard-sync-view` inside that service. `ProtectSystem=strict`, `NoNewPrivileges=true`, and the `accounts.db` and `.env` masks remain. The host view directory stays empty. The service completed `VERIFIED`. `result.json` is mode `0640`, owner `guard:lg-health`, and the health collector can read its status. The backup file and directory remain mode `0600` and `0700`. The original unit is saved under `pre-18c4p-code`. The sync backup timer remains disabled.

`study_sync.db` is mode `0600`, owner `guard:guard`. No SQLite sidecar files were present. `language-guard.service` has `UMask=0077`, and the running process umask is `0077`. After restart, health and HTTPS return 200, the marker is unchanged, and Sync stays on.

## Machine A

The isolated client was open as `Language Guard — PRODUCTION`. The Owner completed the upload. Server state above is the evidence. Client Synced status was not re-read from the screen.

## Machine B

**PASS — Owner confirmed.** Both real Windows computers showed `syncprobe` / `lab-marker` for `syncpilot_18c4p`. No separate Machine B log or screenshot is stored.

The later backup `study-sync-20261123-171338-651159.db` is mode `0600`, schema 3, integrity `ok`. The verifier service returned `VERIFIED` for that file. The earlier backup remains in place. Production Sync stays on.

## Rollback

Remove the drop-in and the `STUDY_SYNC_ENABLED` line, run `systemctl daemon-reload`, and restart `language-guard.service`. Leave any `study_sync.db` and client outbox in place. Do not restore `accounts.db` automatically.
