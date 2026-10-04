# Architecture

Durable subsystem boundaries. Exact code lives in `app/`; this document states ownership and contracts.

See also: [invariants.md](invariants.md), [decisions/](decisions/).

## Vocabulary

- **`VocabularyEntry` / VocabStore** own lexical information (`word`, `meaning`, alternatives, optional note/POS) plus optional enrichment (`examples`, `pronunciation.ipa`, controlled `forms`).
- **Stable UUID (`id` / `vocab_id`)** owns learning identity — see [ADR-009](decisions/ADR-009-stable-vocabulary-identity.md).
- Editable spelling/meaning must never own Progress / SRS / attempt identity.
- Lexical model: [ADR-010](decisions/ADR-010-vocabulary-model-v2.md); enrichment storage: [ADR-011](decisions/ADR-011-vocabulary-enrichment-model.md).
- Enrichment fields are optional storage; providers that fill them are a later phase.

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

## StudySession

- Logical activity state machine (Vocabulary required when planned count > 0; Reading optional when enabled).
- Does **not** own Tkinter locking/window enforcement. See [ADR-008](decisions/ADR-008-study-session.md).

## UI (Tkinter)

- Home Dashboard, Vocabulary Library, Mistake Book, quiz/reading adapters consume domain models / view-models.
- Must not independently reimplement SRS / Mistake / DailyStudy rules.
- ScreenGuard owns lock/fullscreen enforcement.

## AI

```text
consumers → ai_teacher facade → AIService → AIProvider → OpenAIProvider
```

- OpenAI is one implementation, not the architecture ([ADR-003](decisions/ADR-003-ai-provider-boundary.md)).
- Production API key remains **server-side**.

## Account / server

- Desktop uses HTTP + account token.
- Do not expose the account DB directly to the desktop client.
- Reading generation wire may still use field name `vi` for meaning — local vocab schema remains canonical `meaning`.

## Languages

Canonical `StudyLanguage` registry ([ADR-002](decisions/ADR-002-canonical-study-languages.md)). Study language ≠ UI/native language.
