# Phase 18B.9 — Production deployment readiness runbook (reuse package)

Status: **RUNBOOK / READINESS PACKAGE — not executed.** Does not authorize SSH,
credential provisioning, Google API calls, Drive transfers, key generation,
isolation service execution, backup/restore, timer enablement, or activation.

Baseline: GitHub `dc9ec43355f686f62842d0cddabf16ce05ca2d72` plus the source PR
that lands the installed-layout packager `verify` fix (see Issue #8 readiness
report). Historical pre-fix audit **UNSAFE** and D5A2D2/D5A2D3 **FAIL** remain
preserved. Current VPS evidence: inactive install **INSTALL PASS**; post-fix
Gate A **PASS** + Gate B **CONFIG PASS**.

## 1. Component reuse matrix

| Component | Classification | Evidence / notes |
|---|---|---|
| D5A2D0-P1 15 frozen modules + SHA inventory | **VALIDATED** + **DEPLOYED INACTIVE** | Source-merged; VPS `/opt/language-guard-offbox/offbox` 15/15 MATCH |
| Runtime-trust layout + unit contracts (PR #15) | **VALIDATED** + **DEPLOYED INACTIVE** | Gate A/B PASS; `/usr/bin/python3 -I`; units loaded, not enabled |
| Packager `install-execution-tree --production` | **VALIDATED** | Used for corrective install; installed-layout `verify` fixed in source PR |
| Native age v1.3.2 Linux amd64 + `age1pq1` encrypt path (D5A2B3) | **VALIDATED** (lab) / **LOCAL ONLY** binary | Lab PASS `ENCRYPTED`; WSL binary present; **not** on VPS |
| Lab age archive SHA-256 `cbe24006…` / binary SHA-256 `eb7dd1b5…` | **VALIDATED** artifact identity | Reusable as *versioned binary bytes*; not a secret |
| Lab `age1pq1` recipient + offline identity | **LOCAL ONLY** | Public recipient prefix/length observed in preflight; **do not reuse for production** |
| HTTPS Drive adapter + oauth refresh exchange (D5A2C1-R1) | **VALIDATED** (source-merged) | Frozen modules; no adapter redesign required for reuse |
| D5A2C2 one-shot synthetic Drive `VERIFIED` | **VALIDATED** (historical one-shot) | Ciphertext `a423f281…`; **do not rerun**; not production |
| D5A2C2 External Testing OAuth refresh (~7-day) | **LOCAL ONLY** / expired-policy | Unsuitable for unattended production |
| Production GCP project / durable consent / Desktop client | **PRODUCTION MISSING** | Owner action |
| Production Drive folder id | **PRODUCTION MISSING** | Owner action; My Drive; scope `drive.file` |
| VPS age binary at `/usr/local/lib/language-guard-age/age` | **PRODUCTION MISSING** | Unit `LG_AGE_BIN` already points here |
| VPS public recipient `/etc/language-guard/age-recipient` | **PRODUCTION MISSING** | Public only; never identity |
| VPS `LoadCredential` oauth-refresh | **PRODUCTION MISSING** | Intentionally absent; fail-closed on start |
| Controlled VPS isolation suite (D5 revised classes) | **PRODUCTION MISSING** | D2/D3 FAIL historical; D5 revised gate accepted as *test design* only |
| Monitoring off-box lines in 09:00 report | **PRODUCTION MISSING** | Templates exist; not wired |
| Clean-host restore drill (production ciphertext) | **PRODUCTION MISSING** | Lab synthetic only |
| Timer enable / activation / Cloud Sync | **PRODUCTION MISSING** | Explicitly off |

## 2. Age identity decision

**Do not reuse the lab offline identity or lab public recipient for production.**

Reasons (non-secret): lab material was used for synthetic encrypt/decrypt and
live Drive shots; production recovery must be Owner-controlled and rotatable
without coupling to lab evidence trees.

**Reuse:** the accepted **age v1.3.2** Linux amd64 binary artifact (archive
SHA-256 `cbe24006683f8eb669266162894b9a522a1af52f2665fbc63a4bb032ed26ac10`;
extracted binary SHA-256 `eb7dd1b518f0a307c99cd97782623c5321da049154b04acd2d98d21aa7bc9b2c`)
and the `age1pq1` recipient *type*. Plugins were not required and must not be
installed on the VPS.

## 3. OAuth / Drive readiness (metadata only)

Observed from accepted docs/labs (no credential files opened this task):

- Scope: exactly `https://www.googleapis.com/auth/drive.file`.
- Worker-only credential via systemd `LoadCredential=oauth-refresh:…`.
- Helper must never see tokens (`InaccessiblePaths` includes `/etc/language-guard` and `/run/credentials`).
- D5A2C2 used External Testing refresh policy (~7 days after consent) — **not** production-durable.
- Publishing status of any existing GCP project: **UNKNOWN**.
- Whether a prior lab folder/client can be reused: **UNKNOWN** and **not recommended**.
- Adapter source changes for production reuse: **none required** (fail-closed live transport until `LG_DRIVE_FOLDER` / `LG_UPLOAD_ENABLED` are explicitly set under a later activation gate).

## 4. Staged execution package (Owner-authorized sessions later)

Each stage needs its own Product Owner authorization. This file is not permission.

### Stage 0 — Offline Owner crypto (no VPS)

1. Generate a **new** production age identity offline; store offline only.
2. Export public `age1pq1` recipient text to an Owner-controlled offline file.
3. Confirm decrypt of a tiny synthetic ciphertext on a clean offline host.

### Stage 1 — Durable Google OAuth + Drive folder (Owner machine)

1. Create a dedicated production GCP project (not External Testing lab client).
2. Configure OAuth consent for unattended production use (durable refresh policy).
3. Create Desktop OAuth client; keep client JSON offline.
4. Consent once; store refresh token offline for later VPS install only.
5. Create/designate a My Drive folder owned by that identity; record folder id offline.
6. See also [OFFBOX_OAUTH_CREDENTIALS_RUNBOOK.md](OFFBOX_OAUTH_CREDENTIALS_RUNBOOK.md).

### Stage 2 — Safe VPS credential/binary provisioning (write session)

Install only, still **no** timer enable and **no** `LG_DRIVE_FOLDER` / `LG_UPLOAD_ENABLED`:

1. Install age v1.3.2 binary to `/usr/local/lib/language-guard-age/age` (`root:root 0755`); verify SHA-256.
2. Install public recipient to `/etc/language-guard/age-recipient` (`root:root 0640` or stricter as approved); confirm prefix `age1pq1`, no `AGE-SECRET`.
3. Install `oauth-refresh` for `LoadCredential` (`root:root 0400`).
4. Optionally sync packager fix into `/opt/language-guard-offbox` if the source PR is merged (modules stay frozen).
5. Re-run static verify from installed packager; confirm units still inactive.

### Stage 3 — Controlled isolation tests (execution session)

Exercise revised isolation classes without production DB leakage and without live upload:

- Positive framed helper→worker handoff
- Unauthorized peer / cgroup denial
- Interrupted transfer fail-closed
- Missing credentials fail-closed
- StateDirectory / ownership hazards avoided (no `StateDirectory=` on backup dir)

Keep socket/timer disabled except as required for the explicit test harness under that authorization. Preserve historical D2/D3 FAIL labels.

### Stage 4 — Backup verification + restore drill

1. Synthetic or explicitly approved non-production artifact encrypt on VPS path.
2. Offline decrypt + `PRAGMA integrity_check` on clean host ([OFFBOX_CLEAN_HOST_RESTORE_RUNBOOK.md](OFFBOX_CLEAN_HOST_RESTORE_RUNBOOK.md)).
3. Only later: authorized production-folder upload with `VERIFIED` download-sha256 match.

### Stage 5 — Monitoring + activation criteria

Before enablement:

- Off-box lines wired into 09:00 report ([OFFBOX_MONITORING_SCHEDULE_TEMPLATES.md](OFFBOX_MONITORING_SCHEDULE_TEMPLATES.md)); default Drive line remains **NOT CONFIGURED** until production-eligible provenance.
- Separate Healthchecks missed-job URL (not the report heartbeat).
- Explicit Owner acceptance of RPO/RTO proposals (26h / 4h remain proposals).
- Timer remains disabled until a dedicated activation approval sets schedule + upload env.

## 5. Owner-only actions checklist

- [ ] New production age identity (offline) + public recipient
- [ ] Dedicated production GCP project + durable OAuth consent + Desktop client
- [ ] Production refresh token + My Drive folder id
- [ ] Authorize VPS age binary + recipient + oauth-refresh install
- [ ] Authorize isolation execution package
- [ ] Authorize restore drill / first production-eligible upload
- [ ] Authorize monitoring wiring and, separately, timer activation

## 6. Explicit non-goals

- No second D5A2C2 live shot.
- No Cloud Sync.
- No reuse of lab private identity for production recovery.
- No secret values in git, issues, or chat.
- No claim that Gate A/B PASS equals production backup readiness.
