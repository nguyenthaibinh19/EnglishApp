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

## Practice records

- Append-only recognition and assisted vocabulary events in a separate `practice_records.db`. ADR-026 is Accepted. See [ADR-026](decisions/ADR-026-practice-records.md).
- Not a `LearningAttempt`, not an SRS review, and not a Cloud Sync progress event.
- Guest and account files stay separate. The file is not `account_study.db`.
- Observable error classes are `near_match` and `incorrect_answer`. Practice older than the latest independent attempt does not override that attempt.
- Phase 19.4C opens the correct practice file from the live StudyBundle identity for unlocked development sessions only. Frozen installs do not write practice rows from Home.

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
ListeningSession → WindowsSpeechProvider
                   System.Speech preferred
                   WinRT only for the same language
```

- StudyGuard chooses up to 2 target words; AI only writes content ([ADR-017](decisions/ADR-017-listening-content-generation.md)).
- Question/answer/transcript = study language; meaning = native; lookup on demand.
- Answer must be grounded in transcript. Cache + bundled sample fallback. No Listening attempt/SRS/mastery writes.
- StudyMaster must **not** discover Windows voices during construction. TTS discovery runs only when Listening is enabled and the learner opens Listening, via `ui_common.run_async` (off the Tk thread). Provider/catalog is cached for the StudyMaster lifetime. Async discovery completion auto-opens Listening only when still safe (no other study child open; pending language still active); otherwise the cache remains for a later explicit click. Listening callbacks bind the window's language explicitly (not mutable `active_code()`).
- No Progress / SRS / AttemptHistory writes from Listening.
- Playback goes through one shared slot in `speech_player`. Listening, Voice Settings, Vocabulary Library, Word Detail, and Study Feedback use that slot. A saved voice is device-local and is not an account preference. Discovery and synthesis stay off the Tk thread. A missing same-language voice uses the unavailable path. There is no wrong-language voice and no cloud speech fallback.

## Sentence practice (development)

- Progressive sentence exercises are a **separate skill** from vocabulary recall. Phase 19.5A is merged unreleased source. Session-memory results only — no `LearningAttempt`, Progress, SRS, Mistake Book, PracticeRecord, or sync outbox writes.
- Content contract: versioned `SentenceExercise` / `GrammarRule` / `SentencePack` in `sentence_content.py`, including `family_id` for related scaffolding. Reviewed `accepted_answers` are content; AI drafts are not answer keys. Dutch A1 remains author-curated / pending expert validation.
- Ladder: word bank → fill blank → guided writing → independent writing (`sentence_practice.py`). Local grading for reviewed answers; simulated AIService adapter for unlisted open writing — provisional only. Progress = distinct achieved levels. Explicit easier-related recovery is available.
- Grammar Companion selects curated rules by evidenced error hints (`grammar_companion.py`). Uncertain cases stay guidance-only. No full Grammar Library browser yet.
- UI: unlocked `SentencePracticeApp` via StudyMaster **Sentence** and optional post-adaptive CTA under the same `LG_ADAPTIVE_STUDY` + isolated `LG_DATA_DIR` opt-in as Adaptive Study. Post-vocab sentence defers Reading/Listening until the sentence round ends; exit/account/language invalidate deferred transitions. See [PHASE-19.5A-sentence-practice.md](plans/PHASE-19.5A-sentence-practice.md).

## Adaptive Study integration (development)

- Requires `LG_ADAPTIVE_STUDY=1` and a validated isolated `LG_DATA_DIR`. Frozen installs stay classic.
- FreeHome **Start learning** keeps the required StudyMaster → locked `VocabQuizApp` route.
- FreeHome **Adaptive Study (dev)** and StudyMaster **Adaptive** open unlocked `AdaptiveVocabularyApp` only when opted in and ScreenGuard is not locking the learner.
- Due/new selection must equal `planned_vocab_count`; a smaller eligible set refuses Adaptive and leaves vocabulary unresolved.
- Practice persistence statuses: `ok` / `unavailable` / `disabled`. Unavailable is never reported as saved.
- Account generation + language bindings invalidate stale callbacks. See [PHASE-19.4C-adaptive-study-integration.md](plans/PHASE-19.4C-adaptive-study-integration.md).

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
- Phase 18B.4 (accepted commit `d277791`, [ADR-021](decisions/ADR-021-sync-backup-alerts.md) **Accepted**) adds repository timer units and the source alert contract. Phase 18B.8 later installed those units and left `language-guard-sync-backup.timer` disabled. Sync-backup paging is not operational. The sync flag stays unset.
- Phase 18B.5 is **CLOSED** (GitHub-verified `69307892f779e61de7b99563eb5c76ad4296cbcc`). `app/sync_restore_verify.py` checks the newest `study-sync-*.db` by restoring it with `restore_database` into a new directory under a verification root, then opening that copy read-only. It requires `PRAGMA integrity_check` = `ok` and schema version 2, and it does not call `sync_store.connect()`. A missing backup with an absent live path is a skip and creates no database. A directory, symlink, or other non-file at the live path is a failure. The verification root is canonicalized before any mkdir or chmod, including when an ancestor symlink would land in a protected directory. Backup names must be real ASCII timestamps. The newest failure does not select an older file. Phase 18B.8 later enabled the production verify timer. Its natural `SKIPPED` result is not a successful restore.
- Phase 18B.6 is **CLOSED** at `39f3a0bbbc47dda2c213324a820d198d0f0c3501`. It is an ancestor of `main` and is not a VPS deployment. Staging is a separate copied package with its own synthetic accounts, sync database, backup directory, verification root, and proof directory. A pre-start guard refuses a non-loopback bind, port `8765`, a path that resolves into `/opt/language-guard` or `/var/backups/language-guard`, overlapping account and sync paths, symlink aliases into those trees, and a provider key other than the staging fake. An existing staging `.env` must match the staging-only allowlist before the process listens; the pre-materialization guard may run while that file is absent. Proof output is a new non-overwriting file in the proof directory. On Windows, symlink tests skipped because `os.symlink` is unavailable, including the POSIX proof-partial regression. Follow-up QA: one oversized sync request returned 413 and then `ConnectionAbortedError` (WinError 10053); a rerun passed and the full suite did not reproduce it. Local tests do not deploy that tree to the VPS or install `language-guard-staging.service`. Phase 18B.7 later closed as a controlled dark deploy of different server source; this staging drill still does not authorize a staging host.
- Phase 18B.8 health monitoring source is committed at `24e600b` (merge `65b045a`). Production deployment and the 2026-11-10 natural runs passed. The sync-verify timer is enabled. Its `ReadOnlyPaths` line prefixes the absent app and sync-backup directories with `-`. The 07:00 UTC run recorded `SKIPPED`, which is not a successful restore. The 09:00 report was provider-accepted, and the user received both messages. The sync-backup timer is installed, disabled, and inactive. Accounts snapshot mode `0600` from `09556f9` is deployed. Neither change sets `STUDY_SYNC_ENABLED`. Phase 18B.8 is CLOSED — Leader Accepted, 2026-11-10. See [HEALTH_MONITORING.md](procedures/HEALTH_MONITORING.md).
- [ADR-022](decisions/ADR-022-event-first-automatic-account-sync.md) is **Accepted**; **18C.1** shipped the local vertical slice (schema v3 + progress HTTP default-off + per-account client). **18C.2** wires signed-in Tkinter study flows through `study_data.open_study_data()` to `AccountLocalStore`, adds preferences contract v1 (`/api/sync/preferences/*` in `sync_meta`, no schema bump), account day buckets/streak, conflict-resolution UI, and consent-gated guest vocabulary import (attempt-history ledger import still deferred). Production activation remains separately gated. Schema v3 stores immutable attempts and a `progress_changes` journal. The client keeps confirmed + provisional projections. Synced means both outboxes are clear, both download streams are caught up, and no blocking conflict is open. Guest `vocab.json` / `progress.json` / `attempts.jsonl` remain for guest mode only and must not auto-upload on login.
- Login and AI routes still call `account_store.login()` / `user_for_token()` with no directory argument. Sync uses that same `user_for_token()` so it sees the same `accounts.db`. `STUDY_SYNC_DIR` overrides only the sync file.
- `deploy/hetzner/setup.sh` must package the account-server import closure (`sync_http.py`, `sync_store.py`, `vocab_identity.py`, `vocabulary_model.py`, plus the existing AI/listening modules). Importing that package with the flag unset must not create `study_sync.db`. This phase does not run the script on the VPS.
- Not in 18B.1: desktop sync, VPS deploy, production flag, Progress/SRS merge, AttemptHistory sync, settings sync.
- Optimistic concurrency via `expected_revision`; conflicts do not mutate.
- Deletes are tombstones; no silent resurrection.
- `operation_id` retries are idempotent only when the mutation matches; mismatched reuse conflicts.
- Do not store auth tokens or API keys in sync payloads.

## Off-box backup (Phase 18B.9)

Phase 18B.9 is open. The preferred store is Google Drive and the fallback is an unprovisioned Backblaze B2 bucket. [ADR-024](decisions/ADR-024-offbox-age-drive.md) accepts a local age `.age` artifact and a Drive adapter through step 18B.9D5A2C. `VERIFIED` means the downloaded ciphertext SHA-256 matches. It does not mean the daily report, a restore drill, or a production schedule. The VPS has the `lg-backup` user and an empty backup directory, and it does not have the adapter, age, or an OAuth token. `app/offbox_poc.py` remains the closed Restic proof. The step ids D4C through D5A2C1 are defined in [PHASE-18B.9-offbox-status.md](plans/PHASE-18B.9-offbox-status.md). D5A2C1 is CLOSED — Leader Accepted, 2026-11-16, as a localhost milestone. It is not installed and it is not Phase 18B.9C2.

## Environment identity and isolation

Build channel, runtime environment, backend host, account identity, data directory, Cloud Sync status, and version/SHA are **independent** facts ([ADR-025](decisions/ADR-025-environment-identity-and-isolation.md)). A Git branch or EXE filename alone does not authorize production network writes. Staging uses `%APPDATA%\langstudyguard-staging\` and never adopts the production session token or production host. Non-production `LG_DATA_DIR` overrides that overlap production AppData/install paths are rejected. Account/sync HTTP never follows credentialed redirects. Identity is visible on the login/setup window and StudyMaster. Unknown/mismatched identity fails closed. Staging EXE: `build_staging_exe.bat` → `dist-staging/langstudyguard-staging.exe` (must not overwrite `dist/langstudyguard.exe`). **Staging backend/trial is not activated** — reserved for future Owner authorization; local tests use development/localhost.

## Windows installation and Startup

Frozen `prepare()` in `app/install.py` is the installation boundary ([ADR-023](decisions/ADR-023-windows-installation-safety.md)). A source run does nothing. Staging/development frozen builds skip production install/Startup ([ADR-025](decisions/ADR-025-environment-identity-and-isolation.md)).

```text
other frozen path + installed file already present → stop, no copy, no launch, no Startup
running path is the installed exe → seed missing samples only
destination and langstudyguard.lnk both absent → exclusive first install, then one --lock shortcut
staging/dev frozen → run in place; no production LOCALAPPDATA copy; no langstudyguard.lnk
```

- The production installed executable is `%LOCALAPPDATA%\langstudyguard\langstudyguard.exe`. Learner data is `%APPDATA%\langstudyguard`.
- First install is the only path that creates the Startup shortcut. Registration refuses an existing `langstudyguard.lnk` and does not delete `Dutch Guard.lnk` or unrelated shortcuts.
- A failed first install removes only the executable and link that the same attempt created.
- Process spawn is not application initialization.
- The updater can still replace the installed executable after the learner accepts an update inside the installed app. It does not recreate Startup. An external copy cannot use that path while an install exists.
- The decision is committed at `3dff28d3f78a22da0fda73a50168ed9c3d6e9d57`. Local binary status is in [current_state.md](current_state.md).

## Languages

Canonical `StudyLanguage` registry ([ADR-002](decisions/ADR-002-canonical-study-languages.md)). Study language ≠ UI/native language.
