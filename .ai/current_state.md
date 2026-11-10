# Current state

> First file a new agent should read. Keep this concise and update when phases complete.

**Snapshot date:** 2026-11-10. Phase 18B.7 remains **CLOSED**. Phase 18B.8 production deployment is **PASS** and natural operational verification is **PASS**. The user confirmed the 09:00 Europe/Amsterdam Telegram and email. Documentation synchronization is **IN PROGRESS**. Phase closure is **PENDING LEADER REVIEW**. Cloud Sync stays **OFF**. The sync-verify timer is enabled and operational. The sync-backup timer is installed, disabled, and inactive. Windows Startup `--lock` is the next hotfix and is not yet diagnosed. Phase 18B.9 is not started.

**Installer patch:** committed at `3dff28d3f78a22da0fda73a50168ed9c3d6e9d57`. This documentation status update follows that commit and does not name its own SHA. Remote `main` is not claimed by this commit.

**Pre-integration baseline, read on 2026-11-08:** `09556f909b0ce6d8dcc27816800ef6bcd308f1ab`. That SHA is the parent of the installer commit. It is not the current HEAD of this documentation update.

**Deployed server source:** `d0f2f004c85ce9f4265d33bd034ba18423f1e3a5`. A newer Git commit is not a deploy.

**Phase 18B.8 source:** `24e600bacff67d134217deb931eb953721c9ea9b`, merge `65b045a62dc0f0e1f3e6f7d156ed22311e9bc705` (source committed; production install started 2026-11-09; not closed)

**Accounts backup mode source:** `09556f909b0ce6d8dcc27816800ef6bcd308f1ab` (deployed on the VPS; Step A FULL PASS; not the whole server tree)

**ADR-022 accepted commit:** `d9d0fe3` (event-first account sync architecture only; not implemented)

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
Step A FULL PASS: accounts backup safety deployed from ``09556f9``. Latest natural snapshot ``accounts-20261110-032712.db`` is mode ``0600``.
Phase 18B.8 operational PASS, closure pending: natural sync verification at 07:00 UTC recorded ``SKIPPED``. The natural 09:00 report was provider-accepted, and the user received both messages. Cloud Sync stays OFF.
Next, in this order: Leader review of this documentation, then a Windows Startup ``--lock`` hotfix, then Phase 18B.9 off-box recovery. Do not start 18B.9 first.
Committed at ``3dff28d3f78a22da0fda73a50168ed9c3d6e9d57``: Windows installation safety ([ADR-023](decisions/ADR-023-windows-installation-safety.md)). Startup ``--lock`` and Emergency Exit under ``--lock`` remain unverified. This is not a release.
Phase 18C is not started.
Accepted, not started: ADR-022 event-first automatic account sync (architecture only, `d9d0fe3`). No schema, HTTP, or Windows client. Phase 18C is not started.
Then (directional, after sync readiness): AI Local Reading/Listening; optional Listening history/SRS; dictionary/pronunciation enrichment; Reading Lab
```

Listening is optional (settings default **off**). Content is AI-generated from StudyGuard-selected targets (max 2) with validated cache + bundled fallback; question/answer/transcript are study language; meaning is native; word lookup on demand. Audio remains Windows local TTS only.

**Phase 17C production acceptance (2026-10-26, SHA `c0b2d2d`):** live VPS `/api/listening` deployed and verified (authenticated 200 + negative cases); Windows TTS verified; UI hotfix for missing theme color shipped; frozen Windows `.exe` Listening flow operator-QA passed. No Listening attempt/SRS/mastery persistence. No cloud TTS, STT, or pronunciation scoring.

**Phase 18A CLOSED (accepted `94f1bf7`):** isolated `app/sync_store.py` + `study_sync.db` vocabulary entity store (revision, tombstone, operation_id + expected_revision idempotency, cursor pagination, strict payload allowlist, future-schema rejection before DDL). See [ADR-018](decisions/ADR-018-account-cloud-sync.md).

**Phase 18B.1 CLOSED (accepted `599e473`):** POST `/api/sync/vocabulary/put`, `/delete`, and `/changes` on the existing account server. Sync remains **default-off** unless `STUDY_SYNC_ENABLED` is exactly `1`. Phase 18B.7 later placed this code on the server with the flag still unset. **No desktop sync client** exists. See [ADR-019](decisions/ADR-019-vocabulary-sync-http.md).

**Phase 18B.2 CLOSED (independently verified `5f4251a`):** online backup and restore for `study_sync.db` only (`study-sync-` prefix, integrity check before publish, no-clobber restore, no source delete). **Not scheduled.** Sync flag stays **OFF**. Phase 18B.7 later copied the scripts and left them unscheduled. **No desktop sync client.** `backup_accounts.py` stays accounts-only. See [ADR-020](decisions/ADR-020-sync-database-backup.md) and [SYNC_DB_OPERATIONS.md](procedures/SYNC_DB_OPERATIONS.md).

**Phase 18B.3 CLOSED (accepted `97f7b25`):** production-readiness plan only. It does not install a timer or set the sync flag. See [PHASE-18B.3-production-readiness.md](plans/PHASE-18B.3-production-readiness.md).

**Phase 18B.4 CLOSED (accepted `d277791`):** `language-guard-sync-backup.service` and `.timer` exist in the repository and in the VPS application tree at `/opt/language-guard/deploy/hetzner/`. That acceptance did not enable them. Phase 18B.8 later installed both unit files into `/etc/systemd/system` and left the timer disabled and inactive. Production sync-backup paging is not operational. Sync is not activated. See [ADR-021](decisions/ADR-021-sync-backup-alerts.md).

**Phase 18B.5 CLOSED (GitHub-verified `69307892f779e61de7b99563eb5c76ad4296cbcc`):** `app/sync_restore_verify.py` and `deploy/hetzner/verify_sync_backup.py` restore the newest `study-sync-*.db` into a new temporary directory, open it read-only, and require schema version 2. A missing backup is a skip only when the live path is absent. A directory, symlink, or other non-file there is a failure. The verification root is checked, including ancestor symlinks, before anything is created. Phase 18B.7 copied this source to the VPS. Phase 18B.8 later enabled `language-guard-sync-verify.timer`. Its first natural run recorded `SKIPPED`, which is not a successful restore. The verifier does not set `STUDY_SYNC_ENABLED`. See [SYNC_DB_OPERATIONS.md](procedures/SYNC_DB_OPERATIONS.md).

**Phase 18B.6 CLOSED (`39f3a0bbbc47dda2c213324a820d198d0f0c3501`):** a copied account-server tree, its own synthetic `accounts.db` and `study_sync.db`, and a pre-start guard. Local tests bind `127.0.0.1` on a port other than `8765` and mock AI routes. Before listen, the staging `.env` must exist and match the staging-only allowlist; the pre-materialization guard may still run while that file is absent. Proof status is a new non-overwriting file in the staging proof directory and must not replace a database, backup, or `.env`. On this Windows host, symlink tests in `tests/test_sync_staging_isolation.py` skipped because `os.symlink` is unavailable, including the POSIX proof-partial regression. This does not create `/opt/language-guard-staging` on the VPS, install `language-guard-staging.service`, or change production `.env`. See [SYNC_DB_OPERATIONS.md](procedures/SYNC_DB_OPERATIONS.md).

**Article-Matching Hotfix CLOSED (GitHub-verified `d0f2f004c85ce9f4265d33bd034ba18423f1e3a5`):** a Dutch legacy answer was evaluated with English articles from the active settings language. Explicit quiz `language_code` takes priority. Legacy `nl` / `en` keys remain when the caller does not pass a language. Canonical `word` entries and explicit `articles` / `elisions` remain supported. Exact-without-hint remains the mastery rule, and a new submit appends an attempt instead of rewriting older rows. Windows RC QA on this commit: pytest 487 passed, 7 skipped; smoke all checks passed. With settings language `en`, legacy `de fiets` accepts `fiets`, and `language_code=nl` accepts it for a canonical entry. The seven Linux tests stayed skipped (`os.symlink` unavailable; `systemd-analyze` unavailable) and are not passes. HTTP 413 / WinError 10053 was not reproduced in five earlier reruns and stays follow-up QA. This hotfix does not authorize a VPS deploy.

**Windows RC QA of `d0f2f00` is historical.** That unpublished local executable is no longer official `dist` or the installed application. Its frozen GUI was not completed in a disposable Windows environment. The replacement binary and its limits are in the Windows installation-safety paragraph above. Production Sync stays OFF.

**Phase 18B.7 CLOSED (Leader-accepted controlled dark deploy, 2026-11-03):** server source `d0f2f004c85ce9f4265d33bd034ba18423f1e3a5`, recorded against GitHub baseline `6b59331e124e18cf6f6f371b8b562a569b22a309`. Twelve approved server files were deployed with matching SHA-256 checksums. `language-guard.service` restarted successfully. Fresh login returned HTTP 200 and issued a session. One authenticated AI Grade request returned HTTP 200 with a functional response. Public health returned HTTP 200. The three Sync POSTs returned HTTP 404. `STUDY_SYNC_ENABLED` remains unset. `study_sync.db` remained absent. The accounts backup was verified, and database permissions were hardened. The existing accounts backup timer is unchanged. No sync timer was installed, and no rollback was required. `setup.sh` was not used. The seven Linux-specific tests (symlink cases and `systemd-analyze`) stay explicitly deferred and are not passes. This closure does not authorize Phase 18B.8.

**Phase 18B.8 operational PASS, closure pending Leader review (verified 2026-11-10):** production deployment passed and the natural runs passed. The user confirmed both scheduled notifications. Documentation synchronization is in progress, and this phase is not closed. The health socket and the 30-minute and 09:00 timers are enabled from commit `5f0c3c37b0852b5e434f1b46fb6251b91f419dca`. The notifier tree is `/opt/language-guard-notify`, root-owned. `guard` is not in `lg-notify-client`. Credential files stay root mode `0400` and were not printed. A manual check and report on 2026-11-09 recorded provider acceptance before the natural runs. The one-line hotfix is `ReadOnlyPaths=/opt/language-guard/venv -/opt/language-guard/app /opt/language-guard/deploy/hetzner -/var/backups/language-guard/study-sync`. Production SHA-256 is `168e6c48e3d19e6951d35d99a6087651d3b78f6f67d02a5af545211c56e7dcbc`. The previous unit is `02e45baf68836d66179669d1282dd4c54b063d75fe023d22bb66de95b83a0bf6`, saved at `/root/language-guard-sync-verify-rollback-20261109T151626Z`. `language-guard-sync-verify.timer` fired at `2026-11-10 07:00:00 UTC`. The service finished at `07:00:01 UTC` with `ExecMainStatus=0` and recorded `SKIPPED` at `2026-11-10T07:00:01Z`, mode `0640`, owner `lg-verify:lg-health`. That `SKIPPED` result is not a successful sync backup or restore. `language-guard-health-report.timer` fired at `2026-11-10 08:00:00 UTC` and finished at `08:00:07 UTC` with exit status 0. Telegram and email were `PROVIDER_ACCEPTED`, and the user received both. Healthchecks accepted the `2026-11-10` heartbeat. The report text was `OK — sync backup SKIPPED, no study_sync.db yet`. Account service, public health, accounts backup age, accounts integrity, disk, and the sync flag were `VERIFIED`. Sync database, sync backup, and sync verification were `SKIPPED`. The latest observed 30-minute check was `2026-11-10 11:30:20 UTC` and exited 0 with the same pattern. `language-guard-sync-backup.timer` is installed, disabled, and inactive. `language-guard.service` stayed PID `858409` with no restart. Cloud Sync stayed OFF. `study_sync.db` was not created. No accounts-backup traverse ACL was added. The repository unit edit is not committed.

**Accounts backup mode, Step A FULL PASS (`09556f9`):** production `backup_accounts.py` is SHA-256 `6a762f60a7786042bd68825fc34ee81ef5b1e1f5248d0c72a40035bcb0b67055` and the unit is SHA-256 `49c293d4e3f0b2fad8b8e2256007014a1a85be70d45d7c3c35683452d2d52c39` with effective `UMask=0077`. Step A recorded `accounts-20261109-031959.db`. The later natural run at `2026-11-10 03:27:12 UTC` wrote `accounts-20261110-032712.db`, a regular `0600` `guard:guard` file of 20480 bytes. Retention stayed at 14, all mode `0600`. The directory stayed `0700`. The 2026-11-05 `0644` finding is historical and was corrected before monitoring installation. `setup.sh` was not used.

**Windows installation safety, not closed ([ADR-023](decisions/ADR-023-windows-installation-safety.md)):** the patch is committed at `3dff28d3f78a22da0fda73a50168ed9c3d6e9d57`. `tests/test_install.py` passed 15 tests on 2026-11-08. The isolated build, official `dist\langstudyguard.exe`, the single ZIP entry `langstudyguard.exe`, and `%LOCALAPPDATA%\langstudyguard\langstudyguard.exe` share SHA-256 `bbcd5e9a8bb22c72acdf863c94b68f6dbb7cc76717b737c6b93b0e50b28d58c3`. The ZIP file itself is SHA-256 `260089de6ff4eab071dbc70c904dd09ba6b9ca3091bcccaaa55a83bd859274f8`. The user confirmed Home Dashboard open and a normal close. That launch did not create Startup. A new user Startup shortcut then set the target to the installed executable, arguments `--lock`, and the install directory as the working directory. Automatic Startup and Emergency Exit under `--lock` have not been run on this build. Previous dist and install backups remain outside the repository. This is not a GitHub Release.

**ADR-022 Accepted** (architecture only; not implemented; `d9d0fe3`): event-first progress sync and automatic account sync while the Windows app is running. Local study stays authoritative offline. Server-order folding and `received_at`-anchored `ladder-v2` SRS are locked, including a late offline wrong answer resetting streak. Confirmed and provisional projections stay separate. Import identity is file identity plus byte offset. A replacement file requires overlap preflight and explicit reconciliation before an ambiguous line can upload; accepted events are not deleted or silently duplicated. Synced requires both vocabulary and progress outboxes clear, both download cursors caught up, and no unresolved blocking conflict. Future signed-in vocabulary is per-account; machine-global guest `vocab.json` must not automatically appear in or upload to an account. No tables, routes, or client are authorized. Milestones 18C.1–18C.3 are not started. See [ADR-022](decisions/ADR-022-event-first-automatic-account-sync.md).

**Known deferred (not reopening 17C):** Dutch `nl-NL` voice may be missing on a given Windows machine (OS install). ScreenGuard still splits `pause_enforcement` from rare `release_display`. Progress Dashboard unchanged. AI enrichment remains advisory (draft → Apply). The oversized-body HTTP 413 WinError 10053 abort was not reproduced on 2026-11-02; the handler is unchanged. Linux symlink and `systemd-analyze` coverage is still outstanding on this Windows host.
