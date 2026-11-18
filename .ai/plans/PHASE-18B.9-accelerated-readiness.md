# Phase 18B.9 — Accelerated source-side readiness package

Status: **SOURCE MERGED — NOT DEPLOYED** (PR #13 / d6643e0).
Not deployed. Not production-ready. No VPS/SSH, unit enablement, Drive, or Cloud Sync.

Baseline at branch open: `3d8a2727baf0bf901b7a74db6ddd90369126ea17`.
Frozen offbox Python modules: **unchanged** (15/15 D5A2D0-P1 hashes).

## Delivered in this package

1. Reproducible packaging verifier/stager: `deploy/hetzner/install_offbox_packaging.py` (pinned D5A2D0-P1 inventory; local SHA256SUMS alone cannot authorize)
2. Disabled-by-default unit templates (stderr/journal separation; no StateDirectory on backup dir)
3. Proposed timer template (not enabled)
4. `setup.sh` opt-in via `LG_INSTALL_OFFBOX=1` → mandatory `install-app-tree` verify-before-copy (never enables offbox units)
5. Monitoring line helper template: `deploy/hetzner/offbox_report_lines.py` (not wired into health_report)
6. Runbooks/checklists under `.ai/procedures/OFFBOX_*.md`
7. Offline regression tests for packaging, tamper rejection, permissions markers, idempotency, incorrect configs, report lines

## Readiness matrix (source package)

| Area | Classification |
|---|---|
| A Packaging + SHA pin | **Completed and tested** (offline) |
| B Unit templates + isolation markers | **Completed and tested** (static/offline) |
| C setup.sh opt-in copy, no enable | **Completed and tested** (static) |
| D Monitoring/schedule templates | **Completed and tested** (offline helper; not installed) |
| E VPS Python / journal mode | **Requires live VPS evidence** |
| F Production age recipient/identity | **Requires Product Owner credentials/authorization** |
| G Production OAuth / Drive folder | **Requires Product Owner credentials/authorization** |
| H Unit install + isolation re-proof on VPS/WSL | **Requires live operations** (historical D2/D3 FAIL preserved) |
| I Clean-host restore drill | **Requires live operations** + owner identity |
| J Activation / timer enable / Drive line leave NOT CONFIGURED | **Requires Product Owner authorization** |

Overall: **NOT READY for production.** Offline tests do not claim production readiness.

## Historical failures preserved

D5A2D2 / D5A2D3 remain **FAIL** and are not rewritten by this package.
