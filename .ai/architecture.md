# Architecture

Durable subsystem boundaries. Exact code lives in `app/`; this document states ownership and contracts.

See also: [invariants.md](invariants.md), [decisions/](decisions/).

## Vocabulary

- **`VocabularyEntry` / VocabStore** own lexical information (`word`, `meaning`, alternatives, optional note/POS) plus optional enrichment (`examples`, `pronunciation.ipa`, controlled `forms`).
- **Stable UUID (`id` / `vocab_id`)** owns learning identity — see [ADR-009](decisions/ADR-009-stable-vocabulary-identity.md).
- Editable spelling/meaning must never own Progress / SRS / attempt identity.
- Lexical model: [ADR-010](decisions/ADR-010-vocabulary-model-v2.md); enrichment storage: [ADR-011](decisions/ADR-011-vocabulary-enrichment-model.md); review-before-apply: [ADR-012](decisions/ADR-012-enrichment-review-before-apply.md).
- Enrichment pipeline (domain, not Tkinter):

```text
VocabularyEntry → EnrichmentService → VocabularyEnrichmentProvider
    → EnrichmentDraft (ephemeral) → review/select → apply → VocabStore.update
```

- Drafts are never auto-persisted. Production AI enrichment uses `AccountServerVocabularyEnrichmentProvider` → `/api/enrich` (review-before-apply; [ADR-013](decisions/ADR-013-ai-vocabulary-enrichment.md)). Enrich UI appears when AI is configured.

## Progress

- Current **aggregate** learning state per vocab item (seen/correct/wrong/streak/last_seen + SRS fields).
- Does **not** replace complete historical event history.
- Keys: vocab UUID (progress v3); `legacy_index` supports word→id compatibility reads.

## SRS / Scheduler

| Concern | Owner | Role |
|---------|--------|------|
| Long-term due scheduling | `srs` + Progress fields `interval_days` / `due_at` | When a word is due for review |
| Candidate priority + in-session requeue | `VocabScheduler` / `scheduler` | Which item to ask next in a session |

Do not conflate “due now” with “requeued later in this session”. See [ADR-001](decisions/ADR-001-scheduler-separation.md), [ADR-006](decisions/ADR-006-srs-v2.md).

## AttemptHistory

- Historical answer events (JSONL, append-oriented).
- `vocab_id` is identity when available; `word` is a historical spelling snapshot.
- Feeds Mistake Book, analytics, future AI dataset work. See [ADR-004](decisions/ADR-004-learning-attempt-history.md).

## MistakeBook

- **Derived** state from AttemptHistory — not a separate persistent attention store.
- Current rule: latest non-mastered attempt → needs attention; latest mastered → cleared. See [ADR-005](decisions/ADR-005-mistake-book-semantics.md).

## DailyStudyPlanner

- Derives today’s workload semantics: NEW / DUE / FUTURE / NEEDS ATTENTION.
- Plans are **not** persisted.
- Must never present future-review fallback as “due”. See [ADR-007](decisions/ADR-007-daily-study-planner.md).

## Learning Progress Dashboard

```text
VocabStore + Progress + AttemptHistory + MistakeBook
        ↓
LearningProgressSnapshot (derived, not persisted)
        ↓
ProgressViewModel → ProgressApp
```

- Read-only analytics for one study language (counts, mastery-quality **attempts**, 7-day activity).
- Reuses DailyStudy / SRS / MistakeBook helpers — UI must not redefine them.
- Overview **Needs attention** = current actionable vocab only (orphans excluded from that count).
- See [ADR-014](decisions/ADR-014-learning-progress-dashboard.md).

## StudySession

- Logical activity state machine: Vocabulary required when planned count > 0; Reading optional when enabled; Listening optional when enabled (default off).
- Order when present: vocabulary → reading → listening.
- Does **not** own Tkinter locking/window enforcement. See [ADR-008](decisions/ADR-008-study-session.md).

## Listening

```text
VocabStore / Progress / MistakeBook
        ↓
listening_source (target select + cache + fallback)
        ↓
ai_teacher → AIService → AIProvider → OpenAIProvider
   (production desktop: POST /api/listening)
        ↓
validated ListeningItem
        ↓
ListeningSession → WindowsLocalTTSProvider
```

- StudyGuard chooses up to 2 target words; AI only writes content ([ADR-017](decisions/ADR-017-listening-content-generation.md)).
- Question/answer/transcript = study language; meaning = native; lookup on demand.
- Answer must be grounded in transcript. Cache + bundled sample fallback. No Listening attempt/SRS/mastery writes.
- StudyMaster must **not** discover Windows voices during construction. TTS discovery runs only when Listening is enabled and the learner opens Listening, via `ui_common.run_async` (off the Tk thread). Provider/catalog is cached for the StudyMaster lifetime. Async discovery completion auto-opens Listening only when still safe (no other study child open; pending language still active); otherwise the cache remains for a later explicit click. Listening callbacks bind the window's language explicitly (not mutable `active_code()`).
- No Progress / SRS / AttemptHistory writes from Listening.

## UI (Tkinter)

- Home Dashboard, Progress Dashboard, Vocabulary Library, Mistake Book, quiz/reading/listening adapters consume domain models / view-models.
- Must not independently reimplement SRS / Mistake / DailyStudy rules.
- ScreenGuard owns lock/fullscreen enforcement.
- Activity launch is transactional (`ui_common.launch_toplevel_app`): constructor failure destroys the partial Toplevel and must not leave a blank orphan or hidden root.
- StudyMaster keeps the parent root mapped during child activities; parent uses `pause_enforcement` (not fullscreen release) while a child ScreenGuard is active. Avoid withdraw/deiconify.
- `ScreenGuard.pause_enforcement` / `enforcement_paused` stop focus/topmost fighting without changing fullscreen/state/geometry. `release_display` is the rare heavy path (e.g. updater).
- Micro-popups that would still flash as `Toplevel` under lock (Reading word actions) may use an in-window overlay Frame and must **not** pause ScreenGuard enforcement.
- `reset_window` restores `state("normal")` on real page/root transitions only — not micro-navigation.
- Utility windows should use `transient(parent)` / `open_owned_popup` rather than appearing as independent app restarts.

## AI

```text
consumers → ai_teacher facade → AIService → AIProvider → OpenAIProvider
```

Capabilities: grade sentence, generate reading, enrich vocabulary (POS/forms/examples).

- OpenAI is one implementation, not the architecture ([ADR-003](decisions/ADR-003-ai-provider-boundary.md)).
- Production API key remains **server-side**.
- Vocabulary enrichment is advisory ([ADR-012](decisions/ADR-012-enrichment-review-before-apply.md), [ADR-013](decisions/ADR-013-ai-vocabulary-enrichment.md)).

## Account / server

- Desktop uses HTTP + account token (`Bearer` + body token).
- Authenticated AI endpoints: `/api/grade`, `/api/reading`, `/api/enrich`, `/api/listening`.
- Do not expose the account DB directly to the desktop client.
- Reading generation wire may still use field name `vi` for meaning — local vocab schema remains canonical `meaning`.

## Account Cloud Sync (Phase 18A store + Phase 18B.1 HTTP)

```text
account_server.py  (STUDY_SYNC_ENABLED must be exactly "1")
        ↓  Bearer session only — user_id from account_store.user_for_token()
sync_http.py
        ↓
app/sync_store.py  →  study_sync.db  (separate from accounts.db)
        ↓
vocabulary_entities + vocabulary_changes
(revision, tombstone, operation_id, change cursor)
```

- Local-first: desktop AppData remains the working store; cloud sync is not required to study.
- Phase 18A (accepted commit `94f1bf7`) implements **vocabulary entity persistence only** ([ADR-018](decisions/ADR-018-account-cloud-sync.md), status **Accepted**). It does not activate production sync.
- Phase 18B.1 (accepted commit `599e473`, [ADR-019](decisions/ADR-019-vocabulary-sync-http.md) **Accepted**) adds POST `/api/sync/vocabulary/put|delete|changes` behind a **default-off** server flag. Disabled requests do not open `study_sync.db`. Sync routes reject body-token fallback and client-supplied `user_id`.
- Phase 18B.2 (accepted commit `5f4251a`, [ADR-020](decisions/ADR-020-sync-database-backup.md) **Accepted**) adds a separate sync backup/restore path. It does not replace `backup_accounts.py` and is not on the daily timer. Phase 18B.3 (accepted commit `97f7b25`) is the production-readiness plan.
- Phase 18B.4 (accepted commit `d277791`, [ADR-021](decisions/ADR-021-sync-backup-alerts.md) **Accepted**) adds repository timer units and the source alert contract. Those units are not installed. Production paging is not operational. The sync flag stays unset.
- Phase 18B.5 is **Leader-approved source, pending GitHub commit verification** (repository-only; not scheduled or installed). Phase 18B.6 is the next possible milestone and is not automatically authorized. `app/sync_restore_verify.py` checks the newest `study-sync-*.db` by restoring it with `restore_database` into a new directory under a verification root, then opening that copy read-only. It requires `PRAGMA integrity_check` = `ok` and schema version 2, and it does not call `sync_store.connect()`. A missing backup with an absent live path is a skip and creates no database. A directory, symlink, or other non-file at the live path is a failure. The verification root is canonicalized before any mkdir or chmod, including when an ancestor symlink would land in a protected directory. Backup names must be real ASCII timestamps. The newest failure does not select an older file. No timer is installed.
- [ADR-022](decisions/ADR-022-event-first-automatic-account-sync.md) is **Accepted — architecture only; not implemented** (`d9d0fe3`). It does not add tables, routes, or a client, and it does not authorize activation. Future schema v3 would store immutable attempts (including bounded answer, expected answer, and prompt) and a `progress_changes` journal. The client keeps a confirmed server projection and a provisional local projection. A validated page persists each new attempt once, applies only newer confirmed snapshots, skips older snapshots without regression, and treats an equal version with different content as a conflict. The download cursor advances only in the commit that applies the whole page. An upload acknowledgement may update confirmed and must not move that cursor past unseen changes. Merge is server accept order with `due_at` anchored to `received_at` (`ladder-v2`); a late wrong answer may reset streak. `attempts.jsonl` stays unchanged. Legacy import identity is OS file identity plus byte offset, with the line hash only for verification, after explicit per-account consent. A replacement file with a new identity still requires an overlap preflight; consent alone must not upload a line already imported, and accepted events are not deleted. Synced means both the vocabulary and progress outboxes are clear, both download streams are caught up, and no blocking conflict is open. Future signed-in vocabulary lives in that account's store. Machine-global guest `vocab.json` must not automatically appear in or upload to an account. Synced durability is one SQLite database per account, not an atomic write with `progress.json` or JSONL. Signed-in daily activity is in that account database. `progress.json` `days` is guest/legacy only and is not account-wide analytics.
- Login and AI routes still call `account_store.login()` / `user_for_token()` with no directory argument. Sync uses that same `user_for_token()` so it sees the same `accounts.db`. `STUDY_SYNC_DIR` overrides only the sync file.
- `deploy/hetzner/setup.sh` must package the account-server import closure (`sync_http.py`, `sync_store.py`, `vocab_identity.py`, `vocabulary_model.py`, plus the existing AI/listening modules). Importing that package with the flag unset must not create `study_sync.db`. This phase does not run the script on the VPS.
- Not in 18B.1: desktop sync, VPS deploy, production flag, Progress/SRS merge, AttemptHistory sync, settings sync.
- Optimistic concurrency via `expected_revision`; conflicts do not mutate.
- Deletes are tombstones; no silent resurrection.
- `operation_id` retries are idempotent only when the mutation matches; mismatched reuse conflicts.
- Do not store auth tokens or API keys in sync payloads.

## Languages

Canonical `StudyLanguage` registry ([ADR-002](decisions/ADR-002-canonical-study-languages.md)). Study language ≠ UI/native language.
