# Phase 18B.9 off-box status

Status updated: **2026-11-19**. Phase 18B.9 remains **OPEN / PRODUCTION NOT READY**. This is the phase map; it does not independently authorize VPS actions. See the latest Owner approval on Issue #8 and the active handoff.

The names `18B9D4C` and `PHASE18B9D4C` are the same step: Phase **18B.9**, local step **D4C**. They are not Phase 18B.4. Phase 18B.4 is the already closed sync-backup timer contract.

The accepted frozen offbox source and systemd unit templates are now in this repository under `deploy/hetzner/offbox/` and `deploy/hetzner/`, from PR #12 and PR #13. `app/offbox_poc.py` is still the closed 18B.9B Restic proof and must not be installed as the uploader. Earlier `D:\Tools` labs remain historical evidence, not production. Cursor has reported an **inactive-only VPS packaging installation**; it is not an operational backup.

## How to read a step

| Written form | Means |
|---|---|
| 18B.9 | The open off-box recovery phase |
| 18B.9B | Closed local Restic proof, commit `274156e` |
| 18B.9C1 | Design accepted on 2026-11-10, commit `d4b8588` |
| 18B.9C2 | Named future external drill. **Not authorized.** D5A2C1 is not 18B.9C2 |
| 18B.9D4C through 18B.9D5A2D2 | Local and approved-operation steps after the design. The letter suffix is the step id. D5A2D0-P1 is accepted review-branch import. D5A2D2 is WSL isolation correction |

## Closed before these steps

Phase 18B.9B is **CLOSED — Leader Accepted, 2026-11-10**, commit `274156e`. It is a local synthetic Restic proof. It does not produce the standalone `.age` artifact.

Phase 18B.9C1 is **DESIGN ACCEPTED, 2026-11-10**. The standalone age `.age` artifact remains the architecture. Two sentences in that plan are no longer the current build: age v1.3.2 with an `age1pq1` recipient has been validated on WSL, and the transfer is the Drive adapter, not `rclone copy`. Backblaze B2 remains the unprovisioned fallback. Object Lock and a deleting lifecycle stay off. A 26-hour RPO and a 4-hour RTO remain proposals.

## Step map

| Step | Lab report | Result | What it is not |
|---|---|---|---|
| 18B.9D4C | `D:\Tools\age-c2d4c-linux-20261112T1644Z-7f3a9c21` | Leader accepted the 12 functional Linux tests. One naming attempt failed and was preserved | Not a VPS change. The `lgd4c-*` units stay installed, inactive, and not enabled |
| 18B.9D4D | `D:\Tools\age-c2d4d-freeze-20261112T1710Z-b7e4c1d2` | Security configuration freeze recorded. No unit was installed in that step | Not a claim that cgroup identity is race-free. pidfd does not remove the pre-open race |
| 18B.9D4E | `D:\Tools\age-c2d4e-approval-20261112T1724Z-a91c3e70` | One read-only VPS session, exit 0. Script SHA-256 `c7a97334fee06910614462560dab4619ed8a3bb18a2c9f9cec983ab28b47b0a9` | Not a write. `lg-backup` was absent. Journal mode and the production venv Python stayed unknown |
| 18B.9D5A1 | `D:\Tools\age-c2d5a1-user-20261113T1242Z-6c8e1a40` | One approved `useradd`. VPS `lg-backup` is uid 994, gid 977, shell `/usr/sbin/nologin`, locked password | Not a home directory. The home field is `/var/lib/language-guard-backup` and that directory was absent after this step. `accounts.db` stayed unreadable |
| 18B.9D5A2A | `D:\Tools\age-c2d5a2a-directory-20261113T1301Z-4b7d9e12` | One approved mkdir. `/var/lib/language-guard-backup` is mode 0700, `lg-backup:lg-backup`, and empty | Not a socket directory and not a backup schedule |
| 18B.9D5A2B | `D:\Tools\age-c2d5a2b-impl-20261113T1343Z-c4e8a1b7` | Local helper and worker. Authoritative run 18 passed, 0 failed, 1 blocked | The blocked case is the cross-user namespace because sudo asked for a password. Not installed on the VPS |
| 18B.9D5A2B1 | `D:\Tools\age-c2d5a2b1-harden-20261115T2129Z-a91c7e40` | WSL integration **not accepted**. PASS 4, FAIL 3, BLOCKED 1 | Not a production install. Four `lgd5a2b1-*` units were installed and left inactive |
| 18B.9D5A2B2 | `D:\Tools\age-c2d5a2b2-socket-20261116T1016Z-8dfcab54` | Socket transfer of that one run passed. Encryption failed. The empty `snapshot.age` stays 0 bytes | Frame verification is not Drive verification and not `VERIFIED` |
| 18B.9D5A2B3 | `D:\Tools\age-c2d5a2b3-nativeage-20261116T1044Z-c25771fb` | **Leader accepted.** Native encryption integration is closed. Result PASS | The recorded state is `ENCRYPTED`. `download_verified` is false. This is not off-box success |
| 18B.9D5A2C | `D:\Tools\age-c2d5a2c-drive-20261116T1119Z-c8e4a21b` | **Leader accepted.** Fake-transport tests 30 passed, 0 failed, 0 blocked | No Google call. `fakefile001` is not a Drive file. A fake `VERIFIED` is not production evidence |
| 18B.9D5A2C1 | `D:\Tools\age-c2d5a2c1-http-20261116T1155Z-b7d3e91a` | Original localhost run reported 37 passed, 0 failed, 0 blocked. R1 then corrected checkpoint numbering and the synthetic-restore exit | **CLOSED — Leader Accepted, 2026-11-16.** Localhost milestone only. Not a Google call and not a deployment |
| 18B.9D5A2C2 | `D:\Tools\age-c2d5a2c2-preflight-20261116T1344Z-ada71f3f` | Static preflight, then owner-approved one-shot live test. Cursor reported one-invocation PASS | **CLOSED — Leader Accepted, 2026-11-16.** Synthetic live shot only. Not production backup |
| 18B.9D5A2C2-P1 | `D:\Tools\age-c2d5a2c2p1-wsl-20261116T1546Z-c91e4a27` | **Leader accepted, 2026-11-16**, for the local WSL gate and ext4 evidence root. Cursor reported 32 passed, 0 failed, 0 skipped. The Leader did not rerun them | Safety hardening for the later one-shot. Not a deployment |
| 18B.9D5A2C3 | [PHASE-18B.9D5A2C3-production-readiness.md](PHASE-18B.9D5A2C3-production-readiness.md) | **Leader Accepted as PLANNING COMPLETE, 2026-11-16.** Overall **NOT READY**. Recommendations are not automatic authorizations | Not implementation, deploy, or another live test |
| 18B.9D5A2D0 | [PHASE-18B.9D5A2D0-canonical-source-inventory.md](PHASE-18B.9D5A2D0-canonical-source-inventory.md) | Canonical source inventory and packaging plan. Proposed 15-module freeze from C1R1 hashes | Inventory only. Not a deploy |
| 18B.9D5A2D0-P1 | branch `phase18b9/d5a2d0-p1-source-import` commit `98b590e` | **CLOSED — Leader Accepted, 2026-11-16**, controlled source import only. Leader verified 17-file allowlist and 15/15 SHA-256 MATCH | Review branch unchanged. Not merged. Not installed. Not production activation |
| 18B.9D5A2D2 | `D:\Tools\age-c2d5a2d2-isolation-20261116T2030Z-e7c4b921` | Focused WSL isolation run. Automated score **OVERALL FAIL**. B/C/F/G/H PASS; A/D/E FAIL on formal journal criteria | Not VPS install. Canonical hashes unchanged. Units inactive |
| 18B.9D5A2D3 | [PHASE-18B.9D5A2D3-helper-journal-evidence.md](PHASE-18B.9D5A2D3-helper-journal-evidence.md) | Journal recovery complete. Collection query error established. Recovered re-score A/D PASS, E FAIL, **OVERALL FAIL**. No rerun. Does not rewrite D5A2D2 as PASS | Not VPS install. `results-r1` preserved; evidence under `results-r1-recovered/` |
| 18B.9D5A2D4 | [PHASE-18B.9D5A2D4-interrupted-transfer-semantics.md](PHASE-18B.9D5A2D4-interrupted-transfer-semantics.md) | **CLOSED — Leader Accepted: REVISE TEST.** E1/E2 accepted; suite 7/7 PASS; no ACK | Lab `D:\Tools\age-c2d5a2d4-interrupt-20261117T1500Z-a8f3c1e2`; D5A2D2/D3 FAIL preserved |
| 18B.9D5A2D5 | [PHASE-18B.9D5A2D5-revised-isolation-evidence.md](PHASE-18B.9D5A2D5-revised-isolation-evidence.md) | **CLOSED — Leader Accepted:** revised WSL isolation safety gate. Historical D2/D3 FAIL preserved. Not production | Composite A/B/C/D/E1/E2/F/G/H |
| 18B.9D5A2D6 | [PHASE-18B.9D5A2D6-source-integration-readiness.md](PHASE-18B.9D5A2D6-source-integration-readiness.md) | **CLOSED — Leader Accepted:** READY_FOR_SOURCE_INTEGRATION_REVIEW. **Not** merge approval. Import unmerged | 17-file allowlist frozen |
| 18B.9D5A2D7 | [PHASE-18B.9D5A2D7-source-integration-candidate.md](PHASE-18B.9D5A2D7-source-integration-candidate.md) | **SOURCE MERGED — NOT DEPLOYED** (PR #12 / `c03a0f5`) | 23 files on main; no VPS/units/Drive/Cloud Sync |
| 18B.9 accelerated readiness | [PHASE-18B.9-accelerated-readiness.md](PHASE-18B.9-accelerated-readiness.md) | **SOURCE MERGED** (PR #13 / d6643e0); **inactive VPS packaging installed**; **exec-path audit UNSAFE** (Cursor evidence 2026-11-19, Issue #8) | 15 pinned offbox modules and 4 inert unit files copied; no daemon reload, execution or production backup; runtime path trust UNSAFE; D2/D3 FAIL preserved |
| 18B.9 runtime trust remediation | [OFFBOX_RUNTIME_TRUST.md](../procedures/OFFBOX_RUNTIME_TRUST.md) | **SOURCE MERGED** (PR #15 / `adbc3d5`); **corrective inactive VPS install INSTALL PASS** (static); dedicated `/opt/language-guard-offbox` + `/usr/bin/python3 -I`; frozen module bytes unchanged | **no daemon-reload/activation**; post-fix PASS audit still required; historical UNSAFE + D2/D3 FAIL preserved |

Earlier local labs C2B, C2C, C2D, D3, D3A, and D3B informed the adapter. They are not re-opened by this map. The one C2D synthetic upload does not validate the D5A2C adapter. Their OAuth files were not read for this record.

## Accepted local behavior

- The artifact is one age ciphertext of one integrity-checked SQLite snapshot. The worker encrypts with `age -r` and does not receive the identity.
- Native age is v1.3.2 at `/var/lib/lgd5a2b1-a91c7e40-linux-age/age` on WSL only. The archive digest is `sha256:cbe24006683f8eb669266162894b9a522a1af52f2665fbc63a4bb032ed26ac10`. The archive plugins were not extracted. This binary is not on the VPS.
- D5A2B3 ciphertext SHA-256 `dd6457a36a3ce577833d2a935e9bee95b9df2b0a23a0ec9f633edba75004f9b0` decrypted, matched the snapshot, and passed `PRAGMA integrity_check`. That proves local encryption. It does not prove a remote copy.
- The Drive adapter reserves one file id, uploads, then downloads that same id and compares SHA-256. HTTP 200 or 201 alone is not `VERIFIED`. A restore drill is a separate record and does not create `VERIFIED`.
- Multipart is used at or below 5 MiB. Above that, the upload is resumable in 256 KiB chunks. `DELETE`, `PATCH`, copy, trash, and a metadata update are refused.
- An ambiguous result keeps the reserved id. A missing object stays `UNKNOWN` and does not allocate a second id.
- D5A2C1 adds the real HTTPS transport and changes one branch in its own copy: a resumable HTTP 404 reconciles the original file id. The accepted D5A2C lab still records an expired session as `UNKNOWN` with detail `session-expired`. Do not rewrite that lab. The accepted D5A2C1 copy is the later R1 lab, which is not in this repository. R1 parses the full checkpoint index, selects the latest checkpoint numerically, and returns success from the one-shot script only when remote verification and the synthetic restore both succeed. Fifteen other `offbox` modules are unchanged from D5A2C1. R1 changed `drive_upload.py`, `loopback_drive.py`, `live_synthetic_once.py`, and the associated tests.
- New attempts record `transport` as `fake`, `localhost`, or `https`. Only `transport=https`, state `VERIFIED`, `download_verified` true, and detail `downloaded-sha256` can satisfy a production gate. No such live record exists. Older records without the field are not production evidence.
- `VERIFYING` is the download check inside the transition. It is not a persisted state.

## Identities that must not be mixed

| Identity | Where | Id |
|---|---|---|
| `guard` | VPS | uid 995, gid 982 |
| `lg-backup` | VPS | uid 994, gid 977 |
| `lgd5a2b1-guard` | WSL lab | uid 994, gid 984 |
| `lgd5a2b1-backup` | WSL lab | uid 993, gid 983 |
| `lgd4c-guard`, `lgd4c-backup` | older WSL lab | not the VPS account |

The WSL uid 994 is `lgd5a2b1-guard`. The VPS uid 994 is `lg-backup`. They are different machines.

## What is installed, and what is not

**Latest reported VPS state (2026-11-19):** Following one Owner-authorized inactive install, `/opt/language-guard/offbox` holds 15/15 SHA-verified modules (`root:root 0644`); four offbox unit files are present in `/etc/systemd/system` (`root:root 0644`) and **not daemon-reloaded, started or enabled**. `/var/lib/language-guard-helper` is `guard:guard 0700`, while `/var/lib/language-guard-backup` remains `lg-backup:lg-backup 0700`, empty. Production age binary, recipient and `oauth-refresh` are still absent. The older sync-backup timer stays disabled; accounts retention remains 14, `STUDY_SYNC_ENABLED` unset and `study_sync.db` absent. Google Drive **NOT CONFIGURED**.

**Executable-path trust (observed, 2026-11-19):** ONE Owner-authorized read-only SSH audit classified the worker executable-path trust boundary **UNSAFE**. Observed: `/opt/language-guard` is `guard:guard 755` and writable by `guard` (not sticky); offbox leaves remain root-owned but the parent allows rename/replace of the `offbox` entry; worker `venv/bin/python` resolves to root-owned `/usr/bin/python3.14`, while `venv`/`venv/bin`/`site-packages` are guard-owned and writable by `guard`; `lg-backup` cannot write those paths; no shared groups; ACLs match unix modes. Install-time root leaf hashes do not establish runtime trust. Historical D5A2D2/D5A2D3 **FAIL preserved**. Evidence: [Issue #8 audit](https://github.com/nguyenthaibinh19/EnglishApp/issues/8#issuecomment-7009010670), [OFFBOX_VPS_PREREQUISITES.md](../procedures/OFFBOX_VPS_PREREQUISITES.md). Install evidence: [Issue #8 install](https://github.com/nguyenthaibinh19/EnglishApp/issues/8#issuecomment-7008470434), [Architect review](https://github.com/nguyenthaibinh19/EnglishApp/issues/8#issuecomment-7008526944).

On WSL, these four units exist, are inactive, and are not enabled: `lgd5a2b1-handoff.socket`, `lgd5a2b1-handoff@.service`, `lgd5a2b1-worker.service`, `lgd5a2b1-intruder.service`. The worker unit hash after D5A2B3 is `7fba4c491aa20c6ef9b6ffdb61e0e0708b5467947ad3e8ab8ca21370a77b1fd1`. The D4C units remain installed and inactive. Do not reset the three failed helper instances left by D5A2B2.

## Current gate

Phase 18B.9D5A2C2 is **CLOSED — Leader Accepted, 2026-11-16**. The one-shot synthetic Google Drive live test is closed. Phase 18B.9D5A2C1 remains closed as the localhost milestone. Phase 18B.9 remains **OPEN**. Google Drive production remains **NOT CONFIGURED**. Cloud Sync remains **OFF**. No VPS change was made and no production backup was activated.

**18B.9D5A2C3 — Production Readiness Review** is **Leader Accepted as PLANNING COMPLETE, 2026-11-16**. See [PHASE-18B.9D5A2C3-production-readiness.md](PHASE-18B.9D5A2C3-production-readiness.md). Overall production readiness remains **NOT READY**. Recommendations in that report are not automatic authorizations.

**18B.9D5A2D0 — Canonical Source Inventory** remains the planning basis. See [PHASE-18B.9D5A2D0-canonical-source-inventory.md](PHASE-18B.9D5A2D0-canonical-source-inventory.md).

**18B.9D5A2D0-P1 — Controlled Canonical Source Import** is **CLOSED — Leader Accepted, 2026-11-16**, for controlled source import only. Leader independently verified branch commit `98b590e`, the 17-file allowlist, and 15/15 SHA-256 MATCH. The review branch remains unchanged and is not merged.

**18B.9D5A2D2 — WSL Systemd Isolation Correction** completed one focused run with automated score **OVERALL FAIL**. See [PHASE-18B.9D5A2D2-wsl-isolation.md](PHASE-18B.9D5A2D2-wsl-isolation.md). Not a VPS install. Canonical hashes unchanged. New `lgd5a2d2-*` units inactive.

D5A2C1 evidence remains: original localhost 37 reported passes; R1 17 focused passes reproduced by the Leader; 37 regression passes not independently rerun. R1 review archive SHA-256 `9d9473f8d16b77b4ed1bbc2c855bde12fd907ffbecfbae5f249d9b6d57061819`.

D5A2C2 live evidence: one authorized invocation. Cursor reported PASS with status `VERIFIED`, detail `downloaded-sha256`, restore integrity `ok`, marker `1`. Ciphertext SHA-256 `a423f281ca55ae1a833cf40d2df854e84678fed24a28d89742215b101593f97c`. Documentation checkpoint `29317d0`. The accepted P1 script SHA-256 is `90f987c78c21c9a212eb14ed16ac3944ed4d5eac4b1550ea378ce8cd76cbf78a`. A second live attempt is **NOT AUTHORIZED**. The synthetic Drive object remains until a separate deletion approval. No `DELETE` or `PATCH` was performed.

Local evidence stays outside GitHub under the private WSL evidence root. Credentials and folder id are not in this repository. An External Testing refresh token is expected to expire about seven days after the 2026-11-16 consent. The daily report stays **NOT CONFIGURED** until a separately reviewed production activation. The Phase 18B.8 report remains the only notification path, and the off-box lines are not installed.

## Still unknown / remaining gates

The executable-path trust question was answered **UNSAFE** ([Issue #8 #7009010670](https://github.com/nguyenthaibinh19/EnglishApp/issues/8#issuecomment-7009010670)) and that historical result is preserved. Corrective inactive VPS install under [#7011064958](https://github.com/nguyenthaibinh19/EnglishApp/issues/8#issuecomment-7011064958) reported **INSTALL PASS** (static only; authorization exhausted): `/opt/language-guard-offbox` + reviewed on-disk units with `/usr/bin/python3 -I`; no daemon-reload/start/enable; obsolete `/opt/language-guard/offbox` left in place ([OFFBOX_RUNTIME_TRUST.md](../procedures/OFFBOX_RUNTIME_TRUST.md)). Remaining gate: a **separately Owner-authorized** post-fix read-only audit must report **PASS** before any isolation/activation request. Native age is not installed. Live isolation, age/OAuth/Drive provisioning, and production activation remain unproven and unauthorized.
