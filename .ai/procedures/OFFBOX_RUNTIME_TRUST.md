# Phase 18B.9 — Offbox runtime trust layout (source design)

**Status (2026-11-19):** Source remediation (PR #15) is merged; corrective inactive install **INSTALL PASS**; post-fix Gate A **PASS** and Gate B **CONFIG PASS**. **PR #16 SOURCE MERGED — VPS PACKAGER NOT UPDATED** (`bf5442b`; frozen modules unchanged). **PRODUCTION UPLOAD ENTRYPOINT SOURCE MERGED — NOT DEPLOYED / NOT ACTIVATED** (PR #17 / `b6e515e`; source `2602105`; LF pin `cc9ce5b7…`): worker ExecStart targets `production_upload_worker.py` under `/opt/language-guard-offbox/deploy/hetzner/`. Packager `verify`/`verify-deps` pin the wrapper independently of D5A2D0-P1. Inactive encrypt-only exits non-zero (`INACTIVE_NOT_OFFBOX_EXIT=3`). Default remains inert without deliberate LoadCredential activation files. Frozen `backup_worker.main()` still refuses live-upload env. VPS tree not updated. Historical pre-fix executable-path audit remains **UNSAFE** ([Issue #8 #7009010670](https://github.com/nguyenthaibinh19/EnglishApp/issues/8#issuecomment-7009010670), Architect [#7009128705](https://github.com/nguyenthaibinh19/EnglishApp/issues/8#issuecomment-7009128705)). This document does **not** authorize enable/start, isolation, age/OAuth/Drive, or activation. See [OFFBOX_PRODUCTION_DEPLOYMENT_RUNBOOK.md](OFFBOX_PRODUCTION_DEPLOYMENT_RUNBOOK.md).

Historical D5A2D2/D5A2D3 **FAIL** preserved. Drive **NOT CONFIGURED**. Cloud Sync **OFF**. Production **NOT READY**.

## Problem (observed)

- `/opt/language-guard` is `guard:guard 0755` and writable by `guard` (not sticky).
- Root-owned leaves under `/opt/language-guard/offbox` can still be replaced via parent rename.
- Worker/helper templates previously used `/opt/language-guard/venv/bin/python`, whose symlink and `site-packages` are guard-controlled.

## Proposed trusted layout

| Path | Owner/mode (intended) | Role |
|---|---|---|
| `/opt` | `root:root 0755` | Ancestor (already root) |
| `/opt/language-guard-offbox` | `root:root 0755` | Dedicated execution root (sibling of app tree) |
| `/opt/language-guard-offbox/offbox/*.py` | `root:root 0644` | Frozen D5A2D0-P1 modules (unchanged bytes) |
| `/opt/language-guard-offbox/deploy/hetzner/production_upload_worker.py` | `root:root 0644` | Production orchestration wrapper (outside frozen modules; LF-only via `.gitattributes`; independent SHA pin) |
| `/usr/bin/python3` | system root-owned | Interpreter (`-I` isolated mode) |
| `/opt/language-guard` | unchanged `guard` app tree | Account server only; **no** offbox executables |
| `/opt/language-guard/accounts.db` | existing | Helper read-only data path (`LG_SOURCE_DB`) |
| `/var/lib/language-guard-backup` | `lg-backup:lg-backup 0700` | Worker state (unchanged) |
| `/var/lib/language-guard-helper` | `guard:guard 0700` | Helper audit (unchanged) |

Unit templates:

- Helper: `User=guard`, `ExecStart=/usr/bin/python3 -I /opt/language-guard-offbox/offbox/snapshot_helper.py`
- Worker: `User=lg-backup`, `ExecStart=/usr/bin/python3 -I /opt/language-guard-offbox/deploy/hetzner/production_upload_worker.py`
  (wrapper reuses frozen `backup_worker.run()`; default unit LoadCredential remains `oauth-refresh` only)

`setup.sh` opt-in `LG_INSTALL_OFFBOX=1` installs via
`install-execution-tree --dest /opt/language-guard-offbox --production` and
root-owns that tree. It must never nest the execution tree under `APP_DIR` and
must not chown it to `guard`. Offline/test installs omit `--production` and may
use a temporary destination; production mode requires the exact trusted root and
ancestry/symlink/ownership preflight before any copy.

Unit verification pins the **exact active directive contract** for all four
templates (section, key, exact value, multiplicity). Extra `Environment=`
entries (e.g. `LD_PRELOAD`), loosened sandbox settings (`ProtectSystem=no`,
`NoNewPrivileges=no`, `ReadWritePaths=/`), or
`InaccessiblePaths` removal/replacement fail closed. Unexpected executable
directives (`ExecStartPre`, …) and `EnvironmentFile=` remain rejected.
Comments/blank lines do not affect the contract. Path-trust classification requires resolved
interpreter identity, leaf+ancestor metadata, and ACL evidence; missing
metadata yields **UNKNOWN**, not PASS. Production destination preflight covers
ancestors **and** existing planned descendants (symlink / ownership / mode
drift), including correct-hash files with unsafe ownership, before any copy.

## Offline verification

```bash
python deploy/hetzner/install_offbox_packaging.py verify
python deploy/hetzner/install_offbox_packaging.py verify-deps
python -m pytest tests/test_offbox_runtime_trust.py tests/test_offbox_packaging.py tests/test_offbox_setup_boundary.py tests/test_offbox_integrity.py tests/test_offbox_import_smoke.py tests/test_production_upload_worker.py -q
```

## Corrective inactive VPS write (executed; authorization exhausted)

Cursor-reported under [Issue #8 #7011064958](https://github.com/nguyenthaibinh19/EnglishApp/issues/8#issuecomment-7011064958):

1. Staged approved source; ran `install-execution-tree --dest /opt/language-guard-offbox --production`; applied `root:root` `0755`/`0644`.
2. Replaced the four inactive unit files under `/etc/systemd/system` with reviewed templates (still **disabled/inactive**; **no** `daemon-reload`).
3. Left `/opt/language-guard` account-server tree/venv/`accounts.db` and obsolete `/opt/language-guard/offbox` untouched.
4. Static checks: 15/15 module hashes; unit SHA match; no guard/lg-backup-writable component under the new tree path; offbox units inactive.

**Post-fix audit completed (Cursor-reported):** Gate A PASS + Gate B CONFIG PASS. Manager configuration reloaded once; units remain inactive/not enabled. This is **not** live isolation PASS and **not** activation.

## Prohibited without new Owner authorization

Further SSH/VPS sessions, systemd enable/start/stop/restart, age install, OAuth/Drive provisioning, Cloud Sync, live isolation, backup/restore, and removal of the obsolete `/opt/language-guard/offbox` tree.