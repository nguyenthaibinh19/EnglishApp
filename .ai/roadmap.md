# Roadmap

Directional plan — **not** a rigid release commitment. Update when phases complete or priorities shift.

## Completed

Architecture phases 1–14 (summary only):

| Phase | Theme |
|------:|--------|
| 1 | Scheduler separation from Progress |
| 2 | Canonical `StudyLanguage` registry |
| 3 | AI provider abstraction |
| 4 | pytest foundation (+ retained smoke test) |
| 5 | LearningAttempt history (JSONL) |
| 6 | Mistake Book (latest-attempt attention) |
| 7 | Practice Mistakes (`ReadOnlyVocabView`) |
| 8 | SRS v2 (`interval_days` / `due_at`) |
| 9 | DailyStudyPlanner |
| 10 | StudySession activity state machine |
| 11 | Home Dashboard (FreeHome) |
| 12 | Vocabulary Library + Word Detail |
| 13 | Stable vocabulary UUID identity |
| 14 | Vocabulary Model v2 (`meaning` / `alternatives` / …) |
| 14.5 | Project Memory Foundation (`.ai/`) |
| 15A | Vocabulary Enrichment Data Model (`examples` / IPA / forms storage) |
| 15B | Enrichment draft / review / apply foundation (no production providers) |
| 15C | Production AI vocabulary enrichment v1 (`/api/enrich`, review-before-apply) |
| 16 | Learning Progress Dashboard v1 (derived read-only analytics) |

## Current

```text
Phase 16 — Learning Progress Dashboard v1 — completed
```

## Next

```text
Dictionary / authoritative pronunciation providers; optional AI+dictionary orchestration
```

Progress Dashboard exposes calm, non-gamified counts and recent activity. AI coaching / CEFR / charts remain out of scope for this phase.

Likely next themes: WikDict/language-rule providers, pronunciation source for IPA — still review-before-apply; **not** a mandate to add CEFR/audio/TTS in one step.

## Near-term (directional)

- Dictionary / pronunciation enrichment
- Reading Lab improvements
- Listening (new activity — via StudySession, not ad-hoc `main.py` chains)

## Long-term (directional)

- StudyGuard AI / local model (`StudyGuardAIProvider` / `LocalModelProvider`)
- AI evaluation dataset from AttemptHistory
- Cloud sync (requires stable vocab IDs — already foundation)
- Production distribution / code signing
- Website evolution (`langstudyguard.com`)
- Commercial / payment layer
- Possible mobile / web clients

## Deferred / deliberate non-goals (for now)

- Premature FSRS state mixed into current Progress persistence
- Semantic duplicate headwords as a product feature (IDs allow it later; policy still blocks duplicate normalized adds)
- Embedding production OpenAI keys in the desktop app
- Treating chat history as project source of truth
- Bundling `.ai/` into the frozen executable as runtime data
