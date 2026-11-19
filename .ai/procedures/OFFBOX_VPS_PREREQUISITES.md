# Phase 18B.9 — VPS prerequisites and executable-path audit

**Status (2026-11-19):** The first read-only prerequisites probe, the first inactive packaging install, the Owner-authorized **executable-path trust audit** (**UNSAFE**, preserved), and the Owner-authorized **corrective inactive VPS install** (**INSTALL PASS**, static only) have been completed **as reported by Cursor**. Audit authorization: [Issue #8 #7008591938](https://github.com/nguyenthaibinh19/EnglishApp/issues/8#issuecomment-7008591938); audit result: [#7009010670](https://github.com/nguyenthaibinh19/EnglishApp/issues/8#issuecomment-7009010670); corrective write authorization: [#7011064958](https://github.com/nguyenthaibinh19/EnglishApp/issues/8#issuecomment-7011064958) (**exhausted**). Conditional post-fix audit + one daemon-reload were Owner-authorized and are now exhausted. This document does not authorize service execution, isolation proof, age/OAuth/Drive, or activation.

**Phase 18B.9 is OPEN; production NOT READY; Drive NOT CONFIGURED; Cloud Sync OFF.** Historical D5A2D2/D5A2D3 FAIL stays recorded.

## Completed evidence (not reauthorized by this file)

- First prerequisites probe (Cursor-reported; Architect did **not** rerun SSH): production venv/system Python `3.14.4`, `accounts.db` `PRAGMA journal_mode=delete` via SQLite read-only URI; VPS `guard` UID/GID `995/982`, `lg-backup` `994/977`; backup dir `lg-backup:lg-backup 0700` empty; offbox units, age, recipient and OAuth refresh initially absent. See [Issue #8 review #7008262047](https://github.com/nguyenthaibinh19/EnglishApp/issues/8#issuecomment-7008262047).
- One inactive packaging **write** session (Cursor-reported): source `f99e73cf01a599425cbc66dd84f5ed53d154a2b4`; `VERIFY_OK modules=15 units=4 inventory=D5A2D0-P1`; `/opt/language-guard/offbox` 15 module SHA-256 matches, leaf files `root:root 0644` and directory `0755`; `/var/lib/language-guard-helper` created `guard:guard 0700`; four unit files copied to `/etc/systemd/system` `root:root 0644`, **not daemon-reloaded, enabled or started**. Existing app and timer unchanged. See [Issue #8 install #7008470434](https://github.com/nguyenthaibinh19/EnglishApp/issues/8#issuecomment-7008470434) and [Architect review #7008526944](https://github.com/nguyenthaibinh19/EnglishApp/issues/8#issuecomment-7008526944).
- The first post-install permissions checker falsely treated root-owned leaf `0644` as unsafe because root can write; a corrected **read-only** check confirmed 15/15 hashes. That check still did **not** prove runtime path safety.
- **Executable-path trust audit (ONE read-only SSH, exit 0; docs SHA `bf9107e…`; host `ubuntu-4gb-fsn1-1`): UNSAFE.** Observed metadata (not prior assumptions):
  - Identities: `guard` 995/982 groups=`guard` only; `lg-backup` 994/977 groups=`lg-backup` only; no shared supplementary groups.
  - `namei -l` / `stat`: `/opt` `root:root 755`; `/opt/language-guard` **`guard:guard 755`**; `/opt/language-guard/offbox` `root:root 755`; leaf `backup_worker.py` / `snapshot_helper.py` `root:root 644`.
  - Effective write (`runuser` + `test -w`, no probe files): `guard` **YES** on `/opt/language-guard`, `/opt/language-guard/venv`, `/opt/language-guard/venv/bin`, and `…/site-packages`; `guard` **NO** on offbox dir/leaves and on `/usr/bin/python3.14`; `lg-backup` **NO** on all of those paths.
  - Parent `/opt/language-guard` is writable by `guard` and **not sticky**, so `guard` can rename/replace the `offbox` directory entry even though current leaves are root-owned.
  - Interpreter chain: `/opt/language-guard/venv/bin/python` (`guard:guard` symlink) → `python3` → `/usr/bin/python3` → `/usr/bin/python3.14` (`root:root 755` under root-owned `/usr/bin`). Resolved system interpreter leaf is safe; the **venv symlink parents are not**.
  - `venv` / `venv/bin` / `venv/lib/python3.14/site-packages` are `guard:guard 755`; site-packages contents are guard-owned. `pyvenv.cfg`: `home=/usr/bin`, `include-system-site-packages=false`, `version=3.14.4`.
  - `getfacl` present; ACL entries match owner/group/other unix modes (no extra ACL grants observed).
  - Note: `test -w` on the `venv/bin/python` symlink reported NO for `guard` because that query follows to the root-owned target; replaceability of the symlink itself is still YES via writable `venv/bin`.

## Why the additional read-only check was required

Systemd `language-guard-offbox-worker.service` runs as `lg-backup` but executes `/opt/language-guard/venv/bin/python /opt/language-guard/offbox/backup_worker.py`. The helper runs as `guard` using the same interpreter. In the source, `deploy/hetzner/setup.sh` contains `chown -R guard:guard /opt/language-guard`. Root ownership of leaf modules alone does not prevent replacement when a less-trusted principal can write/rename a parent directory or retarget the interpreter/import path.

## Audit classification criteria (retained)

**PASS** only when all relevant runtime entrypoint/import paths are independently verifiable and cannot be rewritten or replaced by a less-trusted principal. **UNSAFE** if such a principal can replace worker-executable bytes (including via writable parent, interpreter or import dependency). **UNKNOWN** where evidence is incomplete. No proof-by-writing, and no unapproved repairs.

## Observed assessment

**UNSAFE.** Less-trusted `guard` can control the worker's invoked interpreter path (`venv/bin` symlink replaceability) and can replace the offbox tree via parent-directory rename; `guard` can also write `site-packages`. `lg-backup` itself cannot write those paths. Install-time 15/15 root leaf hashes ≠ runtime trust.

## Source remediation + corrective inactive install (observed)

Source correction is documented in [OFFBOX_RUNTIME_TRUST.md](OFFBOX_RUNTIME_TRUST.md) (PR #15). Cursor-reported corrective inactive install under [#7011064958](https://github.com/nguyenthaibinh19/EnglishApp/issues/8#issuecomment-7011064958):

1. Dedicated `/opt/language-guard-offbox` root-owned execution tree installed (sibling of `/opt/language-guard`).
2. On-disk unit templates now use `/usr/bin/python3 -I` (not the guard-owned app venv).
3. Packager `install-execution-tree --production` used; tree `root:root` dirs `0755` / files `0644`; 15/15 D5A2D0-P1 hashes MATCH.
4. Four inactive unit files replaced; **no** `daemon-reload`/start/enable.
5. Obsolete `/opt/language-guard/offbox` left untouched; account server unchanged.
6. Static checks do **not** prove live isolation.

**Post-fix Gate A PASS + Gate B CONFIG PASS** under [#7011582969](https://github.com/nguyenthaibinh19/EnglishApp/issues/8#issuecomment-7011582969) (exhausted). Historical pre-fix **UNSAFE** evidence remains preserved. Live isolation/activation still require new Owner authorization.

## Strict prohibited operations

- No file writes, `chmod`/`chown`, `setup.sh`, package install, systemd `daemon-reload`/`enable`/`start`/`restart`/`stop`, socket/worker/helper execution or isolation tests without new Owner authorization.
- No reading `.env`, OAuth/other credential contents, private keys, user DB rows, account data, backup artifacts or recovery data.
- No age install, recipient/token provisioning, Google Drive API calls, backup/restore, Cloud Sync, AI-M4 or production activation.
- Do not auto-correct unsafe configuration observed by this audit.

## Authorization boundary

Owner's read-only executable-path approval, corrective inactive-write approval, and conditional post-fix audit/daemon-reload approval are all **exhausted**. Any live isolation, age/OAuth/Drive setup, enable/start or activation needs a separate explicit Product Owner authorization.
