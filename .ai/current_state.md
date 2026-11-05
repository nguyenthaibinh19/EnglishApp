# Current state

> First file a new agent should read. Keep this concise and update when phases complete.

**Snapshot date context:** 2026-11-03 — Phase 18B.7 is **CLOSED**: the controlled dark deploy is Leader-accepted. Phase 18B.8 repository code, unit templates, and [HEALTH_MONITORING.md](procedures/HEALTH_MONITORING.md) exist and are **not deployed, not installed, and not closed**. Production installation is not authorized. Windows release-candidate QA is **PAUSED**, unpublished, and is not an active release milestone. The Article-Matching Hotfix is **CLOSED** and GitHub-verified at `d0f2f004c85ce9f4265d33bd034ba18423f1e3a5`. Phase 18B.6 is **CLOSED** at `39f3a0bbbc47dda2c213324a820d198d0f0c3501`. Phase 18B.5 is **CLOSED** and GitHub-verified at `69307892f779e61de7b99563eb5c76ad4296cbcc`. Phase 18B.4 remains **CLOSED** at `d277791`. ADR-022 remains **Accepted** as architecture only (`d9d0fe3`) and is not implemented. Phase 18C is not started. Sync flag stays **OFF**. No production paging, sync timer, Sync activation, or Windows sync client.

**Local implementation HEAD:** `cc3fd0fc9fd16dc6e39d48bbcd7928bcee4e0628` (this worktree; Phase 18B.8 is uncommitted)

**GitHub `main` last verified by Leader:** `604031446d0a832edfc3d6cdead6c84b87cc276a`

**Deployed server source:** `d0f2f004c85ce9f4265d33bd034ba18423f1e3a5`

**ADR-022 accepted commit:** `d9d0fe3` (event-first account sync architecture only; not implemented)

**Phase 18B.5 accepted commit:** `69307892f779e61de7b99563eb5c76ad4296cbcc` (restore verification; source copied in 18B.7; no production verification job installed or scheduled)

**Phase 18B.6 accepted commit:** `39f3a0bbbc47dda2c213324a820d198d0f0c3501` (isolated local staging; CLOSED; staging unit not installed)

**Article-Matching Hotfix accepted commit:** `d0f2f004c85ce9f4265d33bd034ba18423f1e3a5` (CLOSED; GitHub-verified; not a Windows release)

**Phase 18B.7 accepted deploy:** `d0f2f004c85ce9f4265d33bd034ba18423f1e3a5` (CLOSED; controlled dark deploy; Sync remains OFF; sync timer not installed)

**Phase 18B.4 accepted commit:** `d277791` (sync backup timer templates in the repository and `/opt/language-guard/deploy/hetzner/`; not installed into systemd, enabled, or started; ADR-021 Accepted)

**Phase 18B.3 accepted commit:** `97f7b25` (production-readiness plan; no timer, no deploy)

**Phase 18B.2 accepted commit:** `5f4251a` (sync backup and restore; ADR-020 Accepted; not scheduled)

**Phase 18B.1 accepted commit:** `599e473` (vocabulary sync HTTP; ADR-019 Accepted)

**Phase 18A accepted commit:** `94f1bf7` (vocabulary sync store; ADR-018 Accepted)

**Accepted Vocabulary Manager hotfix:** `ed51a92` (canonical `meaning` + Listbox `exportselection=False`)

**Phase 17C accepted commit:** `c0b2d2d375d1b258a5c14fec5f713065875ee0fa`

**Windows Startup:** deferred pending access to the affected PC (unchanged).

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

**Test notes (do not treat as a permanent green invariant):** a pre-17C-deploy snapshot once reported ~340 pytest passes. On 2026-11-02, at `d0f2f004c85ce9f4265d33bd034ba18423f1e3a5`, full `python -m pytest` was 487 passed, 7 skipped, and smoke passed every check. The seven skips are the Linux symlink tests and `systemd-analyze`; they were not run as passes. Windows RC packaging is local and unpublished. Do not claim a later tree is green without fresh evidence.

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
Completed: Phase 18B.4 — Sync backup timer units and alert contract (accepted ``d277791``; templates in the repository and ``/opt/language-guard/deploy/hetzner/``; not installed into systemd, enabled, or started; no production paging; sync flag OFF)
Completed: Phase 18B.5 — Restore verification (GitHub-verified ``69307892f779e61de7b99563eb5c76ad4296cbcc``; source copied in 18B.7; no production verification job installed or scheduled)
Completed: Phase 18B.6 — Isolated local staging (CLOSED ``39f3a0bbbc47dda2c213324a820d198d0f0c3501``; repository-only; staging unit not installed)
Completed: Phase 18B.7 — Controlled dark deploy (CLOSED; server source ``d0f2f004c85ce9f4265d33bd034ba18423f1e3a5``; Sync OFF; no sync timer)
Next: Phase 18B.8 repository implementation is present and uncommitted. It is not installed, not closed, and does not authorize a timer, a VPS change, or Sync activation. Windows RC QA remains PAUSED and unpublished.
Accepted, not started: ADR-022 event-first automatic account sync (architecture only, `d9d0fe3`). No schema, HTTP, or Windows client. Phase 18C is not started.
Then (directional, after sync readiness): AI Local Reading/Listening; optional Listening history/SRS; dictionary/pronunciation enrichment; Reading Lab
```

Listening is optional (settings default **off**). Content is AI-generated from StudyGuard-selected targets (max 2) with validated cache + bundled fallback; question/answer/transcript are study language; meaning is native; word lookup on demand. Audio remains Windows local TTS only.

**Phase 17C production acceptance (2026-10-26, SHA `c0b2d2d`):** live VPS `/api/listening` deployed and verified (authenticated 200 + negative cases); Windows TTS verified; UI hotfix for missing theme color shipped; frozen Windows `.exe` Listening flow operator-QA passed. No Listening attempt/SRS/mastery persistence. No cloud TTS, STT, or pronunciation scoring.

**Phase 18A CLOSED (accepted `94f1bf7`):** isolated `app/sync_store.py` + `study_sync.db` vocabulary entity store (revision, tombstone, operation_id + expected_revision idempotency, cursor pagination, strict payload allowlist, future-schema rejection before DDL). See [ADR-018](decisions/ADR-018-account-cloud-sync.md).

**Phase 18B.1 CLOSED (accepted `599e473`):** POST `/api/sync/vocabulary/put`, `/delete`, and `/changes` on the existing account server. Sync remains **default-off** unless `STUDY_SYNC_ENABLED` is exactly `1`. Phase 18B.7 later placed this code on the server with the flag still unset. **No desktop sync client** exists. See [ADR-019](decisions/ADR-019-vocabulary-sync-http.md).

**Phase 18B.2 CLOSED (independently verified `5f4251a`):** online backup and restore for `study_sync.db` only (`study-sync-` prefix, integrity check before publish, no-clobber restore, no source delete). **Not scheduled.** Sync flag stays **OFF**. Phase 18B.7 later copied the scripts and left them unscheduled. **No desktop sync client.** `backup_accounts.py` stays accounts-only. See [ADR-020](decisions/ADR-020-sync-database-backup.md) and [SYNC_DB_OPERATIONS.md](procedures/SYNC_DB_OPERATIONS.md).

**Phase 18B.3 CLOSED (accepted `97f7b25`):** production-readiness plan only. It does not install a timer or set the sync flag. See [PHASE-18B.3-production-readiness.md](plans/PHASE-18B.3-production-readiness.md).

**Phase 18B.4 CLOSED (accepted `d277791`):** `language-guard-sync-backup.service` and `.timer` exist in the repository and in the VPS application tree at `/opt/language-guard/deploy/hetzner/`. They have not been installed into `/etc/systemd/system`, enabled, or started. Production paging is not operational. Sync is not activated. See [ADR-021](decisions/ADR-021-sync-backup-alerts.md).

**Phase 18B.5 CLOSED (GitHub-verified `69307892f779e61de7b99563eb5c76ad4296cbcc`):** `app/sync_restore_verify.py` and `deploy/hetzner/verify_sync_backup.py` restore the newest `study-sync-*.db` into a new temporary directory, open it read-only, and require schema version 2. A missing backup is a skip only when the live path is absent. A directory, symlink, or other non-file there is a failure. The verification root is checked, including ancestor symlinks, before anything is created. Phase 18B.7 copied this source to the VPS. No production verification job is installed or scheduled. The verifier does not set `STUDY_SYNC_ENABLED`. See [SYNC_DB_OPERATIONS.md](procedures/SYNC_DB_OPERATIONS.md).

**Phase 18B.6 CLOSED (`39f3a0bbbc47dda2c213324a820d198d0f0c3501`):** a copied account-server tree, its own synthetic `accounts.db` and `study_sync.db`, and a pre-start guard. Local tests bind `127.0.0.1` on a port other than `8765` and mock AI routes. Before listen, the staging `.env` must exist and match the staging-only allowlist; the pre-materialization guard may still run while that file is absent. Proof status is a new non-overwriting file in the staging proof directory and must not replace a database, backup, or `.env`. On this Windows host, symlink tests in `tests/test_sync_staging_isolation.py` skipped because `os.symlink` is unavailable, including the POSIX proof-partial regression. This does not create `/opt/language-guard-staging` on the VPS, install `language-guard-staging.service`, or change production `.env`. See [SYNC_DB_OPERATIONS.md](procedures/SYNC_DB_OPERATIONS.md).

**Article-Matching Hotfix CLOSED (GitHub-verified `d0f2f004c85ce9f4265d33bd034ba18423f1e3a5`):** a Dutch legacy answer was evaluated with English articles from the active settings language. Explicit quiz `language_code` takes priority. Legacy `nl` / `en` keys remain when the caller does not pass a language. Canonical `word` entries and explicit `articles` / `elisions` remain supported. Exact-without-hint remains the mastery rule, and a new submit appends an attempt instead of rewriting older rows. Windows RC QA on this commit: pytest 487 passed, 7 skipped; smoke all checks passed. With settings language `en`, legacy `de fiets` accepts `fiets`, and `language_code=nl` accepts it for a canonical entry. The seven Linux tests stayed skipped (`os.symlink` unavailable; `systemd-analyze` unavailable) and are not passes. HTTP 413 / WinError 10053 was not reproduced in five earlier reruns and stays follow-up QA. This hotfix does not authorize a VPS deploy.

**Windows RC QA PAUSED** (not a release, not published, not the active milestone): a local `dist/langstudyguard.exe` and zip were built from `d0f2f00` with PyInstaller 6.22.3. The bundle contains a dedicated QA emergency password only. It does not contain the developer `.env` API key, account token, or account-server URL. Isolated `--check` exited 0: `install.prepare()` is skipped, the report was written under a disposable AppData directory, no isolated install copy or Startup shortcut was created, and the API key was absent. The primary installed exe, Startup shortcut, `progress.json`, and `settings.json` hashes were unchanged. Python 3.13.13, the build interpreter, also reported pytest 487 passed, 7 skipped, and smoke all checks passed. Frozen GUI QA remains blocked: Windows Sandbox is not installed, no Hyper-V VM is available, and the extra local accounts were not used. Production Sync stays OFF.

**Phase 18B.7 CLOSED (Leader-accepted controlled dark deploy, 2026-11-03):** server source `d0f2f004c85ce9f4265d33bd034ba18423f1e3a5`, recorded against GitHub baseline `6b59331e124e18cf6f6f371b8b562a569b22a309`. Twelve approved server files were deployed with matching SHA-256 checksums. `language-guard.service` restarted successfully. Fresh login returned HTTP 200 and issued a session. One authenticated AI Grade request returned HTTP 200 with a functional response. Public health returned HTTP 200. The three Sync POSTs returned HTTP 404. `STUDY_SYNC_ENABLED` remains unset. `study_sync.db` remained absent. The accounts backup was verified, and database permissions were hardened. The existing accounts backup timer is unchanged. No sync timer was installed, and no rollback was required. `setup.sh` was not used. The seven Linux-specific tests (symlink cases and `systemd-analyze`) stay explicitly deferred and are not passes. This closure does not authorize Phase 18B.8.

**Phase 18B.8 repository implementation, not closed and not deployed:** `app/health_monitor.py`, `app/health_notify.py`, `deploy/hetzner/health_report.py`, health-check, health-report, and sync-verify unit templates. Checks are every 30 minutes and the daily report is 09:00 Europe/Amsterdam, both as calendar suffixes. The sync backup template is `04:45:00 UTC`. Accounts backup code and its timer are unchanged. `setup.sh` copies the new templates into the app tree and does not enable them. `STUDY_SYNC_ENABLED` stays unset. The collector stays `guard` and does not load provider credentials. The notifier is a separate `lg-notify` template. The collector does not create `study_sync.db`. A restore verification is `UNKNOWN` until the verifier writes `result.json`; a recorded `VERIFIED` matches the current backup identity only. Health-channel backup alerts wait for the next 30-minute check. A 30-minute poll can miss a database created and deleted between checks. Provider acceptance is not proof a person received the message. See [HEALTH_MONITORING.md](procedures/HEALTH_MONITORING.md). No timer is installed and Sync is not activated.

**ADR-022 Accepted** (architecture only; not implemented; `d9d0fe3`): event-first progress sync and automatic account sync while the Windows app is running. Local study stays authoritative offline. Server-order folding and `received_at`-anchored `ladder-v2` SRS are locked, including a late offline wrong answer resetting streak. Confirmed and provisional projections stay separate. Import identity is file identity plus byte offset. A replacement file requires overlap preflight and explicit reconciliation before an ambiguous line can upload; accepted events are not deleted or silently duplicated. Synced requires both vocabulary and progress outboxes clear, both download cursors caught up, and no unresolved blocking conflict. Future signed-in vocabulary is per-account; machine-global guest `vocab.json` must not automatically appear in or upload to an account. No tables, routes, or client are authorized. Milestones 18C.1–18C.3 are not started. See [ADR-022](decisions/ADR-022-event-first-automatic-account-sync.md).

**Known deferred (not reopening 17C):** Dutch `nl-NL` voice may be missing on a given Windows machine (OS install). ScreenGuard still splits `pause_enforcement` from rare `release_display`. Progress Dashboard unchanged. AI enrichment remains advisory (draft → Apply). The oversized-body HTTP 413 WinError 10053 abort was not reproduced on 2026-11-02; the handler is unchanged. Linux symlink and `systemd-analyze` coverage is still outstanding on this Windows host.
