# Active handoff

Rolling coordination checkpoint. The detailed history remains in [current_state.md](../current_state.md), [roadmap.md](../roadmap.md), [Phase 18B.9 status](../plans/PHASE-18B.9-offbox-status.md), and [ADR-024](../decisions/ADR-024-offbox-age-drive.md). Do not treat a commit/merge as a live activation.

## 1. Checkpoint metadata

- Written: 2026-11-19.
- Last verified `EnglishApp/main` before this documentation update: `f99e73cf01a599425cbc66dd84f5ed53d154a2b4` (PR #14 merge + handoff tip). This documentation update advances `main`; do not use this historical SHA as current HEAD.
- **Active Product Owner authorization:** [Issue #8 comment #7008591938](https://github.com/nguyenthaibinh19/EnglishApp/issues/8#issuecomment-7008591938) for **ONE READ-ONLY executable-path trust audit**. **Authorized, not yet reported or completed.**

## 2. Last completed / accepted results

- **App AI conformance tests MERGED** (PR #14 / `6692dfd`); canonical `C-APP-AI-001` wire contract **v0.2.0 ACCEPTED**; `LocalAIProvider`, AI-M4 and local App routing **NOT AUTHORIZED / NOT IMPLEMENTED**.
- **18B.9 source integration MERGED** (PR #12 / `c03a0f5`); **accelerated packaging source MERGED** (PR #13 / `d6643e0`). Source merges alone are not deployments.
- Cursor-reported **VPS prerequisites read-only probe** completed: Python 3.14.4; SQLite journal `delete`; `guard` 995/982; `lg-backup` 994/977. Architect accepted *reported evidence*, no independent SSH rerun.
- Cursor-reported **one inactive VPS packaging write** completed (Issue #8 #7008470434): verified 15/15 pinned offbox module hashes on host; root-owned `0644` leaf modules in `/opt/language-guard/offbox`; `guard:guard 0700` helper directory; four systemd units copied but **not daemon-reloaded, started or enabled**. Architect accepted *inactive install scope only* (Issue #8 #7008526944).
- **NEW UNRESOLVED SECURITY GATE:** Actual `/opt/language-guard` ancestor, venv interpreter symlink target and import dependency path write/rename permissions **UNKNOWN**. `setup.sh` historically `chown -R guard:guard` and the backup worker runs as `lg-backup` from the app venv. Root-owned leaf modules do NOT alone establish worker code trust. This is a hypothesis to verify, not a confirmed exploit.

## 3. Next approved App task

**Phase 18B.9 P0 — ONE read-only SSH executable-path trust audit**, using [OFFBOX_VPS_PREREQUISITES.md](../procedures/OFFBOX_VPS_PREREQUISITES.md), the Owner's exact Issue #8 authorization and Architect's finding. Report `APP_18B9_EXEC_PATH_READONLY_AUDIT_RESULT` as `PASS` / `UNSAFE` / `UNKNOWN`; metadata only (including resolved interpreter/import ancestry, ACL and effective access). Update Issue #8 and source documentation with **actual results**; no automatic fixes.

## 4. STOP / boundaries

- The read-only authorization is **not** a write, `daemon-reload`, service execution, isolation proof, age install, recipient/OAuth/Drive, backup/restore or activation authorization. Any such work requires new Owner approval.
- Phase 18B.9 **OPEN / PRODUCTION NOT READY**. Offbox units installed **inactive**; Google Drive **NOT CONFIGURED**; Cloud Sync **OFF**; historical D5A2D2/D5A2D3 **FAIL preserved**. Windows Startup `--lock` hotfix still deferred.
- **AI-M4 / LocalAIProvider NOT AUTHORIZED.** Do not shift the App roadmap priority without Owner decision.
