# Phase 18B.9 off-box status

Status date: **2026-11-16**. Phase 18B.9 remains **OPEN**. This file is the phase map. It is not a deployment and it does not authorize the next live test.

The names `18B9D4C` and `PHASE18B9D4C` are the same step: Phase **18B.9**, local step **D4C**. They are not Phase 18B.4. Phase 18B.4 is the already closed sync-backup timer contract.

The implementation is not in this repository. `app/offbox_poc.py` is the closed Phase 18B.9B Restic proof and must not be installed as the uploader. The helper, worker, and Drive adapter live in local labs under `D:\Tools`. Those labs are evidence. They are not production.

## How to read a step

| Written form | Means |
|---|---|
| 18B.9 | The open off-box recovery phase |
| 18B.9B | Closed local Restic proof, commit `274156e` |
| 18B.9C1 | Design accepted on 2026-11-10, commit `d4b8588` |
| 18B.9C2 | Named future external drill. **Not authorized.** D5A2C1 is not 18B.9C2 |
| 18B.9D4C through 18B.9D5A2C2-P1 | Local and approved-operation steps after the design. The letter suffix is the step id. D5A2C2 is a static preflight. P1 is the local safety correction. Neither is a live test |

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
| 18B.9D5A2C2 | `D:\Tools\age-c2d5a2c2-preflight-20261116T1344Z-ada71f3f` | Static preflight completed. Conclusion: ready for owner review. The live script was not executed | **NOT AUTHORIZED** as a Google call. Not a deployment. D5A2C1 stays closed |
| 18B.9D5A2C2-P1 | `D:\Tools\age-c2d5a2c2p1-wsl-20261116T1546Z-c91e4a27` | Preflight accepted with conditions. Focused checks then passed 32, failed 0, skipped 0. New lab only | **PENDING REVIEW.** Not a Google call. The Drive adapter was not changed. D5A2C1 stays closed |

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

On the VPS, Phase 18B.9 has created only the `lg-backup` user and the empty `/var/lib/language-guard-backup` directory. No off-box unit, age binary, recipient, or `oauth-refresh` file is installed. `language-guard-sync-backup.timer` stays disabled. Accounts backup retention stays 14. `STUDY_SYNC_ENABLED` stays unset. `study_sync.db` stays absent. Google Drive stays **NOT CONFIGURED**.

On WSL, these four units exist, are inactive, and are not enabled: `lgd5a2b1-handoff.socket`, `lgd5a2b1-handoff@.service`, `lgd5a2b1-worker.service`, `lgd5a2b1-intruder.service`. The worker unit hash after D5A2B3 is `7fba4c491aa20c6ef9b6ffdb61e0e0708b5467947ad3e8ab8ca21370a77b1fd1`. The D4C units remain installed and inactive. Do not reset the three failed helper instances left by D5A2B2.

## Current gate

Phase 18B.9D5A2C1 is **CLOSED — Leader Accepted, 2026-11-16**. The localhost HTTPS transport milestone is closed. Phase 18B.9 remains **OPEN**. Google Drive production remains **NOT CONFIGURED**. Cloud Sync remains **OFF**. No VPS change was made and no production backup was activated.

The original D5A2C1 run reported 37 passed, 0 failed, 0 blocked. R1 reported 17 focused passes and 37 regression passes. The Leader independently reproduced the 17 focused tests in an isolated local copy. The 37 regression tests were not independently rerun. The R1 review archive SHA-256 is `9d9473f8d16b77b4ed1bbc2c855bde12fd907ffbecfbae5f249d9b6d57061819`. That archive and the accepted source are outside GitHub.

The live script SHA-256 recorded before R1 was `36973802cf63073e927871770bb467ba1bb3a4ac43389d77f28aae6f0cd147aa`. R1 changed that script. It has not been executed. The Google Drive live synthetic integration is **NOT AUTHORIZED**. The script still does nothing unless a later brief sets `LG_LIVE_APPROVAL` to exactly `APPROVE D5A2C1 SYNTHETIC DRIVE ONLY`. That phrase has not been approved. A future approved run would be one synthetic file, one upload, one download, and one hash compare, with no `DELETE`, `PATCH`, or second create. An `UNKNOWN` result stops. The object would remain in Drive until a separate deletion approval. Success would also require the synthetic restore. Acceptance of the localhost code does not approve that run.

No production credential is in the repository. The C2D OAuth files were not opened. Reuse of that test folder is unconfirmed. The long-term configuration remains a dedicated production Google Cloud project, scope `https://www.googleapis.com/auth/drive.file`, and a root-owned refresh token visible only to the backup worker through `LoadCredential`. An External Testing refresh token expires after seven days. `invalid_grant` fails closed.

Phase 18B.9D5A2C2 is a completed static preflight, 2026-11-16. It inspected the accepted R1 script and did not run it. The preflight conclusion is ready for owner review. That is not permission to run the synthetic test. Owner inputs for the client, refresh token, and folder id remain required, and no existing token is assumed valid. The evidence directory is local and is not in GitHub. A future success would not change the daily report: Google Drive stays **NOT CONFIGURED** until a separately reviewed production activation. The Phase 18B.8 report remains the only notification path, and the off-box lines are not installed.

The Leader then accepted that preflight **with conditions**. Phase 18B.9D5A2C2-P1 applied the two conditions in a new lab and did not modify the accepted R1 lab. Focused offline checks passed 32, failed 0, and skipped 0. The corrected script SHA-256 is `90f987c78c21c9a212eb14ed16ac3944ed4d5eac4b1550ea378ce8cd76cbf78a`. It requires both `/proc/sys/kernel/osrelease` and `/proc/version` to show WSL, keeps the production hostname exclusion, and takes an absolute private mode-0700 evidence root on ext4. There is no default evidence path. The credential directory stays separate. The Drive adapter, HTTP transport, and encryption modules were not changed. The approval phrase was not set, and the live script was not executed. The correction is **PENDING REVIEW**. It does not authorize the Google call. Access by `drive.file` to an existing folder remains **UNKNOWN**. No existing token is assumed valid. C2D credentials were not opened.

## Still unknown

The production venv Python version and the production `accounts.db` journal mode were not read. Native age is not on the VPS. No production age identity exists.
