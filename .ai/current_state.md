# Current state

> First file a new agent should read. Keep this concise and update when phases complete.

**Snapshot date context:** 2026-10-29 — Phase 18B.4 is **CLOSED** at `d277791`. ADR-022 is **Accepted** as architecture only and is not implemented. Implementation milestones are not started. Sync flag stays **OFF**. Timer units are not installed. No production paging. Nothing deployed. No desktop sync client.

**Git baseline for this work:** `d2777913e7d175fea0ad26c629c5cf7f2c0feca8`

**Phase 18B.4 accepted commit:** `d277791` (sync backup timer units and source alert contract; not installed; ADR-021 Accepted)

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

**Test notes (do not treat as a permanent green invariant):** a pre-17C-deploy snapshot once reported ~340 pytest passes. Cursor later reported a pre-existing failure in `tests/test_text_utils.py::test_exact_and_article_stripped` (article-stripping matcher / matching smoke check). Do not claim current full-suite green without fresh evidence.

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
Completed: Phase 18B.1 — Authenticated vocabulary sync HTTP (accepted ``599e473``; default-off; not deployed; no desktop client; ADR-019 Accepted)
Completed: Phase 18B.2 — Sync DB backup and restore (independently verified ``5f4251a``; ADR-020 Accepted; backup not scheduled; sync flag OFF; not deployed; no desktop client)
Completed: Phase 18B.3 — Production-readiness plan (accepted ``97f7b25``; planning only; sync flag OFF; backup not scheduled; not deployed; no desktop client)
Completed: Phase 18B.4 — Sync backup timer units and alert contract (accepted ``d277791``; units not installed or enabled; no production paging; sync flag OFF; not deployed)
Next: Phase 18B.5 — repo-only restore verification. It is not automatically authorized.
Accepted, not started: ADR-022 event-first automatic account sync (architecture only). No schema, HTTP, or Windows client. Phase 18B.5 remains the next possible separately authorized milestone. The accepted design includes server-order SRS, replacement overlap preflight before any duplicate upload, and per-account vocabulary isolation.
Then (directional): AI Local Reading/Listening; optional Listening history/SRS; dictionary/pronunciation enrichment; Reading Lab
```

Listening is optional (settings default **off**). Content is AI-generated from StudyGuard-selected targets (max 2) with validated cache + bundled fallback; question/answer/transcript are study language; meaning is native; word lookup on demand. Audio remains Windows local TTS only.

**Phase 17C production acceptance (2026-10-26, SHA `c0b2d2d`):** live VPS `/api/listening` deployed and verified (authenticated 200 + negative cases); Windows TTS verified; UI hotfix for missing theme color shipped; frozen Windows `.exe` Listening flow operator-QA passed. No Listening attempt/SRS/mastery persistence. No cloud TTS, STT, or pronunciation scoring.

**Phase 18A CLOSED (accepted `94f1bf7`):** isolated `app/sync_store.py` + `study_sync.db` vocabulary entity store (revision, tombstone, operation_id + expected_revision idempotency, cursor pagination, strict payload allowlist, future-schema rejection before DDL). See [ADR-018](decisions/ADR-018-account-cloud-sync.md).

**Phase 18B.1 CLOSED (accepted `599e473`):** POST `/api/sync/vocabulary/put`, `/delete`, and `/changes` on the existing account server. Sync remains **default-off** unless `STUDY_SYNC_ENABLED` is exactly `1`. It is **not deployed**. **No desktop sync client** exists. See [ADR-019](decisions/ADR-019-vocabulary-sync-http.md).

**Phase 18B.2 CLOSED (independently verified `5f4251a`):** online backup and restore for `study_sync.db` only (`study-sync-` prefix, integrity check before publish, no-clobber restore, no source delete). **Not scheduled.** Sync flag stays **OFF**. **Nothing deployed.** **No desktop sync client.** `backup_accounts.py` stays accounts-only. See [ADR-020](decisions/ADR-020-sync-database-backup.md) and [SYNC_DB_OPERATIONS.md](procedures/SYNC_DB_OPERATIONS.md).

**Phase 18B.3 CLOSED (accepted `97f7b25`):** production-readiness plan only. It does not install a timer or set the sync flag. See [PHASE-18B.3-production-readiness.md](plans/PHASE-18B.3-production-readiness.md).

**Phase 18B.4 CLOSED (accepted `d277791`):** `language-guard-sync-backup.service` and `.timer` exist in the repository only. They are **not installed or enabled**. Production paging is not operational. Nothing is deployed. Sync is not activated. See [ADR-021](decisions/ADR-021-sync-backup-alerts.md).

**ADR-022 Accepted** (architecture only; not implemented): event-first progress sync and automatic account sync while the Windows app is running. Local study stays authoritative offline. Server-order folding and `received_at`-anchored `ladder-v2` SRS are locked, including a late offline wrong answer resetting streak. Confirmed and provisional projections stay separate. Import identity is file identity plus byte offset. A replacement file requires overlap preflight and explicit reconciliation before an ambiguous line can upload; accepted events are not deleted or silently duplicated. Synced requires both vocabulary and progress outboxes clear, both download cursors caught up, and no unresolved blocking conflict. Future signed-in vocabulary is per-account; machine-global guest `vocab.json` must not automatically appear in or upload to an account. No tables, routes, or client are authorized. Milestones 18C.1–18C.3 are not started. See [ADR-022](decisions/ADR-022-event-first-automatic-account-sync.md).

**Known deferred (not reopening 17C):** Dutch `nl-NL` voice may be missing on a given Windows machine (OS install); legacy article-stripping matcher failure is separate technical debt. ScreenGuard still splits `pause_enforcement` from rare `release_display`. Progress Dashboard unchanged. AI enrichment remains advisory (draft → Apply).
