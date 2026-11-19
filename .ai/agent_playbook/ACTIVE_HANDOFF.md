# Active handoff

Rolling coordination checkpoint. The detailed history remains in [current_state.md](../current_state.md), [roadmap.md](../roadmap.md), [Phase 18B.9 status](../plans/PHASE-18B.9-offbox-status.md), and [ADR-024](../decisions/ADR-024-offbox-age-drive.md). Do not treat a commit/merge as a live activation.

## 1. Checkpoint metadata

- Written: 2026-11-19.
- Docs tip before this update: `bf9107e8a21d5344aadeedaf95c73347b30848b4`. This documentation update advances `main`; do not use that SHA as current HEAD after push.
- **Last completed Owner-authorized VPS session:** ONE read-only executable-path trust audit — **UNSAFE** ([Issue #8 #7009010670](https://github.com/nguyenthaibinh19/EnglishApp/issues/8#issuecomment-7009010670)). Authorization exhausted.

## 2. Last completed / accepted results

- **App AI conformance tests MERGED** (PR #14 / `6692dfd`); canonical `C-APP-AI-001` wire contract **v0.2.0 ACCEPTED**; `LocalAIProvider`, AI-M4 and local App routing **NOT AUTHORIZED / NOT IMPLEMENTED**.
- **18B.9 source integration MERGED** (PR #12 / `c03a0f5`); **accelerated packaging source MERGED** (PR #13 / `d6643e0`). Source merges alone are not deployments.
- Cursor-reported **VPS prerequisites read-only probe** completed: Python 3.14.4; SQLite journal `delete`; `guard` 995/982; `lg-backup` 994/977. Architect accepted *reported evidence*, no independent SSH rerun.
- Cursor-reported **one inactive VPS packaging write** completed (Issue #8 #7008470434): verified 15/15 pinned offbox module hashes on host; root-owned `0644` leaf modules in `/opt/language-guard/offbox`; `guard:guard 0700` helper directory; four systemd units copied but **not daemon-reloaded, started or enabled**. Architect accepted *inactive install scope only* (Issue #8 #7008526944).
- **Executable-path trust audit COMPLETED — UNSAFE (observed, not assumed).** Host `ubuntu-4gb-fsn1-1`; docs SHA at audit `bf9107e…`; SSH exit 0; metadata only. Key observations: `/opt/language-guard` is `guard:guard 755` and `test -w` as `guard` = YES (not sticky); `/opt/language-guard/offbox` and leaf modules are `root:root` with `test -w` as `guard` = NO, but guard can rename/replace the `offbox` directory entry via the writable parent; worker `ExecStart` uses `/opt/language-guard/venv/bin/python` → `python3` → `/usr/bin/python3.14` (resolved target `root:root 755`, safe leaf); `venv`, `venv/bin`, and `site-packages` are `guard:guard` with `test -w` as `guard` = YES; no shared groups; ACLs match unix modes. Install-time 15/15 root leaf hashes do **not** establish runtime path integrity. Historical D5A2D2/D5A2D3 **FAIL preserved**. Details: [OFFBOX_VPS_PREREQUISITES.md](../procedures/OFFBOX_VPS_PREREQUISITES.md).

## 3. Next App task

Phase 18B.9 P0 remains: separately authorize a **corrective ownership/layout write** (or equivalent) so `lg-backup` cannot execute guard-replaceable interpreter/code paths; then re-audit read-only. **No** live isolation, age/OAuth/Drive, or activation without new Owner approval.

## 4. STOP / boundaries

- The read-only audit authorization is **exhausted**. No further VPS operations without new Owner approval.
- Phase 18B.9 **OPEN / PRODUCTION NOT READY**. Offbox units installed **inactive**; Google Drive **NOT CONFIGURED**; Cloud Sync **OFF**; historical D5A2D2/D5A2D3 **FAIL preserved**. Windows Startup `--lock` hotfix still deferred.
- **AI-M4 / LocalAIProvider NOT AUTHORIZED.** Do not shift the App roadmap priority without Owner decision.
