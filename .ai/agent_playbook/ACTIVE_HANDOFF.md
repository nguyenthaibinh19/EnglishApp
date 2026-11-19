# Active handoff

Rolling coordination checkpoint. The detailed history remains in [current_state.md](../current_state.md), [roadmap.md](../roadmap.md), [Phase 18B.9 status](../plans/PHASE-18B.9-offbox-status.md), and [ADR-024](../decisions/ADR-024-offbox-age-drive.md). Do not treat a commit/merge as a live activation.

## 1. Checkpoint metadata

- Written: 2026-11-19.
- **SOURCE INSTALLED INACTIVE — NOT ACTIVATED** (`APP_18B9_INACTIVE_VPS_PACKAGING_SYNC`).
- Approved GitHub main: `eb869eaf310504862a10c902ea2e8803fbab0b53` (PR #16 + #17).
- VPS host: `ubuntu-4gb-fsn1-1`.
- Rollback: `/root/lg-offbox-rollback-20261119T174614Z-eb869ea`.
- Historical pre-fix audit **UNSAFE**; D5A2D2/D5A2D3 **FAIL** preserved.

## 2. Last completed / accepted results

- **VPS packaging sync PASS (static):** packager `verify`/`verify-deps` from installed tree; frozen 15/15; wrapper pin `cc9ce5b7…`; worker unit on disk → `production_upload_worker.py`; units inactive/disabled.
- Changed on VPS: `install_offbox_packaging.py`, new `production_upload_worker.py`, `language-guard-offbox-worker.service` (tree + `/etc/systemd/system`).
- **No** `daemon-reload` / start / enable. On-disk worker unit matches approved template; manager was not reloaded in this session.
- Distinctions: installed ≠ enabled ≠ operational; credentials still unprovisioned.

## 3. Next App task

1. **NOT AUTHORIZED without new Owner approval:** `daemon-reload`, age binary/recipient, OAuth/Drive credentials, synthetic isolation, restore drill, monitoring wiring, timer activation.
2. Runbooks: [OFFBOX_PRODUCTION_DEPLOYMENT_RUNBOOK.md](../procedures/OFFBOX_PRODUCTION_DEPLOYMENT_RUNBOOK.md), [OFFBOX_OAUTH_CREDENTIALS_RUNBOOK.md](../procedures/OFFBOX_OAUTH_CREDENTIALS_RUNBOOK.md), [OFFBOX_RUNTIME_TRUST.md](../procedures/OFFBOX_RUNTIME_TRUST.md).

## 4. STOP / boundaries

- No further SSH/VPS beyond this exhausted sync authorization without new Owner approval.
- Phase 18B.9 **OPEN / PRODUCTION NOT READY**. Drive **NOT CONFIGURED**. Cloud Sync **OFF**.
