# Phase 18B.9D5A2C3 — Production Readiness Review

Status: **PLANNING COMPLETE — awaiting Leader review.** Not a production deployment. This review does **not** claim production readiness.

Baseline: GitHub `931366c77faf8337c2e0b0675fbee22039477b9a`. Written 2026-11-16. Phase 18B.9 remains **OPEN**. Google Drive production remains **NOT CONFIGURED**. Cloud Sync remains **OFF**. No second D5A2C2 live attempt is authorized. The synthetic Drive object remains until a separate deletion approval.

Method: read-only inspection of GitHub `.ai/` documents and accepted local labs under `D:\Tools`. No tests were run. No Google API call, VPS access, credential inspection, OAuth change, source edit, upload, download, or deletion occurred.

## Verdict

The age + Drive adapter has proven local encryption, fake/localhost upload state machines, one synthetic live `VERIFIED` shot, and a synthetic restore. It is **not** packaged for VPS deployment, not scheduled, not monitored in the daily report, and not backed by a durable production OAuth project. Production remains blocked.

## Evidence corpus (read-only)

| Artifact | Role |
|---|---|
| [ADR-024](../decisions/ADR-024-offbox-age-drive.md) | Accepted local architecture through D5A2C1 |
| [PHASE-18B.9-offbox-status.md](PHASE-18B.9-offbox-status.md) | Phase step map |
| [PHASE-18B.9C1-external-readiness.md](PHASE-18B.9C1-external-readiness.md) | Design accepted 2026-11-10; transfer sentence corrected to Drive adapter |
| [HEALTH_MONITORING.md](../procedures/HEALTH_MONITORING.md) | 18B.8 closed; 18B.9 off-box lines designed, not installed |
| [current_state.md](../current_state.md), [ACTIVE_HANDOFF.md](../agent_playbook/ACTIVE_HANDOFF.md) | Accepted product and coordination state |
| `D:\Tools\age-c2d5a2b3-nativeage-20261116T1044Z-c25771fb` | Native age encrypt PASS; state `ENCRYPTED` |
| `D:\Tools\age-c2d5a2c-drive-20261116T1119Z-c8e4a21b` | Fake-transport Drive adapter; 30 PASS |
| `D:\Tools\age-c2d5a2c1r1-http-20261116T1303Z-b4e81c20` | Localhost HTTPS + R1 corrections; 17 focused / 37 regression reported |
| `D:\Tools\age-c2d5a2c2p1-wsl-20261116T1546Z-c91e4a27` | P1 WSL/ext4 live-script gates; live script SHA-256 `90f987c7…`; 32 PASS reported |
| `D:\Tools\age-c2d5a2c2-preflight-20261116T1344Z-ada71f3f` | Preflight contract, owner requirements, risks |
| Private WSL evidence `/home/nguyenthaibinh19/language-guard/d5a2c2-live-evidence` | One-shot live PASS; docs checkpoint `29317d0` |

Proven implementation behavior is labeled **PASS** below. Untested assumptions are **UNKNOWN**. Missing production work is **GAP**.

## Readiness matrix

| Area | Result | Summary |
|---|---|---|
| A. Source packaging and reproducible deployment | **GAP** | Offbox tree lives only in `D:\Tools` labs. Not in the application repository. No signed install path to `/opt/language-guard/offbox/`. |
| B. VPS identities, socket, helper/worker isolation | **GAP** | VPS has `lg-backup` and empty `/var/lib/language-guard-backup` only. D5A2B1 WSL systemd integration is **not accepted**. Production units not installed. |
| C. SQLite snapshot consistency and prerequisites | **PASS** (lab) / **UNKNOWN** (prod) | Lab uses `sqlite3` online backup + `PRAGMA integrity_check`. Production journal mode and venv Python version unread. |
| D. age public/private key separation | **PASS** (design+lab) / **GAP** (prod) | Worker uses `age -r` only. Identity offline. No production recipient or identity exists. Age binary not on VPS. |
| E. Google OAuth lifecycle and least privilege | **GAP** | Scope `drive.file` and LoadCredential design exist. Live shot used External Testing (~7-day refresh). Dedicated production project not created. |
| F. Upload recovery, idempotency, ambiguous outcomes | **PASS** (lab+one live) / **UNKNOWN** (edge live) | Fake/localhost prove reserve-once, reconcile, no DELETE/PATCH. One small live multipart `VERIFIED`. Live large resumable, timeouts, and cert rejection not exercised. |
| G. Scheduling, retention, stale detection, RPO/RTO | **GAP** | No off-box timer. No retention/delete controller. 26h RPO / 4h RTO remain proposals. |
| H. Existing 18B.8 monitoring integration | **GAP** | Design accepted; off-box lines not installed. Daily Drive line stays **NOT CONFIGURED**. |
| I. Recovery on a clean replacement machine | **GAP** | Synthetic restore in-lab only. No owner offline-identity restore of a production artifact on a clean host. |
| J. Remaining known failures / blocked coverage | **GAP** | D5A2B1 not accepted. Timeouts/certs untested. Leader did not independently rerun full regression or P1 suite. |

Overall production readiness: **NOT READY**.

## Findings A–J

### A. Source packaging and reproducible deployment

- **Evidence:** `DEPLOYMENT.txt` in D5A2B lists programs for a later copy to `/opt/language-guard/offbox/`. Accepted modules evolve across labs (B3 encrypt → C drive → C1R1 https/provenance → C2P1 live script). GitHub holds documentation only. `DEPENDENCIES.txt` (D5A2C): stdlib only; age archive SHA-256 `cbe24006…`.
- **Result:** **GAP**
- **Impact:** No reproducible deploy artifact; lab drift risk; cannot install without a packaging milestone.
- **Next action:** Freeze one accepted source tree (recommend P1 offbox + worker path, or a later packaging lab), record module SHA-256 manifest in GitHub docs or a release tarball under Leader control, define install procedure without `setup.sh` chown hazards.
- **Owner approval:** Yes, before any VPS copy.
- **Acceptance criterion:** Named frozen tree, SHA-256 list, and install dry-run plan accepted; nothing enabled.

### B. VPS identities, Unix socket, helper/worker isolation

- **Evidence:** D5A1/D5A2A created VPS `lg-backup` uid 994 gid 977 and empty mode-0700 `/var/lib/language-guard-backup`. D5A2B `DEPLOYMENT.txt` proposes handoff socket `lg-backup:lg-backup` 0600, helper as `guard`, worker as `lg-backup`, helper state dir `/var/lib/language-guard-helper` absent. D5A2B1 WSL systemd: PASS on peer denial and missing credentials; FAIL on positive transfer (helper `StandardError` polluted socket), invalid-cgroup refusal observation, interrupted transfer; BLOCKED StateDirectory chown. Step **not accepted**. D5A2B3 later proved native encrypt over the WSL socket path with helper accept + `ENCRYPTED`, units left inactive.
- **Result:** **GAP**
- **Impact:** Production isolation and helper/worker install are unproven on the VPS. StateDirectory interaction with the existing backup directory is untested (DEPLOYMENT caution).
- **Next action:** Resolve B1 unit defects (stderr to journal), measure StateDirectory, then a separately approved VPS unit install review—still disabled.
- **Owner approval:** Yes for any VPS unit write or daemon-reload.
- **Acceptance criterion:** Documented unit set with peer checks, credential fail-closed, no enabled timer, no live Drive upload from VPS.

### C. SQLite snapshot consistency and production prerequisites

- **Evidence:** `offbox/snapshot_copy.py` (P1): `source_conn.backup(memory)`, integrity check, WAL header rewrite to single-file image. D5A2B3 snapshot SHA-256 recorded and matched after decrypt. Production `accounts.db` journal mode **UNKNOWN** (status map + DEPENDENCIES). Production venv Python **UNKNOWN**. Helper opens source `mode=ro`.
- **Result:** **PASS** (lab implementation) / **UNKNOWN** (production prerequisites)
- **Impact:** Unknown journal mode or Python mismatch could block or alter snapshot behavior on the VPS.
- **Next action:** One Leader-authorized read-only VPS probe for Python version and journal mode (no backup activation).
- **Owner approval:** Yes for SSH.
- **Acceptance criterion:** Recorded Python version compatible with stdlib APIs used; journal mode documented; snapshot path still integrity-checked.

### D. age public/private key separation

- **Evidence:** ADR-024; B3 validation: native age v1.3.2 at WSL path only; worker `age -r`; identity not on backup host; ciphertext `dd6457a3…` decrypted offline with integrity ok. Production identity/recipient/oauth paths do not exist on VPS (status map).
- **Result:** **PASS** (architecture + lab) / **GAP** (production material)
- **Impact:** Without a production `age1pq1` recipient on the host and an offline identity on the recovery machine, no durable production encrypt/decrypt story exists.
- **Next action:** Owner generates production identity offline; install public recipient only; never place identity on VPS.
- **Owner approval:** Yes (keygen and recipient install).
- **Acceptance criterion:** Recipient file root-owned, worker LoadCredential or bind-mount only for recipient; identity absent from VPS; decrypt proof on recovery host with synthetic then later real artifact.

### E. Google OAuth lifecycle and least privilege

- **Evidence:** Scope `https://www.googleapis.com/auth/drive.file`. `credential.py` LoadCredential directory pattern. OAUTH-CHECKLIST.txt requires dedicated production GCP project. D5A2C2 live used External Testing refresh (~7 days from 2026-11-16 consent). Preflight: publishing status UNKNOWN; folder child permission was unknown before live shot; shared drives not requested. Live shot proved one refresh + upload for that lab client; not a production client.
- **Result:** **GAP**
- **Impact:** Lab token expiry; Testing status unsuitable for unattended backup; client-id visible in process list on live script; production least-privilege and rotation policy incomplete.
- **Next action:** Owner creates dedicated production project, publishes or otherwise obtains durable refresh policy, Desktop client, production folder, root-owned `oauth-refresh`; document rotation and `invalid_grant` fail-closed ops.
- **Owner approval:** Yes for all OAuth provisioning.
- **Acceptance criterion:** Production refresh survives beyond Testing seven-day limit (or documented In Production policy); worker-only credential; helper never sees token; scope exactly `drive.file`.

### F. Upload recovery, idempotency, and ambiguous outcomes

- **Evidence:** ADR-024; D5A2C fake tests: lose-final → RECONCILED, timeout-after reconcile, no second id, expired session UNKNOWN (C lab); C1R1 ties expired-session GET to attempt id and selects latest checkpoint numerically; large paused/restart VERIFIED on localhost. Live D5A2C2: one small multipart, `VERIFIED`, detail `downloaded-sha256`, ciphertext `a423f281…`. DELETE/PATCH refused in adapter. Connect/read timeout, 68 MiB cap, rejected certificate **not exercised** (preflight).
- **Result:** **PASS** (state machine + one live small object) / **UNKNOWN** (live large/resume and TLS edge cases)
- **Impact:** Ambiguous production uploads could strand reserved ids; TLS/timeout behavior unverified live.
- **Next action:** Keep no-second-create rule; optional later authorized edge-case drills; never auto-delete.
- **Owner approval:** Yes for any further Google call.
- **Acceptance criterion:** Production worker records `transport=https`, never allocates a second id after UNKNOWN, and `production_eligible` remains false until VERIFIED + downloaded-sha256.

### G. Backup scheduling, retention, stale detection, RPO/RTO

- **Evidence:** No off-box timer installed. KEEP=14 and accounts timer unchanged by design. Controlled retention/delete not implemented (DEPENDENCIES; zero-deletion). C1 readiness: 26h RPO / 4h RTO proposals only. HEALTH_MONITORING: stale alerting starts only after an approved threshold.
- **Result:** **GAP**
- **Impact:** Even a working uploader would not meet a freshness ceiling; remote object growth unbounded without an owner deletion policy.
- **Next action:** Decide schedule (e.g. daily after accounts snapshot), approve stale threshold separately from the 26h proposal, define owner-only retention.
- **Owner approval:** Yes for schedule, RPO/RTO numbers, and any deletion policy.
- **Acceptance criterion:** Written schedule + stale threshold accepted; timer installed disabled until activation gate; no deleting lifecycle without owner control.

### H. Existing 18B.8 monitoring integration

- **Evidence:** HEALTH_MONITORING Phase 18B.9 section: fixed future report lines; not installed. Notify socket still accepts only `check`, `report`, `backup-incident`, `recovery`, ≤12 lines, no free text. Collector/notifier must not receive age identity or OAuth refresh. Fake/localhost VERIFIED must not become the Drive line.
- **Result:** **GAP**
- **Impact:** Operators would not see Drive status, last success age, or restore-drill age in the 09:00 report; missed off-box runs lack a dedicated Healthchecks check.
- **Next action:** Design socket/check-line packing for off-box statuses without expanding free text; add missed-job Healthchecks when a schedule exists.
- **Owner approval:** Yes before changing notifier schema or enabling lines.
- **Acceptance criterion:** Report shows **NOT CONFIGURED** until activation; after activation, VERIFIED requires `production_eligible`; incidents name condition only.

### I. Recovery on a clean replacement machine

- **Evidence:** Lab `restore_check` and live synthetic restore: integrity ok, marker 1. Architecture: decrypt with offline identity onto a new path. No evidence of restoring a production accounts snapshot onto a clean replacement host. B2 fallback unprovisioned.
- **Result:** **GAP**
- **Impact:** Untested end-to-end disaster recovery; RTO proposal unverified.
- **Next action:** Owner-controlled restore drill plan: offline identity + downloaded ciphertext + new path + integrity_check; later optional B2 copy drill.
- **Owner approval:** Yes.
- **Acceptance criterion:** One successful clean-host restore of a designated artifact with recorded wall time; production data drill only with explicit approval.

### J. Remaining known test failures or blocked coverage

| Item | Status | Notes |
|---|---|---|
| D5A2B1 WSL systemd integration | Not accepted | FAIL transfer/cgroup/interrupt; BLOCKED StateDirectory |
| D5A2B cross-user namespace | Historically blocked | sudo password prompt in early lab |
| Connect/read timeout, body cap, bad cert | Not exercised | Preflight explicit |
| Live large resumable on Google | Not run | Localhost only |
| R1 37 regression / P1 32 checks | Cursor-reported | Leader reproduced 17 R1 focused only |
| Production journal mode / venv Python | Unknown | No VPS read in this review |
| UptimeRobot | UNVERIFIED / DEFERRED | Unrelated but still open monitoring gap |
| Synthetic Drive object | Remains | Deletion needs separate approval |
| External Testing refresh | Expiring | ~7 days after 2026-11-16 consent |

- **Result:** **GAP**
- **Impact:** Shipping before closing B1-class isolation and packaging risks false confidence from the one live shot.
- **Next action:** Treat J items as explicit exit criteria for later milestones; do not reopen D5A2C2 live.
- **Owner approval:** Case-by-case.
- **Acceptance criterion:** Each blocker either closed with evidence or explicitly deferred with Leader sign-off.

## Proven vs assumption

| Proven | Assumption / not proven |
|---|---|
| Native age 1.3.2 `age1pq1` encrypt on WSL | Same binary and recipient type on VPS |
| Helper→worker frame + encrypt to `ENCRYPTED` on WSL (B3) | Same units safe on VPS with StateDirectory |
| Fake + localhost upload state machine | All live TLS timeout/cert paths |
| One synthetic live VERIFIED + restore | Production DB backup; unattended schedule |
| `production_eligible` predicate in code | Any production_eligible=true record exists (none should until activation) |
| 18B.8 Telegram/email/Healthchecks for current checks | Off-box lines fit the closed socket without redesign |

## Stale documentation (identified, not silently rewritten)

| Document | Stale point | Handling |
|---|---|---|
| ADR-024 opening status | Still says live Google synthetic test is not authorized | Status line needs a dated note that D5A2C2 one-shot is closed; architecture bullets stay |
| `handoffs/2026-11-16-phase-18B9-offbox.md` | Prefaces that live test is NOT AUTHORIZED | Historical snapshot; leave body; durable truth is current_state / ACTIVE_HANDOFF |
| PHASE-18B.9C1 | Still contains historical `rclone copy` command text | Already has 2026-11-16 correction pointing at ADR-024; keep as historical design |
| HEALTH_MONITORING pre-closure STOP paragraph | Contradicts opening CLOSED state | File already warns; no rewrite in this review |
| ADR-024 “no production OAuth client created by this decision” | Still true for **production**; lab OAuth existed for D5A2C2 | Clarify “production” vs lab in status only |

Architectural decisions (standalone `.age`, Drive adapter over rclone, VERIFIED=downloaded SHA-256, no DELETE/PATCH, offline identity) remain in force.

## Proposed architecture decisions (for Leader, not adopted here)

1. **Canonical source freeze:** One lab tree (P1 offbox modules + approved units) becomes the packaging baseline; older labs remain evidence-only.
2. **Production OAuth:** Dedicated GCP project; durable refresh policy; never reuse External Testing for unattended VPS backup.
3. **Activation gate:** Daily report stays **NOT CONFIGURED** until packaging, VPS isolation, production recipient, production OAuth, monitoring lines, and an owner restore drill are accepted.
4. **Retention:** No automated Drive delete in-agent; owner-approved retention procedure only.
5. **RPO/RTO:** Keep 26h/4h as proposals until a schedule and stale threshold are separately accepted.
6. **18B.9C2:** Remains a named external drill and stays **NOT AUTHORIZED** by this review; D5A2C2 does not satisfy 18B.9C2.

## Prioritized blockers

1. No repository-packaged, SHA-pinned deployable offbox tree.
2. D5A2B1-class helper/worker systemd isolation not accepted for production.
3. No production age recipient/identity material; age binary absent on VPS.
4. No durable production OAuth project/token/folder.
5. No schedule, stale threshold, or owner retention policy.
6. Off-box monitoring lines and missed-job check not installed.
7. No clean-host recovery drill with offline identity.
8. Production Python version and `accounts.db` journal mode unread.
9. Live TLS/timeout/large-resume edge coverage UNKNOWN.
10. Lab External Testing token approaching expiry (operational hygiene; not a production blocker by itself).

## Suggested future milestone sequence

Planning names only. None of these are authorized by this document.

1. **D5A2C3 acceptance** — Leader accepts or amends this review.
2. **D5A2D0 packaging freeze** — pin module hashes; write install manifest; still no VPS enable.
3. **D5A2D1 read-only VPS facts** — Python version, journal mode, confirm empty backup dir unchanged.
4. **D5A2D2 unit isolation correction** — fix helper stderr/cgroup lessons from B1; WSL re-proof; StateDirectory measured.
5. **D5A2D3 production crypto materials** — owner age-keygen; recipient install plan.
6. **D5A2D4 production OAuth** — dedicated project; durable refresh; folder; LoadCredential layout.
7. **D5A2D5 monitoring wiring design** — fit Drive lines into 18B.8 socket; Healthchecks for missed off-box job.
8. **D5A2D6 schedule and stale policy** — accept or revise RPO/RTO; timer drafted disabled.
9. **D5A2D7 clean-host restore drill** — synthetic first; production data only with explicit approval.
10. **Activation review** — separate Leader gate; only then may the report leave **NOT CONFIGURED**.

## Authorization / STOP

This review changed documentation only. It does not authorize implementation, VPS changes, Google calls, credential changes, source commits, Cloud Sync, a second live attempt, or remote deletion.

Production readiness is **not** claimed.
