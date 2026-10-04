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
ListeningItem → ListeningSession → ListeningAudioProvider.play(text, language)
        ↓
ListeningApp (Tk adapter) ← StudyMaster / StudySession
```

- Content: spoken `text` + comprehension `question` / `answer` (+ optional alternatives/meaning).
- Production resolve returns no provider yet; unavailable must not block finish after required work.
- No Progress / SRS / AttemptHistory writes in Phase 17A. See [ADR-015](decisions/ADR-015-listening-activity.md).

## UI (Tkinter)

- Home Dashboard, Progress Dashboard, Vocabulary Library, Mistake Book, quiz/reading/listening adapters consume domain models / view-models.
- Must not independently reimplement SRS / Mistake / DailyStudy rules.
- ScreenGuard owns lock/fullscreen enforcement.
- Activity launch is transactional (`ui_common.launch_toplevel_app`): constructor failure destroys the partial Toplevel and must not leave a blank orphan or hidden root.
- StudyMaster keeps the parent root mapped during child activities; parent uses `pause_enforcement` (not fullscreen release) while a child ScreenGuard is active. Avoid withdraw/deiconify.
- `ScreenGuard.pause_enforcement` / `enforcement_paused` stop focus/topmost fighting without changing fullscreen/state/geometry. `release_display` is the rare heavy path (e.g. updater).
- Micro-popups that would still flash as `Toplevel` under lock (Reading word actions) may use an in-window overlay Frame.
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
- Authenticated AI endpoints: `/api/grade`, `/api/reading`, `/api/enrich`.
- Do not expose the account DB directly to the desktop client.
- Reading generation wire may still use field name `vi` for meaning — local vocab schema remains canonical `meaning`.

## Languages

Canonical `StudyLanguage` registry ([ADR-002](decisions/ADR-002-canonical-study-languages.md)). Study language ≠ UI/native language.
