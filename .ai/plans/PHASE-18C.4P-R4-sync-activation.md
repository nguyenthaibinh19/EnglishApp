# Phase 18C.4P-R4 — Production sync activation

Status: **SYNC ON, first row stored, verifier service blocked** (`APP_18C4P_R4A_BLOCKED_VERIFIER_CANNOT_READ_BACKUP`)  
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

`language-guard-sync-verify.service` failed. `lg-verify` cannot list the mode `0700` backup directory, so the service treats the live database as having no backup. The sync backup timer remains disabled. The 08:00 verifier timer is still enabled and will hit the same permission failure. Production Sync stays on for the supervised Machine B test.

The live `study_sync.db` is mode `0644` in a mode `0755` application directory.

## Machine A

The isolated client was open as `Language Guard — PRODUCTION`. The Owner completed the upload. Server state above is the evidence. Client Synced status was not re-read from the screen.

## Machine B

**UNVERIFIED.** On the second computer, use the R3 source client at `ed4e49ea8b977468d10869adec8d2ec3b494fe91`, an isolated data directory, production identity, and `https://langstudyguard.com`. Sign in as `syncpilot_18c4p` and wait at least 90 seconds. `syncprobe` / `lab-marker` should appear without copying a database.

## Rollback

Remove the drop-in and the `STUDY_SYNC_ENABLED` line, run `systemctl daemon-reload`, and restart `language-guard.service`. Leave any `study_sync.db` and client outbox in place. Do not restore `accounts.db` automatically.
