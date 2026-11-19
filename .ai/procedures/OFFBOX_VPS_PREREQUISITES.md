# Phase 18B.9 — VPS prerequisites and executable-path audit

**Status (2026-11-19):** The first read-only prerequisites probe and the separately authorized *inactive-only* offbox packaging install have been completed **as reported by Cursor** and reviewed by the System Architect. The current **executable-path trust audit is OWNER AUTHORIZED, NOT EXECUTED / NOT PASSED**. Authorization: [Issue #8 comment #7008591938](https://github.com/nguyenthaibinh19/EnglishApp/issues/8#issuecomment-7008591938). **One read-only SSH session only.** This document is instructions, not independent permission to run other sessions or change the VPS.

**Phase 18B.9 is OPEN; production NOT READY; Drive NOT CONFIGURED; Cloud Sync OFF.** Historical D5A2D2/D5A2D3 FAIL stays recorded.

## Completed evidence (not reauthorized by this file)

- First prerequisites probe (Cursor-reported; Architect did **not** rerun SSH): production venv/system Python `3.14.4`, `accounts.db` `PRAGMA journal_mode=delete` via SQLite read-only URI; VPS `guard` UID/GID `995/982`, `lg-backup` `994/977`; backup dir `lg-backup:lg-backup 0700` empty; offbox units, age, recipient and OAuth refresh initially absent. See [Issue #8 review #7008262047](https://github.com/nguyenthaibinh19/EnglishApp/issues/8#issuecomment-7008262047).
- One inactive packaging **write** session (Cursor-reported): source `f99e73cf01a599425cbc66dd84f5ed53d154a2b4`; `VERIFY_OK modules=15 units=4 inventory=D5A2D0-P1`; `/opt/language-guard/offbox` 15 module SHA-256 matches, leaf files `root:root 0644` and directory `0755`; `/var/lib/language-guard-helper` created `guard:guard 0700`; four unit files copied to `/etc/systemd/system` `root:root 0644`, **not daemon-reloaded, enabled or started**. Existing app and timer unchanged. See [Issue #8 install #7008470434](https://github.com/nguyenthaibinh19/EnglishApp/issues/8#issuecomment-7008470434) and [Architect review #7008526944](https://github.com/nguyenthaibinh19/EnglishApp/issues/8#issuecomment-7008526944).
- The first post-install permissions checker falsely treated root-owned leaf `0644` as unsafe because root can write; a corrected **read-only** check confirmed 15/15 hashes. This does **not** prove runtime path safety.

## Why the additional read-only check is required

Systemd `language-guard-offbox-worker.service` runs as `lg-backup` but executes `/opt/language-guard/venv/bin/python /opt/language-guard/offbox/backup_worker.py`. The helper runs as `guard` using the same interpreter. In the source, `deploy/hetzner/setup.sh` contains `chown -R guard:guard /opt/language-guard`. **We have not confirmed actual on-host ancestry, symlink targets, venv/dependency ownership or effective write access.** Root ownership of a file does not prevent another user from replacing it if that user can write/rename its parent directory. Do not infer a vulnerability or safety from one file mode alone.

## Owner-authorized executable-path READ-ONLY audit

Use established public-key SSH with `BatchMode=yes`, `StrictHostKeyChecking=yes`, `ForwardAgent=no`. One session only. Commands below are examples of **metadata inspection**, not a blanket command authorization. Record exit statuses and output in redacted private audit evidence (no host/account secrets). Avoid executing the app venv/interpreter to inspect its path; use filesystem metadata.

```bash
# Metadata only; no filesystem modifications
id guard
id lg-backup
getent group guard
getent group lg-backup

# Inspect ancestor replaceability and symlink chains
namei -l /opt/language-guard/offbox/backup_worker.py
namei -l /opt/language-guard/offbox/snapshot_helper.py
namei -l /opt/language-guard/venv/bin/python
readlink -f /opt/language-guard/venv/bin/python

# All target and parent paths must be examined, not just leaf modules
stat -c '%A %a %U:%G %n' /opt /opt/language-guard   /opt/language-guard/offbox /opt/language-guard/venv   /opt/language-guard/venv/bin
# Inspect relevant venv/lib, site-packages, interpreter target and import
# ancestors by metadata once resolved; include symlink targets.
# Optional where available: getfacl -p PATH (ACL metadata only).
# Optional: non-writing permission query as guard/lg-backup using test -w.
# Do not create probe files, import/execute app modules or run offbox services.
```

Check the actual interpreter target (symlink mode `777` alone is not its target permission), venv configuration/import paths, Python `site-packages`, offbox import dependencies and every replaceable ancestor. Assess effective write/rename permissions for `guard`, `lg-backup`, groups and ACLs; group membership matters. If `getfacl` is missing or a relevant path cannot be resolved, classify it **UNKNOWN**; do not install tools or assume PASS.

**PASS** only when all relevant runtime entrypoint/import paths are independently verifiable and cannot be rewritten or replaced by a less-trusted principal. **UNSAFE** if such a principal can replace worker-executable bytes (including via writable parent, interpreter or import dependency). **UNKNOWN** where evidence is incomplete. No proof-by-writing, and no unapproved repairs.

## Strict prohibited operations

- No file writes, `chmod`/`chown`, `setup.sh`, package install, systemd `daemon-reload`/`enable`/`start`/`restart`/`stop`, socket/worker/helper execution or isolation tests.
- No reading `.env`, OAuth/other credential contents, private keys, user DB rows, account data, backup artifacts or recovery data.
- No age install, recipient/token provisioning, Google Drive API calls, backup/restore, Cloud Sync, AI-M4 or production activation.
- If any observation appears to require a change, **STOP and report it**, do not fix it.

## Required report / authorization boundary

Return `APP_18B9_EXEC_PATH_READONLY_AUDIT_RESULT` with exact source revision, read-only commands and exit codes, redacted owner/group/mode/ACL and resolved path evidence, principal-by-principal ability to replace runtime files, `PASS | UNSAFE | UNKNOWN`, and the smallest proposed remediation **only if needed**. Preserve historic D2/D3 FAIL and current inactive state. Update Issue #8 and this procedure/current handoff with results **after** the probe, explicitly distinguishing observed facts from proposed corrective actions.

Owner's read-only approval is exhausted after **one session/report**. Any corrective ownership/layout write, daemon reload, live isolation, age/OAuth/Drive setup or activation needs a separate explicit Product Owner authorization.
