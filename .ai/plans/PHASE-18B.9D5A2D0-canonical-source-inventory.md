# Phase 18B.9D5A2D0 — Canonical source inventory and packaging plan

Status: **INVENTORY COMPLETE — awaiting Leader review.** Planning only. No source was copied, merged, packaged, or installed. This document does **not** authorize deployment.

Baseline: GitHub `c68bc1607ccd20f0ab3f6b6fb70cdb89b7633c3d`. Written 2026-11-16. Phase 18B.9 remains **OPEN**. Google Drive production remains **NOT CONFIGURED**. Cloud Sync remains **OFF**. Overall production status remains **NOT READY**.

Method: read-only SHA-256 inventory of labs under `D:\Tools`. No tests, no network, no VPS, no credential inspection.

D5A2C3 is **Leader Accepted as PLANNING COMPLETE** (2026-11-16). Its proposed future implementations remain recommendations, not automatic authorizations.

## Selection rule (not “newest wins”)

P1 is **not** treated as canonical merely because it is the newest lab.

For each production module, the proposed authority is the **Leader-accepted behavior** that last changed that module:

- Helper / framing / snapshot / native encrypt path: closed under **D5A2B3** (and carried forward unchanged).
- Drive adapter core: introduced under **D5A2C**, then corrected under **D5A2C1** and **D5A2C1-R1**.
- HTTPS transport, provenance, oauth exchange: introduced under **D5A2C1**, unchanged in R1 except where listed.
- D5A2C2-P1 changed **only** the lab live harness (`live_synthetic_once.py`) plus P1-only checks. **All `offbox/*.py` hashes in P1 match C1R1 exactly.**

Therefore the proposed canonical **Python production tree** is the **D5A2C1-R1 `offbox/` set**, verified bitwise-identical to P1 `offbox/`. P1 is corroboration, not an independent source authority.

## Lab roots inspected

| Milestone | Lab path | Acceptance |
|---|---|---|
| D5A2B | `D:\Tools\age-c2d5a2b-impl-20261113T1343Z-c4e8a1b7` | Helper/worker implementation ready (historical) |
| D5A2B1 | `D:\Tools\age-c2d5a2b1-harden-20261115T2129Z-a91c7e40` | **Not accepted** (systemd integration FAIL/BLOCKED) |
| D5A2B2 | `D:\Tools\age-c2d5a2b2-socket-20261116T1016Z-8dfcab54` | Socket transfer; encrypt failed (historical) |
| D5A2B3 | `D:\Tools\age-c2d5a2b3-nativeage-20261116T1044Z-c25771fb` | **Leader accepted** native encrypt |
| D5A2C | `D:\Tools\age-c2d5a2c-drive-20261116T1119Z-c8e4a21b` | **Leader accepted** fake-transport Drive adapter |
| D5A2C1 | `D:\Tools\age-c2d5a2c1-http-20261116T1155Z-b7d3e91a` | Superseded by R1 for changed files |
| D5A2C1-R1 | `D:\Tools\age-c2d5a2c1r1-http-20261116T1303Z-b4e81c20` | **Leader accepted** localhost HTTPS + corrections |
| D5A2C2-P1 | `D:\Tools\age-c2d5a2c2p1-wsl-20261116T1546Z-c91e4a27` | **Leader accepted** live-script WSL/ext4 gates only |

## 1–2. Module inventory (proposed production set)

Authority root: `D:\Tools\age-c2d5a2c1r1-http-20261116T1303Z-b4e81c20\offbox\`.

| Module | SHA-256 | Origin of this bytes | Also present unchanged in | Role | Accepted status |
|---|---|---|---|---|---|
| `age_encrypt.py` | `91b6d8c1adb58ade6695634d00bcbd5f5063bb07a8ab878ef831bceb1292ccff` | D5A2B3 | C, C1, C1R1, P1 | `age -r` encrypt; no identity | **Accepted** (B3+) |
| `attempt_store.py` | `d00f2cca51142cb91b2accff504d0674373d42372cad45d6e1f5a852f7deaef6` | D5A2B3 | C, C1, C1R1, P1 | Exclusive attempt state files | **Accepted** (B3+) |
| `backup_worker.py` | `79455d0ac99a2d77c478f3e6d5ad38a3243cb66bc7763165424d46c8c5395d14` | D5A2C1 | C1R1, P1 | Encrypt then optional publish; records `transport` | **Accepted** (C1/R1) |
| `credential.py` | `87cecf4fa928d93ff93e7cf4b090df48cd8a8a83a3ddf2a67e3846aee683ee0f` | D5A2C | C1, C1R1, P1 | LoadCredential refresh-token reader | **Accepted** (C+) |
| `drive_upload.py` | `3895c9ca2bfbe3d0e89b5b89f6926c0b420bed8da8c5f204af52802178ae0a08` | D5A2C1-R1 | P1 | Reserve id, upload, download verify; R1 progress/symlink fixes | **Accepted** (C1R1) |
| `framing.py` | `afae4d2a666723bcfa29d22824c3ed33bfeabda3902483676e787d67bfbae19d` | D5A2B3 | C, C1, C1R1, P1 | Socket frame codec | **Accepted** (B3+) |
| `https_transport.py` | `c03268768c39bc2ec2f246d9b22b07098fdbc017801837e8815ce31879be0660` | D5A2C1 | C1R1, P1 | Real HTTPS client; host allowlist | **Accepted** (C1) |
| `logutil.py` | `6afc6548f01798e2bd8858a4c490af1616877b82a1bfe2f31f3c3213fa1e6aa8` | D5A2C | C1, C1R1, P1 | Secret redaction in logs | **Accepted** (C+) |
| `monitoring.py` | `8b55d9f0824938e213ec767708dd237249248854013fea233e8d074d4bf12456` | D5A2C1 | C1R1, P1 | Latest-state view incl. `transport` | **Accepted** (C1) |
| `oauth_exchange.py` | `c2b11ce1e0729dd0f9c66752c89c5ce049c806e95693080ff79d8c813224a752` | D5A2C1 | C1R1, P1 | Refresh → access token exchange | **Accepted** (C1) |
| `peer_auth.py` | `bfa236afa5169310c25fff5e26c06b0d99efd878d6905b45c42ff7facadd777f` | D5A2B3 | C, C1, C1R1, P1 | Peer uid/gid/unit checks | **Accepted** (B3+) |
| `provenance.py` | `26e77e915ad1acb769752047e6976b1e40180dc29fa5956c96eaec589d5b3baa` | D5A2C1 | C1R1, P1 | `production_eligible` / `restore_eligible` | **Accepted** (C1) |
| `restore_check.py` | `d767326183d176a9b004893653d68cb3699993faf43e7edf3e0b64b79d8ea76f` | D5A2C | C1, C1R1, P1 | Separate restore drill record | **Accepted** (C+) |
| `snapshot_copy.py` | `6aeb40810068fdee23b7580bdb060375c0521d28172f84116830dafda4df8973` | D5A2B3 | C, C1, C1R1, P1 | SQLite online backup + integrity | **Accepted** (B3+) |
| `snapshot_helper.py` | `7eb388a6a322d3e03e63d8b66b978b012611efa86f0a713b5ba6595a040f7098` | D5A2B3 | C, C1, C1R1, P1 | Helper process entry | **Accepted** (B3+) |

Count: **15** production Python modules.

### Lab / test-only (not proposed for VPS install)

| File | SHA-256 | Origin | Why excluded from production tree |
|---|---|---|---|
| `fake_drive.py` | `09b5fc8c0cd8c36c6cc411f57a2396900434da67c67af525dfb3de5e196c8312` | D5A2C | In-memory fake transport |
| `loopback_drive.py` | `9c6f300e1c5cb216c5ed20939e16818644fbc19b4c1fe8a20f66c9078d2e07bc` | D5A2C1-R1 | Localhost HTTPS stub for tests |
| `live_synthetic_once.py` (P1) | `90f987c78c21c9a212eb14ed16ac3944ed4d5eac4b1550ea378ce8cd76cbf78a` | D5A2C2-P1 | One-shot lab harness; WSL/ext4 gates; **not** the systemd worker |
| `live_synthetic_once.py` (R1) | `25cb4f3e0dee2459abc54d5e5ee5c9388176113f1722fb3c571defb24523d7d5` | D5A2C1-R1 | Superseded by P1 for any future lab use; still not production |
| `tests/run_r1_checks.py` | `c938741356c9cd23b0adfa5258c2319d2609fd7fbc8554b6151c9ddd95310ded` | C1R1 | Test runner |
| `tests/run_wire_checks.py` | `0c9a5224b3108959d17514118ce87f0b976bbf5272a4f1c21f4cd80b19d27461` | C1R1 | Test runner |
| `tests/run_p1_checks.py` | `760ecc7ff31c9663e43756d6dd98358513f1fe37acfe64de07f0370becf28fe1` | P1 | P1 gate tests |

## 3. Differences between older and newer copies

| Module | Older → Newer | What changed (summary) |
|---|---|---|
| `drive_upload.py` | C `136025b4…` → C1 `924492f7…` | Attempt-dir checks; expired session / 404 resume → reconcile; symlink-safe exclusive write; richer transport error detail |
| `drive_upload.py` | C1 `924492f7…` → **C1R1** `3895c9ca…` | Full checkpoint index parse; numeric latest progress; progress-rejected on symlink/malformed; reservation/progress consistency |
| `loopback_drive.py` | C1 `e2116d94…` → **C1R1** `9c6f300e…` | Metadata call records `file_id` (expired-session test correctness) |
| `backup_worker.py` | B3 `5e2a9af1…` → C `9c6300ee…` | Injected transport publish path; VERIFIED/UNKNOWN states; credential + drive_upload |
| `backup_worker.py` | C `9c6300ee…` → **C1** `79455d0a…` | Records `transport` fake/localhost/https on attempt state |
| `logutil.py` | B3 `f41f0a5f…` → C `6afc6548…` | Broader secret markers (Bearer, refresh_token, session URI patterns) |
| `monitoring.py` | C `78460035…` → C1 `8b55d9f0…` | Exposes `transport` in latest view |
| `live_synthetic_once.py` | R1 `25cb4f3e…` → **P1** `90f987c7…` | Positive WSL proc gates; absolute ext4 evidence root; credential/evidence separation; 4 args |
| Helper stack (`age_encrypt`, `framing`, `peer_auth`, `snapshot_*`, `attempt_store`) | B / B1 → **B3** hashes | B3 bytes are the accepted encrypt-era copies; earlier B/B1 hashes are historical only |
| `offbox/*.py` | C1R1 → P1 | **No differences** |

## 4. Proposed canonical source tree

Proposed freeze name (not created): `offbox-canonical-d5a2d0/` contents =

```text
offbox/
  age_encrypt.py
  attempt_store.py
  backup_worker.py
  credential.py
  drive_upload.py
  framing.py
  https_transport.py
  logutil.py
  monitoring.py
  oauth_exchange.py
  peer_auth.py
  provenance.py
  restore_check.py
  snapshot_copy.py
  snapshot_helper.py
docs/
  SHA256SUMS          # the table above
  SOURCE_AUTHORITY.md # points at C1R1 lab root
```

**Not** included in the freeze until a later unit milestone: systemd units (see §7), `fake_drive.py`, `loopback_drive.py`, `live_synthetic_once.py`.

**Units status:** **no accepted production unit set.** Candidates exist but conflict:

| Candidate set | Path | Problem |
|---|---|---|
| D5A2B `lg-backup-*` | B lab `units/` | Early; helper lacked `StandardError=journal`; `StateDirectory=` caution |
| D5A2B1 `lg-backup-*` | B1 lab `units/` | Still missing `StandardError=journal` on handoff; integration **not accepted** |
| D5A2B2/B3 `lgd5a2b1-*` | lab-named; `/mnt/d/Tools/...` ExecStart | WSL evidence only; not production names/paths |
| D5A2C `language-guard-offbox-*` | C lab `units/` | Has `StandardError=journal`; **NOT installed**; ExecStart still lab `/mnt/d/Tools/...`; worker env incomplete vs B deployment model |

Proposed unit **direction** (draft only, not frozen bytes): production names from D5A2C (`language-guard-offbox-*.{socket,service}`), identity/path model from D5A2B `DEPLOYMENT.txt` (`guard` helper, `lg-backup` worker, `/opt/language-guard/offbox`, `/var/lib/language-guard-backup`, `/run/language-guard-offbox/handoff.sock`), mandatory `StandardError=journal` on the handoff instance, **no** `StateDirectory=` until measured, ExecStart must use `/opt/language-guard/...` not lab paths.

## 5. Packaging and runtime dependencies

From D5A2C `DEPENDENCIES.txt` and lab evidence:

| Dependency | Requirement |
|---|---|
| Python | stdlib only; lab ran 3.14.4 on WSL; **production venv version UNKNOWN** |
| age | Linux amd64 **v1.3.2**; archive SHA-256 `cbe24006683f8eb669266162894b9a522a1af52f2665fbc63a4bb032ed26ac10`; plugins not extracted; binary not on VPS |
| Recipient | public `age1pq1` file only; identity offline |
| OAuth | Desktop client; scope `drive.file`; refresh via LoadCredential `oauth-refresh` |
| Network | Hosts `www.googleapis.com`, `oauth2.googleapis.com` only (https_transport) |
| OS | systemd socket activation; no pip packages |

## 6. Production install layout and ownership (plan only)

Drawn from D5A2B `DEPLOYMENT.txt` + ADR-024. Nothing below is installed.

| Path | Owner / mode | Purpose |
|---|---|---|
| `/opt/language-guard/offbox/*.py` | `root:root` `0644` (dir `0755`) | Frozen modules |
| `/opt/language-guard/venv/bin/python` | existing | Interpreter (version TBD) |
| `/var/lib/language-guard-backup` | `lg-backup:lg-backup` `0700` | Already exists empty (D5A2A) |
| `/var/lib/language-guard-helper` | `guard:guard` `0700` | **Absent**; plaintext snapshots only |
| `/run/language-guard-offbox/handoff.sock` | `lg-backup:lg-backup` `0600` | Socket inode |
| `/etc/language-guard/age-recipient` | root-owned, worker-readable | Public recipient only |
| `/etc/language-guard/oauth-refresh` | root `0400` via LoadCredential to worker only | Refresh token |
| age binary under backup-owned path or `/usr/local/...` | root-owned, worker-executable | v1.3.2 pinned |

Processes: helper `User=guard`; worker `User=lg-backup`. Helper must not receive OAuth or age identity. Worker must not open live `accounts.db` (InaccessiblePaths). Collector/notifier must not receive off-box credentials (18B.8 rule).

## 7. Remaining known security defects (esp. D5A2B1)

These block treating any unit set as deployable:

1. **D5A2B1 positive transfer FAIL:** handoff `StandardOutput=socket` without `StandardError=journal` polluted the frame stream (`magic` failure). B2/C templates added `StandardError=journal`; B1 production-named units did **not** receive an accepted retest.
2. **D5A2B1 invalid-cgroup FAIL:** intruder/refusal token observation failed; peer isolation not proven under that unit set.
3. **D5A2B1 interrupted transfer FAIL:** incomplete transfer not observed as designed.
4. **StateDirectory BLOCKED:** recursive chown risk on `/var/lib/language-guard-backup` unmeasured; D5A2B warns not to start a unit with `StateDirectory=language-guard-backup` to discover behavior.
5. **Lab ExecStart paths:** B3/C units point at `/mnt/d/Tools/...` — unsuitable for VPS.
6. **B1 helper Expected UID 994:** on VPS, uid 994 is `lg-backup`, not a guard-class user; WSL lab uids must not be copied blindly.
7. **Worker live-upload gating:** production worker must keep fail-closed until explicitly configured; C worker refused live when folder/upload env set without live transport — packaging must preserve an activation gate.
8. **pidfd / pre-open race:** D4D freeze noted pidfd does not remove the pre-open race; still an architectural residual.

## 8. Explicit test evidence gaps before deployment

| Gap | Why it matters |
|---|---|
| D5A2B1-class isolation not accepted on production-shaped units | Cannot claim helper/worker boundary on VPS |
| StateDirectory interaction unmeasured | Risk to existing empty backup directory ownership |
| Production Python version unread | stdlib API assumptions |
| Production `accounts.db` journal mode unread | Snapshot behavior |
| Connect/read timeout, 68 MiB cap, bad cert | https_transport edges never exercised |
| Live large resumable on Google | Only localhost large + one small live multipart |
| Leader did not independently rerun C1 37-regression or P1 32 | Acceptance relies on Cursor reports + 17 focused R1 |
| Clean-host restore with offline production identity | Disaster recovery unproven |
| Off-box monitoring lines not installed | Operators lack Drive status |
| No schedule / stale threshold | Freshness undefined |
| Units not frozen | Cannot install reproducibly |

## 9. Acceptance criteria for a later source-packaging implementation

A later packaging milestone may be accepted only when **all** of the following are true:

1. A new exclusive lab or archive contains exactly the 15 modules with the SHA-256 values in §1–2 (or a Leader-approved amendment list with new hashes).
2. A `SHA256SUMS` file is published under `.ai/` or the archive; no secrets included.
3. Lab-only files (`fake_drive`, `loopback_drive`, `live_synthetic_once`) are absent from the VPS payload (may remain in a separate test archive).
4. Systemd unit drafts are rewritten with `/opt/language-guard` paths, `StandardError=journal`, no lab hostnames, and **no enablement**; unit SHA-256 recorded.
5. Packaging does **not** start services, does **not** copy OAuth/age identity, does **not** set Drive folder env for live upload.
6. A read-only verification lists installed file hashes matching the freeze.
7. D5A2B1-class isolation defects are either fixed and re-proven in a later accepted milestone, or explicitly deferred by Leader with production install still blocked.
8. Google Drive remains **NOT CONFIGURED**; Cloud Sync remains **OFF**.

## Source conflicts and unresolved risks

- **Unit conflict:** three naming families (`lg-backup-*`, `lgd5a2b1-*`, `language-guard-offbox-*`); none accepted for production.
- **Authority conflict avoided for Python:** P1 == C1R1 for all production modules; freeze points at C1R1.
- **Worker vs live harness:** production path is `backup_worker` + systemd; live script is not a substitute packaging target.
- **Incomplete C worker unit env:** must not freeze C unit bytes without aligning to DEPLOYMENT paths and activation gates.
- **Recommendations ≠ authorization:** D5A2C3 sequence (D5A2D1…) remains recommendations until separately assigned.

## Required next implementation action

**Not authorized by this inventory.** Suggested next Leader assignment after acceptance of this plan:

1. Create an exclusive packaging lab that **copies** (not merges-evolves) the 15 C1R1 modules and writes `SHA256SUMS`.
2. Separately draft production unit files (new hashes) incorporating B1 lessons — still disabled.
3. Do **not** proceed to VPS install until a later isolation milestone closes §7.

## Authorization / STOP

Documentation only. No source copy, no tests, no Google, no VPS, no secrets, no ZIP, no production activation.
