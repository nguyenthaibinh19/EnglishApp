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
| 17A | Listening Foundation (optional StudySession activity + audio-provider seam; no production TTS) |
| 17B | Windows Local TTS Provider v1 (System.Speech; per-language voice capability; lazy StudyMaster discovery) |
| 17C | AI-generated Listening content v1 (StudyGuard targets; study-language question; grounded answer; cache/fallback) |
| 18A | Account Cloud Sync Foundation (Leader-approved source; isolated `study_sync.db` vocabulary store; no production sync) |
| 18B.1 | Authenticated vocabulary sync HTTP (Leader-approved source; default-off; not deployed; no desktop client) |
| 18B.2 | Sync DB backup and restore (independently verified `5f4251a`; not scheduled; sync flag off; not deployed; no desktop client) |
| 18B.3 | Production-readiness plan (accepted `97f7b25`; planning only; no timer, no deploy, no desktop client) |
| 18B.4 | Sync backup timer and alert contract (accepted `d277791`; units not installed; no production paging; sync flag off) |
| 18B.5 | Restore verification (GitHub-verified `6930789`; repository-only; not scheduled or installed) |
| 18B.6 | Isolated local staging (CLOSED `39f3a0b`; repository-only; staging unit not installed) |

## Current

```text
Article-Matching Hotfix — Leader-approved source, pending GitHub commit verification
Not GitHub-verified yet. Root cause: a Dutch legacy answer used English articles from active settings
Explicit quiz language takes priority. Legacy nl/en keys, canonical word entries, and explicit articles/elisions remain supported
Diagnosis: settings language was en, so Dutch "de" was not stripped
QuizEngine.language_code is passed into match_answer; legacy nl/en keys remain the fallback
2026-11-02: full pytest 487 passed, 7 skipped; smoke all checks passed
HTTP 413 WinError 10053 did not reproduce (5 reruns); production HTTP unchanged
Phase 18B.6 remains CLOSED at `39f3a0b`
Phase 18B.5 remains CLOSED at `6930789`
Phase 18B.4 remains CLOSED at `d277791`
ADR-022 remains Accepted architecture only at `d9d0fe3`; no Progress Sync implementation
Sync flag stays OFF; no production paging, timer installation, VPS deployment, or Windows sync client
Phase 18B.7 is not authorized
Planning baseline: 39f3a0b
```

## Next

```text
Phase 18B.7 is the next possible milestone and is not authorized
Then major product priority after sync readiness: AI Local Reading / Listening
Optional later: Listening attempt history / analytics (not mastery / SRS)
Dictionary / pronunciation enrichment (review-before-apply)
Reading Lab improvements
```

Directional only — installing the sync timer, production activation, and the Windows client each need their own authorization. The Article-Matching Hotfix is Leader-approved source, pending GitHub commit verification. It does not start Phase 18B.7 and does not deploy a staging host.

## Near-term (directional)

- Phase 18B.5 restore verification is closed (GitHub-verified `6930789`; repository-only; not scheduled or installed)
- Phase 18B.6 isolated local staging is closed (`39f3a0b`; not a VPS deployment; staging unit not installed). Proof files are new names in the proof directory. The staging `.env` must match the allowlist before listen. Windows symlink tests skipped.
- Article-Matching Hotfix is Leader-approved source, pending GitHub commit verification (not GitHub-verified yet). A Dutch legacy answer was evaluated with English articles from active settings. Explicit quiz language takes priority. Legacy `nl`/`en` keys, canonical `word` entries, and explicit articles/elisions remain supported. On 2026-11-02 full pytest was 487 passed, 7 skipped, and smoke passed every check. The HTTP 413 WinError 10053 abort did not reproduce in five reruns and is follow-up QA only; production HTTP is unchanged.
- Phase 18B.7 is not authorized
- ADR-022 event-first automatic account sync (Accepted, architecture only at `d9d0fe3`; does not replace 18B.5 and does not authorize a client or 18C). Includes replacement overlap preflight and per-account vocabulary isolation. Implementation is not started.
- AI Local Reading / Listening (next major product priority after sync readiness)
- Dictionary / pronunciation enrichment
- Reading Lab improvements
- Optional Listening attempt history / analytics (not mastery)
- Optional future explicit cloud TTS provider behind the same seam (never silent fallback)

## Long-term (directional)

- StudyGuard AI / local model (`StudyGuardAIProvider` / `LocalModelProvider`)
- AI evaluation dataset from AttemptHistory
- Cloud sync transport + Progress/AttemptHistory merge (builds on 18A + stable vocab IDs)
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
- Listening history / SRS / mastery persistence (explicitly out of 17C scope)
- Cloud TTS, STT, or pronunciation scoring for Listening
- Dutch `nl-NL` Windows voice missing on some machines — OS voice install, not an app defect
- Legacy article-stripping matcher failure (`test_text_utils` / smoke) — separate technical debt; does not reopen 17C
- Production cloud sync activation / setting `STUDY_SYNC_ENABLED=1` on the VPS / automatic desktop upload (not 18B.1)
