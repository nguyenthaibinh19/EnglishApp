# Current state

> First file a new agent should read. Keep this concise and update when phases complete.

## Latest verified coordination checkpoint — 2026-11-23

**Current priority:** **Phase 18C.4 — direct production Cloud Sync.** **18C.4P-R1 final package is READY FOR REVIEW** (`APP_18C4P_R1_FINAL_DEPLOYMENT_PACKAGE_READY_FOR_REVIEW`). The copy is four LF files: `sync_http.py`, `sync_store.py`, `srs.py`, and `sync_restore_verify.py`. The accounts timer stays. The sync backup timer stays disabled. The desktop candidate was not launched. Production Cloud Sync **OFF**. Real two-PC acceptance is **NOT TESTED**. Staging is **NOT STARTED**. **18B.9 PAUSED.** 18B.10B–E are **NOT AUTHORIZED.** See [PHASE-18C.4P-R1-final-deployment-package.md](plans/PHASE-18C.4P-R1-final-deployment-package.md).

**Phase 18B.10A: AUDIT ACCEPTED, IMPLEMENTATION DEFERRED** (`APP_18B10A_ARCHITECT_AUDIT_ACCEPTED_DEFERRED`). The audit and its proposed, unapproved numerical limits stay in [PHASE-18B.10A-api-abuse-resistance-audit.md](plans/PHASE-18B.10A-api-abuse-resistance-audit.md). Do not implement 18B.10B, 18B.10C, 18B.10D, or 18B.10E.

**18C.3B CLOSED — Architect Accepted** (`APP_18C3B_PR28_ARCHITECT_MERGE_APPROVED`). PR [#28](https://github.com/nguyenthaibinh19/EnglishApp/pull/28) is merged. Merge `610d979434f8ff10274e8000916563e1e2f57126`. Approved source HEAD `867700198665edb80ba5b96fbf72a5bd0ae96fa2` on base `2cea161f5453909f2503ee1bc3cb41c153603010`. Focused tests: **94 passed, 0 failed, 1 skipped** (Cursor-reported). `test_windows_file_symlink_fails_closed` remains **UNVERIFIED**.

**18C.1 CLOSED — Architect Accepted** (PR #20, merge `8e94f77491cc2f318c93fc511e258d0299ff4d03`): local core Account Sync demonstration — schema-v3 progress tables + `/api/sync/progress/*` behind the existing default-off flag; per-account local SQLite; vocabulary + event-first progress sync engine; localhost two-device demo; explicit vocabulary conflict freeze (no silent LWW).

**18C.2 CLOSED — Architect Accepted** (PR #21): signed-in Tkinter flows via `study_data.open_study_data()`; preferences v1 with base-revision optimistic concurrency + explicit Keep local/server; UTC `occurred_at` day buckets + signed-in Today/streak alignment; tombstone-safe vocab resolve (`local_as_new`); in-flight late-ack rebase; GUI walkthrough evidence under `qa-evidence/phase18c2-gui-sync/`. Guest mode still uses guest files with local-calendar Progress. Full ADR-022 AttemptHistory ledger/overlap import remains deferred (vocab consent import only). See [PHASE-18C.2-acceptance.md](plans/PHASE-18C.2-acceptance.md). Production activation remains separately gated.

**18B.9 historical note (paused):** SOURCE INSTALLED INACTIVE — NOT ACTIVATED. Owner-authorized VPS packaging sync applied approved main `eb869eaf310504862a10c902ea2e8803fbab0b53` (PR #16 + #17) under `/opt/language-guard-offbox/`. Installed-layout `verify`/`verify-deps` PASS; frozen 15/15 MATCH; wrapper LF pin `cc9ce5b7aadbd690f800a0a29cacfd0bbaf0c5f46d3c107ac3100ae1bc9e8427`. Off-box units remain disabled/inactive. **No** `daemon-reload`, start/enable, OAuth/Drive, credentials, backup/restore, isolation, or Cloud Sync.

**Source merges:** PR [#17](https://github.com/nguyenthaibinh19/EnglishApp/pull/17) upload entrypoint (`2602105` / merge `b6e515e`); PR [#16](https://github.com/nguyenthaibinh19/EnglishApp/pull/16) packager verify fix. Design: [OFFBOX_RUNTIME_TRUST.md](procedures/OFFBOX_RUNTIME_TRUST.md). Runbook: [OFFBOX_PRODUCTION_DEPLOYMENT_RUNBOOK.md](procedures/OFFBOX_PRODUCTION_DEPLOYMENT_RUNBOOK.md). OAuth contract: [OFFBOX_OAUTH_CREDENTIALS_RUNBOOK.md](procedures/OFFBOX_OAUTH_CREDENTIALS_RUNBOOK.md).

**Reuse posture:** age v1.3.2/`age1pq1`, Drive adapter libraries, and D5A2C2 one-shot remain lab-validated; lab OAuth/identity must **not** be reused for production. Upload entrypoint is **installed inactive** on VPS — not enabled/operational. Credential delivery contract is in source; **real provisioning** absent (`oauth-refresh` absent). Isolation must stay synthetic-only.

Historical pre-fix executable-path audit **ACCEPTED UNSAFE** preserved ([#7009010670](https://github.com/nguyenthaibinh19/EnglishApp/issues/8#issuecomment-7009010670)). D5A2D2/D5A2D3 **FAIL** preserved. Owner actions still required for age/OAuth/folder/credential install, isolation execution, restore drill, monitoring, and activation.

**Existing operational facts (Cursor-reported):** VPS Python `3.14.4`; journal `delete`; `guard` 995/982; `lg-backup` 994/977. Drive **NOT CONFIGURED**; Cloud Sync **OFF**.

**AI separate workstream:** `C-APP-AI-001 v0.2.0` ACCEPTED; PR #14 MERGED. **AI-M4 / LocalAIProvider NOT AUTHORIZED.**

**The 2026-11-16 paragraph below is a historical snapshot and includes status assertions superseded by this 2026-11-19 checkpoint; preserve for provenance, do not use it as the current authority.**

**Historical snapshot date:** 2026-11-16. The off-box map is [PHASE-18B.9-offbox-status.md](plans/PHASE-18B.9-offbox-status.md). A name such as `18B9D4C` means Phase 18B.9 step D4C, not Phase 18B.4. Phase 18B.7 remains **CLOSED**. Phase 18B.8 is **CLOSED — Leader Accepted, 2026-11-10**. This closure covers monitoring infrastructure. It does not activate vocabulary Cloud Sync. Production deployment is **PASS**. Natural operational verification is **PASS**. The user received the scheduled Telegram and email. Healthchecks accepted the 2026-11-10 heartbeat. Monitoring integration is commit `f57bcc6`. This closure commit completes the documentation synchronization. Cloud Sync stays **OFF**. `study_sync.db` is absent. The sync-verify timer is enabled and operational. Its natural result was `SKIPPED`, which is not a successful restore. The sync-backup timer is installed, disabled, and inactive. UptimeRobot external uptime monitor: **UNVERIFIED / DEFERRED**. Phase 18B.9B is **CLOSED — Leader Accepted, 2026-11-10**, commit `274156e`. That commit is a local synthetic recovery proof, not a production uploader. Its historical full suite was 30 passed and 1 skipped. A later wrong-password check passed, and the full suite was not rerun after that correction. Phase 18B.9 remains **OPEN**. Google Drive, using the existing 5 TB Google AI Pro Student allowance, is the preferred pre-public store. That choice adds no storage subscription while the allowance remains. Backblaze B2 EU Central is the fallback and is not provisioned. B2 is not assumed to be append-only, and its Object Lock and deleting lifecycle stay off. No production remote backup has been run. Phase 18B.9C1 is **DESIGN ACCEPTED, 2026-11-10**. A standalone age `.age` artifact remains the architecture. Age v1.3.2 and an `age1pq1` recipient were later validated on WSL, and the transfer is the Drive adapter in [ADR-024](decisions/ADR-024-offbox-age-drive.md), not `rclone copy`. That pipeline is not installed on the VPS. Daily off-box status in the 09:00 Europe/Amsterdam report, failure and stale alerts, and a restore drill are mandatory and are not installed. Before activation the report says Google Drive is **NOT CONFIGURED**. A 26-hour RPO and a 4-hour RTO remain proposals. Phase 18B.9C1 is not a deployment. Phase 18B.9C2 is **NOT AUTHORIZED**. Phase 18B.9D5A2C1 is **CLOSED — Leader Accepted, 2026-11-16**. That acceptance is the localhost HTTPS transport milestone, including the R1 corrections. It is not a production deployment and not a VPS change. Phase 18B.9D5A2C2 is **CLOSED — Leader Accepted, 2026-11-16**. That acceptance is one authorized synthetic Google Drive live shot only, recorded at documentation checkpoint `29317d0`. It is not production off-box backup. A second live attempt is **NOT AUTHORIZED**. The synthetic Drive object remains until a separate deletion approval. D5A2C3 Production Readiness Review is **Leader Accepted as PLANNING COMPLETE, 2026-11-16** ([PHASE-18B.9D5A2C3-production-readiness.md](plans/PHASE-18B.9D5A2C3-production-readiness.md)); overall production status remains **NOT READY**. Its proposed future implementations are recommendations, not automatic authorizations. D5A2D0 canonical source inventory remains the planning basis ([PHASE-18B.9D5A2D0-canonical-source-inventory.md](plans/PHASE-18B.9D5A2D0-canonical-source-inventory.md)). D5A2D0-P1 is **CLOSED — Leader Accepted, 2026-11-16**, for controlled source import only: review branch `phase18b9/d5a2d0-p1-source-import` commit `98b590e`, Leader-verified 17-file allowlist and 15/15 SHA-256 MATCH. That branch is not merged and is not a deployment. D5A2D2 WSL isolation correction ran once with automated score **OVERALL FAIL** ([PHASE-18B.9D5A2D2-wsl-isolation.md](plans/PHASE-18B.9D5A2D2-wsl-isolation.md)); canonical hashes unchanged; new test units inactive; not a VPS install. GOV-0A is Leader Accepted with corrections. GOV-0B1 is **CLOSED — Leader Accepted**; canonical ecosystem governance is under [ecosystem/README.md](ecosystem/README.md) (EnglishApp-hosted; Web/AI link, do not fork). Three repos confirmed: App public; Web private; AI private (`langstudyguard-ai` exists — no App integration accepted). GOV-0C is **NOT AUTHORIZED**. GOV-0E GitHub Project is **PLANNED / DEFERRED**. EnglishApp remains the active workstream under ChatGPT → Cursor; Product Owner leads Web/AI day-to-day (milestone reports to ChatGPT). D5A2D2 remains FAIL (historical). D5A2D3 remains FAIL (historical). D5A2D4 is **CLOSED — Leader Accepted: REVISE TEST** (E1/E2). D5A2D5 is **CLOSED — Leader Accepted: REVISED WSL ISOLATION SAFETY GATE**. D5A2D6 is **CLOSED — Leader Accepted: READY_FOR_SOURCE_INTEGRATION_REVIEW** (not merge approval). D5A2D7-R2 **CLOSED — LEADER ACCEPTED**; D5A2D7-P1 **CLOSED — LEADER ACCEPTED** — review branch `phase18b9/d5a2d7-source-candidate` @ `e2160e77c4849606cad5e614dedfd2f79d8088dc` — **NOT MERGED**, **PR NOT CREATED**, **NOT DEPLOYED** — [PHASE-18B.9D5A2D7-source-integration-candidate.md](plans/PHASE-18B.9D5A2D7-source-integration-candidate.md). GOV-0E private Project `LangstudyGuard` is **CLOSED — LEADER ACCEPTED** (setup/docs only) — [GITHUB_PROJECT_OPERATIONS.md](ecosystem/GITHUB_PROJECT_OPERATIONS.md). GOV-0E-A1 merged (PR #10 / `9c36a4f`); GOV-0E-A2 **CLOSED — Leader Accepted** (S1/S2; #11 Done) — [GOV-0E-A2-live-smoke.md](plans/GOV-0E-A2-live-smoke.md). **D5A2D7 SOURCE MERGED — NOT DEPLOYED** (PR #12 / c03a0f5). **18B.9 accelerated readiness SOURCE MERGED — NOT DEPLOYED** (PR #13 / d6643e0; pinned D5A2D0-P1 verify-before-copy). Production still NOT READY. Production still NOT READY. AI-M2 implementation committed @ `5cd4dd2` (architectural acceptance pending; `C-APP-AI-001` still PROPOSED / IN REVIEW; App LocalAIProvider NOT AUTHORIZED). Import `98b590e` freeze unchanged. No production readiness implied. Phase 18B.9 remains OPEN. Production stays **NOT READY**. Google Drive stays **NOT CONFIGURED**. Cloud Sync stays **OFF**. The Windows Startup `--lock` hotfix remains **DEFERRED** until the affected computer is available. It is not diagnosed. Website W1 is handled by Antigravity in a separate workspace.

**Installer patch:** committed at `3dff28d3f78a22da0fda73a50168ed9c3d6e9d57`. This documentation status update follows that commit and does not name its own SHA. Remote `main` is not claimed by this commit.

**Pre-integration baseline, read on 2026-11-08:** `09556f909b0ce6d8dcc27816800ef6bcd308f1ab`. That SHA is the parent of the installer commit. It is not the current HEAD of this documentation update.

**Deployed server source:** `d0f2f004c85ce9f4265d33bd034ba18423f1e3a5`. A newer Git commit is not a deploy.

**Phase 18B.8 source:** `24e600bacff67d134217deb931eb953721c9ea9b`, merge `65b045a62dc0f0e1f3e6f7d156ed22311e9bc705` (CLOSED — Leader Accepted, 2026-11-10; monitoring only; Cloud Sync OFF)

**Accounts backup mode source:** `09556f909b0ce6d8dcc27816800ef6bcd308f1ab` (deployed on the VPS; Step A FULL PASS; not the whole server tree)

**ADR-022 accepted commit:** `d9d0fe3` (event-first account sync architecture). **18C.1 implements the local vertical slice in source** (schema v3 + client); production flag remains off.

**Phase 18B.5 accepted commit:** `69307892f779e61de7b99563eb5c76ad4296cbcc` (restore verification source; 18B.8 later enabled the production verifier; a `SKIPPED` result is not a successful restore)

**Phase 18B.6 accepted commit:** `39f3a0bbbc47dda2c213324a820d198d0f0c3501` (isolated local staging; CLOSED; staging unit not installed)

**Article-Matching Hotfix accepted commit:** `d0f2f004c85ce9f4265d33bd034ba18423f1e3a5` (CLOSED; GitHub-verified; not a Windows release)

**Phase 18B.7 accepted deploy:** `d0f2f004c85ce9f4265d33bd034ba18423f1e3a5` (CLOSED; controlled dark deploy; Sync remains OFF; no sync timer was installed in that deploy)

**Phase 18B.4 accepted commit:** `d277791` (sync backup timer contract; ADR-021 Accepted; 18B.8 later installed the unit and left the timer disabled)

**Phase 18B.3 accepted commit:** `97f7b25` (production-readiness plan; no timer, no deploy)

**Phase 18B.2 accepted commit:** `5f4251a` (sync backup and restore; ADR-020 Accepted; not scheduled)

**Phase 18B.1 accepted commit:** `599e473` (vocabulary sync HTTP; ADR-019 Accepted)

**Phase 18A accepted commit:** `94f1bf7` (vocabulary sync store; ADR-018 Accepted)

**Accepted Vocabulary Manager hotfix:** `ed51a92` (canonical `meaning` + Listbox `exportselection=False`)

**Phase 17C accepted commit:** `c0b2d2d375d1b258a5c14fec5f713065875ee0fa`

**Windows Startup:** one user shortcut exists and points at the installed safety build with `--lock`. That automatic start has not been executed. See **Windows installation safety** below.

## Product

**StudyGuard / langstudyguard** is a Windows desktop study-lock app that helps a learner practice vocabulary (and optional reading / listening) before dismissing a locked fullscreen session.

- **Stack:** Python + Tkinter desktop client
- **Account server:** Hetzner VPS; domain `langstudyguard.com`
- **Distribution:** GitHub Releases (`langstudyguard.zip` / `.exe`); unsigned binary (SmartScreen friction known)
- **ScreenGuard / startup lock:** works and must remain untouched unless an explicit phase says otherwise
- **AI:** production requests go through the account server; OpenAI production key must never be embedded in the desktop executable

### Study languages (canonical registry)

`nl`, `en`, `fr`, `de`, `es`, `it`, `pt`

Dutch (`nl`) is the historical default for some compatibility paths — core architecture must not assume Dutch.

### UI / native languages

`vi`, `en` — distinct from study language.

## Current architecture map

```text
VocabularyEntry
      │
      ├──────────────┐
      ↓              ↓
   Progress      AttemptHistory
      ↓              ↓
     SRS         MistakeBook
      │              │
      └──────┬───────┘
             ↓
      DailyStudyPlanner
             ↓
        StudySession
             ↓
      Tkinter application
```

AI path:

```text
quiz / reading / listening / vocab enrich / account_server
        ↓
   ai_teacher facade
        ↓
      AIService
        ↓
     AIProvider
        ↓
 OpenAIProvider   (future: StudyGuardAIProvider, LocalModelProvider)
```

Production vocab enrichment:

```text
Word Detail → AccountServerVocabularyEnrichmentProvider
    → account /api/enrich → AIService → EnrichmentDraft → review → Apply
```

Production Listening content:

```text
listening_source (local target select)
    → AI generate_listening (/api/listening when frozen)
    → validated ListeningItem → cache
    → ListeningSession → WindowsLocalTTSProvider
```

Major UI surfaces: Home Dashboard, Progress Dashboard, Vocabulary Library + Word Detail, Mistake Book, study session (quiz + optional reading + optional listening).

## Persistence (local, per study language)

Typical layout under AppData language folders:

| File | Role | Identity / notes |
|------|------|------------------|
| `vocab.json` | Vocabulary entries | Stable UUID `id`; lexical + optional enrichment |
| `progress.json` | Aggregate learning + SRS | **version 3**, words keyed by vocab UUID; `legacy_index` for compat |
| `attempts.jsonl` | Append-oriented attempt events | Prefer `vocab_id`; `word` is historical snapshot |
| `settings.json` | App/settings | Native language, study languages, activities, etc. |

### Canonical lexical fields

```text
id, word, meaning,
alternatives?, part_of_speech?, note?,
examples?, pronunciation?, forms?
```

Enrichment storage + draft/review + production AI provider:

- `examples`: `[{text, meaning?}, ...]`
- `pronunciation`: `{ipa}` when present (storage only; AI v1 does **not** generate IPA)
- `forms`: subset of `plural` / `past` / `past_participle` / `comparative` / `superlative`
- `EnrichmentDraft` is ephemeral; AI proposes POS/forms/examples; learner must Apply
- Production path: authenticated `/api/enrich` on the account server

Legacy read still supported: `vi`, `alt`, `type`, `nl`, `en`, string `example`. New writes use canonical fields. Account HTTP wire may still send `vi` — that is **not** the local canonical field.

## Current test commands

```text
python -m pytest
python app/smoke_test.py
```

**Test notes (do not treat as a permanent green invariant):** a pre-17C-deploy snapshot once reported ~340 pytest passes. On 2026-11-02, at `d0f2f004c85ce9f4265d33bd034ba18423f1e3a5`, full `python -m pytest` was 487 passed, 7 skipped, and smoke passed every check. The seven skips are the Linux symlink tests and `systemd-analyze`; they were not run as passes. Do not claim a later tree is green without fresh evidence.

Later evidence, not a full-suite rerun of this worktree:

| Evidence | Result | What it is |
|---|---|---|
| Leader Linux QA of merge `65b045a` | 106 passed, 0 failed, 0 skipped | Health, restore verification, backup alert, and package tests. Not a VPS install |
| Leader Linux QA of the accounts-backup mode patch that became `09556f9` | 127 passed, 0 failed, 0 skipped | Those suites plus the sync-backup tests, including mode `0600` under umask `0022`. Not a deploy |
| `pytest tests/test_install.py` on this worktree, 2026-11-08 | 15 passed, 0 failed, 0 skipped | Mocks and temporary paths only. Does not launch the real executable |

## Current development position

```text
Completed: Phase 14 — Vocabulary Model v2
Completed: Phase 14.5 — Project Memory Foundation
Completed: Phase 15A — Vocabulary Enrichment Data Model
Completed: Phase 15B — Vocabulary Enrichment Draft & Review Foundation
Completed: Phase 15C — Production AI Vocabulary Enrichment v1
Completed: Phase 16 — Learning Progress Dashboard v1
Completed: Phase 17A — Listening Foundation (+ hardening / product-QA patch)
Completed: Phase 17A.1 — Window Lifecycle Stabilization
Completed: Phase 17B — Windows Local TTS Provider v1 (+ final hardening / async race fix)
Completed: Phase 17C — AI-generated Listening content v1 (production accepted)
Completed: Phase 18A — Account Cloud Sync Foundation (accepted ``94f1bf7``; isolated ``study_sync.db`` vocabulary store; ADR-018 Accepted)
Completed: Phase 18B.1 — Authenticated vocabulary sync HTTP (accepted ``599e473``; default-off; server copy from 18B.7 with the flag unset; no desktop client; ADR-019 Accepted)
Completed: Phase 18B.2 — Sync DB backup and restore (independently verified ``5f4251a``; ADR-020 Accepted; backup not scheduled; sync flag OFF; server copy from 18B.7 left unscheduled; no desktop client)
Completed: Phase 18B.3 — Production-readiness plan (accepted ``97f7b25``; planning only; sync flag OFF; backup not scheduled; no desktop client)
Completed: Phase 18B.4 — Sync backup timer units and alert contract (accepted ``d277791``; 18B.8 installed the unit into systemd and left the timer disabled; no production paging; sync flag OFF)
Completed: Phase 18B.5 — Restore verification (GitHub-verified ``69307892f779e61de7b99563eb5c76ad4296cbcc``; 18B.8 enabled the production verifier; a ``SKIPPED`` result is not a successful restore)
Completed: Phase 18B.6 — Isolated local staging (CLOSED ``39f3a0bbbc47dda2c213324a820d198d0f0c3501``; repository-only; staging unit not installed)
Completed: Phase 18B.7 — Controlled dark deploy (CLOSED; server source ``d0f2f004c85ce9f4265d33bd034ba18423f1e3a5``; Sync OFF; no sync timer)
Completed: Phase 18B.8 — Production health monitoring (CLOSED — Leader Accepted, 2026-11-10; monitoring only; Cloud Sync OFF; sync-verify timer enabled; sync-backup timer installed and disabled)
Step A FULL PASS: accounts backup safety deployed from ``09556f9``. Latest natural snapshot ``accounts-20261110-032712.db`` is mode ``0600``.
Completed: Phase 18B.9B — Local encrypted recovery proof (CLOSED — Leader Accepted, 2026-11-10, ``274156e``; local synthetic restic only; historical suite 30 passed, 1 skipped; later wrong-password check passed; full suite not rerun after that correction; not a production uploader)
Phase 18B.9 remains OPEN. Google Drive 5 TB is the preferred pre-public store and adds no storage subscription. Backblaze B2 is the fallback and is not provisioned. No production remote backup has been run. The local Drive adapter is not installed.
Phase 18B.9C1 is DESIGN ACCEPTED, 2026-11-10. Age v1.3.2 and an `age1pq1` recipient are validated on WSL only. [ADR-024](decisions/ADR-024-offbox-age-drive.md) replaces the `rclone copy` transfer. The production pipeline is not installed. Daily off-box monitoring, failure and stale alerts, and a restore drill remain mandatory and uninstalled. Google Drive is NOT CONFIGURED. Phase 18B.9C2 is NOT AUTHORIZED.
Leader accepted 18B.9D4C, 18B.9D5A2B3, 18B.9D5A2C, 18B.9D5A2C1, and 18B.9D5A2C2. D5A2C1 is CLOSED — Leader Accepted, 2026-11-16, as a localhost milestone. The accepted localhost code is the R1 local lab and is not in this repository. The original localhost run reported 37 passed. R1 reported 17 focused passes, which the Leader reproduced, and 37 regression passes, which were not independently rerun. D5A2C2 is CLOSED — Leader Accepted, 2026-11-16, as one synthetic live shot only. Cursor reported one-invocation PASS with ciphertext SHA-256 `a423f281ca55ae1a833cf40d2df854e84678fed24a28d89742215b101593f97c`. Documentation checkpoint `29317d0`. A second live attempt is NOT AUTHORIZED. The synthetic Drive object remains until separate deletion approval. D5A2C3 is Leader Accepted as PLANNING COMPLETE; production remains NOT READY. D5A2D0 inventory proposed a 15-module freeze from D5A2C1-R1. D5A2D0-P1 is CLOSED — Leader Accepted, 2026-11-16, for controlled source import only (`phase18b9/d5a2d0-p1-source-import` @ `98b590e`; Leader-verified 15/15 hashes); not merged, not installed. D5A2D2 WSL isolation focused run scored OVERALL FAIL and remains FAIL historically. D5A2D3 recovered helper journals (A/D); overall FAIL on original E. D5A2D4 Leader Accepted REVISE TEST (E1/E2). D5A2D5 Leader Accepted revised WSL isolation safety gate (A/B/C/D/E1/E2/F/G/H). D5A2D6 Leader Accepted READY_FOR_SOURCE_INTEGRATION_REVIEW (not merge approval). D5A2D7-P1 CLOSED — Leader Accepted (`e2160e7` on review branch only); main has no offbox source; PR/merge not authorized. GOV-0E CLOSED — Leader Accepted for Project LangstudyGuard (setup/docs only). ChatGPT is System Leader plus Active App Lead → Cursor; Product Owner leads Web/AI day-to-day. No accepted production unit set. The VPS has the 18B.9D5A1 user and the empty 18B.9D5A2A directory. 18B.9D5A2B1 is not accepted. No production backup was activated. Google Drive remains NOT CONFIGURED. Import branch `98b590e` remains unmerged.
Documentation checkpoint policy is IN FORCE, 2026-11-16. Documentation-only updates under ``.ai/`` may be committed and pushed to ``origin/main`` without a separate approval. Source commits, deploys, and production actions remain separately gated. A documentation commit is not a source commit and not a deployment.
B2 is not assumed to be append-only. Object Lock and a deleting lifecycle stay off. A 26-hour RPO and a 4-hour RTO remain proposals.
Windows Startup ``--lock`` hotfix remains DEFERRED until the affected computer is available. It is not diagnosed. Website W1 is handled by Antigravity in a separate workspace.
Committed at ``3dff28d3f78a22da0fda73a50168ed9c3d6e9d57``: Windows installation safety ([ADR-023](decisions/ADR-023-windows-installation-safety.md)). Startup ``--lock`` and Emergency Exit under ``--lock`` remain unverified. This is not a release.
**18C.1 CLOSED — Architect Accepted.** **18C.2 is next.** **18B.9 off-box is PAUSED, NOT CLOSED.** Cloud Sync **OFF**. GUI integration **not complete**.
Then (directional): 18C.2 signed-in GUI sync; resume 18B.9 when Owner re-prioritizes; AI Local Reading/Listening; optional Listening history/SRS; dictionary/pronunciation enrichment; Reading Lab
```

Listening is optional (settings default **off**). Content is AI-generated from StudyGuard-selected targets (max 2) with validated cache + bundled fallback; question/answer/transcript are study language; meaning is native; word lookup on demand. Audio remains Windows local TTS only.

**Phase 17C production acceptance (2026-10-26, SHA `c0b2d2d`):** live VPS `/api/listening` deployed and verified (authenticated 200 + negative cases); Windows TTS verified; UI hotfix for missing theme color shipped; frozen Windows `.exe` Listening flow operator-QA passed. No Listening attempt/SRS/mastery persistence. No cloud TTS, STT, or pronunciation scoring.

**Phase 18A CLOSED (accepted `94f1bf7`):** isolated `app/sync_store.py` + `study_sync.db` vocabulary entity store (revision, tombstone, operation_id + expected_revision idempotency, cursor pagination, strict payload allowlist, future-schema rejection before DDL). See [ADR-018](decisions/ADR-018-account-cloud-sync.md).

**Phase 18B.1 CLOSED (accepted `599e473`):** POST `/api/sync/vocabulary/put`, `/delete`, and `/changes` on the existing account server. Sync remains **default-off** unless `STUDY_SYNC_ENABLED` is exactly `1`. Phase 18B.7 later placed this code on the server with the flag still unset. **No desktop sync client** exists. See [ADR-019](decisions/ADR-019-vocabulary-sync-http.md).

**Phase 18B.2 CLOSED (independently verified `5f4251a`):** online backup and restore for `study_sync.db` only (`study-sync-` prefix, integrity check before publish, no-clobber restore, no source delete). **Not scheduled.** Sync flag stays **OFF**. Phase 18B.7 later copied the scripts and left them unscheduled. **No desktop sync client.** `backup_accounts.py` stays accounts-only. See [ADR-020](decisions/ADR-020-sync-database-backup.md) and [SYNC_DB_OPERATIONS.md](procedures/SYNC_DB_OPERATIONS.md).

**Phase 18B.3 CLOSED (accepted `97f7b25`):** production-readiness plan only. It does not install a timer or set the sync flag. See [PHASE-18B.3-production-readiness.md](plans/PHASE-18B.3-production-readiness.md).

**Phase 18B.4 CLOSED (accepted `d277791`):** `language-guard-sync-backup.service` and `.timer` exist in the repository and in the VPS application tree at `/opt/language-guard/deploy/hetzner/`. That acceptance did not enable them. Phase 18B.8 later installed both unit files into `/etc/systemd/system` and left the timer disabled and inactive. Production sync-backup paging is not operational. Sync is not activated. See [ADR-021](decisions/ADR-021-sync-backup-alerts.md).

**Phase 18B.5 CLOSED (GitHub-verified `69307892f779e61de7b99563eb5c76ad4296cbcc`):** `app/sync_restore_verify.py` and `deploy/hetzner/verify_sync_backup.py` restore the newest `study-sync-*.db` into a new temporary directory, open it read-only, and require the supported schema version (originally 2; **18C.1 advances supported schema to 3** with additive progress tables). A missing backup is a skip only when the live path is absent. A directory, symlink, or other non-file there is a failure. The verification root is checked, including ancestor symlinks, before anything is created. Phase 18B.7 copied this source to the VPS. Phase 18B.8 later enabled `language-guard-sync-verify.timer`. Its first natural run recorded `SKIPPED`, which is not a successful restore. The verifier does not set `STUDY_SYNC_ENABLED`. See [SYNC_DB_OPERATIONS.md](procedures/SYNC_DB_OPERATIONS.md).

**Phase 18B.6 CLOSED (`39f3a0bbbc47dda2c213324a820d198d0f0c3501`):** a copied account-server tree, its own synthetic `accounts.db` and `study_sync.db`, and a pre-start guard. Local tests bind `127.0.0.1` on a port other than `8765` and mock AI routes. Before listen, the staging `.env` must exist and match the staging-only allowlist; the pre-materialization guard may still run while that file is absent. Proof status is a new non-overwriting file in the staging proof directory and must not replace a database, backup, or `.env`. On this Windows host, symlink tests in `tests/test_sync_staging_isolation.py` skipped because `os.symlink` is unavailable, including the POSIX proof-partial regression. This does not create `/opt/language-guard-staging` on the VPS, install `language-guard-staging.service`, or change production `.env`. See [SYNC_DB_OPERATIONS.md](procedures/SYNC_DB_OPERATIONS.md).

**Article-Matching Hotfix CLOSED (GitHub-verified `d0f2f004c85ce9f4265d33bd034ba18423f1e3a5`):** a Dutch legacy answer was evaluated with English articles from the active settings language. Explicit quiz `language_code` takes priority. Legacy `nl` / `en` keys remain when the caller does not pass a language. Canonical `word` entries and explicit `articles` / `elisions` remain supported. Exact-without-hint remains the mastery rule, and a new submit appends an attempt instead of rewriting older rows. Windows RC QA on this commit: pytest 487 passed, 7 skipped; smoke all checks passed. With settings language `en`, legacy `de fiets` accepts `fiets`, and `language_code=nl` accepts it for a canonical entry. The seven Linux tests stayed skipped (`os.symlink` unavailable; `systemd-analyze` unavailable) and are not passes. HTTP 413 / WinError 10053 was not reproduced in five earlier reruns and stays follow-up QA. This hotfix does not authorize a VPS deploy.

**Windows RC QA of `d0f2f00` is historical.** That unpublished local executable is no longer official `dist` or the installed application. Its frozen GUI was not completed in a disposable Windows environment. The replacement binary and its limits are in the Windows installation-safety paragraph above. Production Sync stays OFF.

**Phase 18B.7 CLOSED (Leader-accepted controlled dark deploy, 2026-11-03):** server source `d0f2f004c85ce9f4265d33bd034ba18423f1e3a5`, recorded against GitHub baseline `6b59331e124e18cf6f6f371b8b562a569b22a309`. Twelve approved server files were deployed with matching SHA-256 checksums. `language-guard.service` restarted successfully. Fresh login returned HTTP 200 and issued a session. One authenticated AI Grade request returned HTTP 200 with a functional response. Public health returned HTTP 200. The three Sync POSTs returned HTTP 404. `STUDY_SYNC_ENABLED` remains unset. `study_sync.db` remained absent. The accounts backup was verified, and database permissions were hardened. The existing accounts backup timer is unchanged. No sync timer was installed, and no rollback was required. `setup.sh` was not used. The seven Linux-specific tests (symlink cases and `systemd-analyze`) stay explicitly deferred and are not passes. This closure does not authorize Phase 18B.8.

**Phase 18B.8 CLOSED — Leader Accepted, 2026-11-10:** this closes monitoring infrastructure and does not activate vocabulary Cloud Sync. Production deployment and the natural runs passed. The user received the scheduled Telegram and email. Healthchecks accepted the 2026-11-10 heartbeat. Commit `f57bcc6` integrated the monitoring documentation and the one-line unit hotfix. This closure commit completes documentation synchronization. UptimeRobot external uptime monitor: UNVERIFIED / DEFERRED. It is not installed or verified, and Telegram, email, and Healthchecks do not replace immediate public-outage detection. The health socket and the 30-minute and 09:00 timers are enabled from commit `5f0c3c37b0852b5e434f1b46fb6251b91f419dca`. The notifier tree is `/opt/language-guard-notify`, root-owned. `guard` is not in `lg-notify-client`. Credential files stay root mode `0400` and were not printed. A manual check and report on 2026-11-09 recorded provider acceptance before the natural runs. The one-line hotfix is `ReadOnlyPaths=/opt/language-guard/venv -/opt/language-guard/app /opt/language-guard/deploy/hetzner -/var/backups/language-guard/study-sync`. Production SHA-256 is `168e6c48e3d19e6951d35d99a6087651d3b78f6f67d02a5af545211c56e7dcbc`. The previous unit is `02e45baf68836d66179669d1282dd4c54b063d75fe023d22bb66de95b83a0bf6`, saved at `/root/language-guard-sync-verify-rollback-20261109T151626Z`. `language-guard-sync-verify.timer` fired at `2026-11-10 07:00:00 UTC`. The service finished at `07:00:01 UTC` with `ExecMainStatus=0` and recorded `SKIPPED` at `2026-11-10T07:00:01Z`, mode `0640`, owner `lg-verify:lg-health`. That `SKIPPED` result is not a successful sync backup or restore. `language-guard-health-report.timer` fired at `2026-11-10 08:00:00 UTC` and finished at `08:00:07 UTC` with exit status 0. Telegram and email were `PROVIDER_ACCEPTED`, and the user received both. Healthchecks accepted the `2026-11-10` heartbeat. The report text was `OK — sync backup SKIPPED, no study_sync.db yet`. Account service, public health, accounts backup age, accounts integrity, disk, and the sync flag were `VERIFIED`. Sync database, sync backup, and sync verification were `SKIPPED`. The latest observed 30-minute check was `2026-11-10 11:30:20 UTC` and exited 0 with the same pattern. `language-guard-sync-backup.timer` is installed, disabled, and inactive. `language-guard.service` stayed PID `858409` with no restart. Cloud Sync stayed OFF. `study_sync.db` was not created. No accounts-backup traverse ACL was added. The unit hotfix is in commit `f57bcc6`.

**Accounts backup mode, Step A FULL PASS (`09556f9`):** production `backup_accounts.py` is SHA-256 `6a762f60a7786042bd68825fc34ee81ef5b1e1f5248d0c72a40035bcb0b67055` and the unit is SHA-256 `49c293d4e3f0b2fad8b8e2256007014a1a85be70d45d7c3c35683452d2d52c39` with effective `UMask=0077`. Step A recorded `accounts-20261109-031959.db`. The later natural run at `2026-11-10 03:27:12 UTC` wrote `accounts-20261110-032712.db`, a regular `0600` `guard:guard` file of 20480 bytes. Retention stayed at 14, all mode `0600`. The directory stayed `0700`. The 2026-11-05 `0644` finding is historical and was corrected before monitoring installation. `setup.sh` was not used.

**Windows installation safety, not closed ([ADR-023](decisions/ADR-023-windows-installation-safety.md)):** the patch is committed at `3dff28d3f78a22da0fda73a50168ed9c3d6e9d57`. `tests/test_install.py` passed 15 tests on 2026-11-08. The isolated build, official `dist\langstudyguard.exe`, the single ZIP entry `langstudyguard.exe`, and `%LOCALAPPDATA%\langstudyguard\langstudyguard.exe` share SHA-256 `bbcd5e9a8bb22c72acdf863c94b68f6dbb7cc76717b737c6b93b0e50b28d58c3`. The ZIP file itself is SHA-256 `260089de6ff4eab071dbc70c904dd09ba6b9ca3091bcccaaa55a83bd859274f8`. The user confirmed Home Dashboard open and a normal close. That launch did not create Startup. A new user Startup shortcut then set the target to the installed executable, arguments `--lock`, and the install directory as the working directory. Automatic Startup and Emergency Exit under `--lock` have not been run on this build. Previous dist and install backups remain outside the repository. This is not a GitHub Release.

**ADR-022 Accepted** (`d9d0fe3`): event-first progress sync and automatic account sync while the Windows app is running. **18C.1 implements the local vertical slice in source** (schema v3 `learning_attempts` / `user_progress` / `progress_changes`; progress HTTP behind the default-off flag; per-account client store + background engine). Production activation is still separately gated. Local study stays authoritative offline. Server-order folding and `received_at`-anchored `ladder-v2` SRS are locked. Confirmed and provisional projections stay separate. Synced requires both outboxes clear, both cursors caught up, and no unresolved blocking conflict. Signed-in vocabulary is per-account; machine-global guest `vocab.json` must not automatically appear in or upload to an account. Legacy JSONL import / consent ledger from ADR-022 remains deferred beyond 18C.1. See [ADR-022](decisions/ADR-022-event-first-automatic-account-sync.md).

**Known deferred (not reopening 17C):** Dutch `nl-NL` voice may be missing on a given Windows machine (OS install). ScreenGuard still splits `pause_enforcement` from rare `release_display`. Progress Dashboard unchanged. AI enrichment remains advisory (draft → Apply). The oversized-body HTTP 413 WinError 10053 abort was not reproduced on 2026-11-02; the handler is unchanged. Linux symlink and `systemd-analyze` coverage is still outstanding on this Windows host.
