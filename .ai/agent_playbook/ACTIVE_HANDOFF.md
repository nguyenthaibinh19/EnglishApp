# Active handoff

Rolling coordination checkpoint. See [current_state.md](../current_state.md), [HETZNER-LOGIN-API-READONLY-INSPECTION.md](../plans/HETZNER-LOGIN-API-READONLY-INSPECTION.md), and [PRODUCTION-LOGIN-API-COMPATIBILITY.md](../plans/PRODUCTION-LOGIN-API-COMPATIBILITY.md).

## 1. Checkpoint metadata

- Written: 2026-11-19 (Hetzner Account Server **read-only** login inspection complete).
- **Login compatibility source** — PR #24 **MERGED** (`62c567b`); production **not** updated by merge.
- **Inspection** — `APP_HETZNER_LOGIN_READONLY_INSPECTION_READY`; deployed `/api/login` is token-only; `/api/session` absent; Cloud Sync **OFF**.
- **NOT AUTHORIZED:** VPS deploy, service restart, DB writes, login probes, backups create/restore.
- **18C.1 / 18C.2 CLOSED**. **18B.9 PAUSED, NOT CLOSED**. Staging **RESERVED**. Sync pilot **NO-GO**.

## 2. Last results

- Service `language-guard.service` active; flat tree `/opt/language-guard` (not Git).
- Deployed `account_server.py` SHA matches git `599e473` (token-only login).
- `account_store.user_for_token` present — **`account_server.py`-only future hotfix assessed viable**.
- Accounts backup timer enabled; sync-backup timer disabled; `study_sync.db` absent.

## 3. Next

1. Architect review of inspection report.
2. Separate Owner authorization required before any production file replace / restart / login smoke.
3. Do not enable `STUDY_SYNC_ENABLED` or resume 18B.9 from this handoff.

## 4. STOP / boundaries

- No VPS writes, no public Release, no EXE replace, no Cloud Sync activation.
- STOP for Architect review — do not deploy.
