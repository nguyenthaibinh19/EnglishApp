# Phase 18C.4P-R4 — Production sync activation

Status: **SYNC ON, CLIENT TEST OPEN** (`APP_18C4P_R4_SYNC_ACTIVATED_READY_FOR_TWO_PC_REVIEW`)  
Date: 2026-11-23  
Baseline: `59f0b4bfe218da895b3fbf218d1728a0ad28889f`

The flag is server-wide. This is a supervised pilot, not a public release.

## Account and service

`syncpilot_18c4p` is present and active. The password was not read. Live `accounts.db` integrity is `ok`. The account count is 3, unchanged by the restart.

`STUDY_SYNC_ENABLED=1` is set in `/etc/systemd/system/language-guard.service.d/10-sync.conf` and in the service `.env`. `language-guard.service` was restarted. The process environment contains `STUDY_SYNC_ENABLED=1`.

Local health and `https://langstudyguard.com/` return 200. All seven sync routes return 401 without a token. Port 8765 is not public. No new listener appeared. `study_sync.db` does not exist yet, because no authenticated sync has run. The accounts backup timer stays enabled. The sync backup timer stays disabled.

## Machine A

The isolated client is open, PID 38768, title `Language Guard — PRODUCTION`. Before launch the token was empty, the host was `langstudyguard.com`, and the data root was `D:\lg-18c4p-r3-data`.

Sign-in and the vocabulary upload are **UNVERIFIED**. The Owner does this in that window:

1. Click **Log in**.
2. Username `syncpilot_18c4p`. Type the password in the dialog. Do not paste it into chat.
3. Click **Sign in**.
4. Click **Add words**, choose Dutch, then **Add word**.
5. Word `syncprobe`, meaning `lab-marker`. Save.
6. Wait until the Account line says **Synced**.

No server vocabulary row is claimed yet. The one-shot `backup_sync.py` run waits until `study_sync.db` exists, and it will be run before 08:00 Europe/Amsterdam.

## Machine B

**UNVERIFIED.** On the second computer, use the R3 source client at `ed4e49ea8b977468d10869adec8d2ec3b494fe91`, an isolated data directory, production identity, and `https://langstudyguard.com`. Sign in as `syncpilot_18c4p` and wait at least 90 seconds. `syncprobe` / `lab-marker` should appear without copying a database.

## Rollback

Remove the drop-in and the `STUDY_SYNC_ENABLED` line, run `systemctl daemon-reload`, and restart `language-guard.service`. Leave any `study_sync.db` and client outbox in place. Do not restore `accounts.db` automatically.
