# Active handoff

Rolling coordination checkpoint. See [current_state.md](../current_state.md), [HETZNER-LOGIN-API-READONLY-INSPECTION.md](../plans/HETZNER-LOGIN-API-READONLY-INSPECTION.md), and [PRODUCTION-LOGIN-API-COMPATIBILITY.md](../plans/PRODUCTION-LOGIN-API-COMPATIBILITY.md).

## 1. Checkpoint metadata

- Written: 2026-11-19 (Hetzner production login hotfix **DEPLOYED**).
- Tag: `APP_HETZNER_LOGIN_HOTFIX_DEPLOYED` (UTC `2026-11-19T23:02:32Z`).
- Replaced only `/opt/language-guard/account_server.py` → SHA-256 `4101e111abee9400217334b468901c5e033c6be1fa79be7ba189c72f749685b9`.
- Source: approved commit `4f339c9` (CRLF bytes matching Owner expected hash; identical to git LF blob ignoring newlines).
- Cloud Sync **OFF**. Rollback **NOT NEEDED**. Service active; health HTTP 200.
- **Product Owner** performs final authenticated RC login smoke manually.
- **18C.1 / 18C.2 CLOSED**. **18B.9 PAUSED, NOT CLOSED**. Staging **RESERVED**. Sync pilot **NO-GO**.

## 2. Last results

- Pre-gates matched inspection (old SHA `1662fb3b…`).
- Backups under `/var/backups/language-guard/hotfix-login-20261119-230232/` (server file + sqlite backup, integrity `ok`).
- Unrelated files unchanged (`account_store.py`, `sync_http.py`).

## 3. Next

1. Owner RC login smoke (manual).
2. No further VPS changes unless Owner/Architect authorize.
3. Do not enable `STUDY_SYNC_ENABLED` or resume 18B.9 from this handoff.

## 4. STOP / boundaries

- STOP after hotfix report — no new milestone.
