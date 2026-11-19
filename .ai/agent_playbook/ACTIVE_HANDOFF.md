# Active handoff

Rolling coordination checkpoint. The detailed history remains in [current_state.md](../current_state.md), [roadmap.md](../roadmap.md), [Phase 18B.9 status](../plans/PHASE-18B.9-offbox-status.md), and [ADR-024](../decisions/ADR-024-offbox-age-drive.md). Do not treat a commit/merge as a live activation.

## 1. Checkpoint metadata

- Written: 2026-11-19.
- **CORRECTIVE INACTIVE VPS INSTALL — INSTALL PASS (static only).** Authorization exhausted.
- Merge source used: PR #15 / `adbc3d5f8fd71ee8a2d462d806dc4c4a91fd0241` (session docs tip `ed41f690d5a165ca37cb29cf908ceef566f4ddd0`).
- Historical executable-path audit remains **UNSAFE** (pre-fix evidence preserved). A **new** Owner-authorized post-fix read-only audit must report **PASS** before isolation/activation.

## 2. Last completed / accepted results

- Executable-path trust audit **ACCEPTED UNSAFE** (Issue #8 #7009010670 / Architect #7009128705) — preserved as historical evidence.
- Obsolete inactive tree `/opt/language-guard/offbox` left **untouched** (still present; units no longer reference it).
- **PR #15 SOURCE MERGED** earlier; design: [OFFBOX_RUNTIME_TRUST.md](../procedures/OFFBOX_RUNTIME_TRUST.md).
- **Owner-authorized corrective inactive write EXECUTED and reported:** `/opt/language-guard-offbox` installed `root:root` `0755`/`0644`, 15/15 D5A2D0-P1 module SHA MATCH; four `language-guard-offbox*` unit files replaced on disk (`root:root 0644`) with reviewed templates referencing `/usr/bin/python3 -I` and `/opt/language-guard-offbox`; all four remain inactive/not enabled; **no** `daemon-reload`/start/enable; account server unchanged. Classification: **INSTALL PASS** (static packaging only — not live isolation).

## 3. Next App task — Owner authorized, NOT YET EXECUTED

Exactly **ONE conditional VPS audit/config session** is now approved under [Issue #8 #7011582969](https://github.com/nguyenthaibinh19/EnglishApp/issues/8#issuecomment-7011582969): Gate A read-only post-fix executable-path, Python `-I` import and on-disk unit/drop-in audit; only on unequivocal Gate A PASS, Gate B **one** `systemctl daemon-reload` followed by read-only loaded unit config/state checks. STOP on any FAIL/UNSAFE/UNKNOWN; no fixes or retries. Return `APP_18B9_POSTFIX_CONFIG_AUDIT_RESULT` with one consolidated docs/Issue update. This **does not authorize** starting/enabling/restarting units, executing worker/helper, live isolation, backup/restore, age/OAuth/Drive, Cloud Sync or activation. The known deployed-layout `verify` path quirk is for a future source-maintenance task, not a VPS patch. Historical UNSAFE/D2/D3 FAIL remain unchanged.

## 4. STOP / boundaries

- The ONE corrective inactive-write authorization ([Issue #8 #7011064958](https://github.com/nguyenthaibinh19/EnglishApp/issues/8#issuecomment-7011064958)) is **exhausted** after the install report.
- No further SSH/VPS write or activation without fresh Product Owner approval.
- Phase 18B.9 **OPEN / PRODUCTION NOT READY**. D5A2D2/D5A2D3 **FAIL preserved**. AI-M4 **NOT AUTHORIZED**.
