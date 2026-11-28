# ADR-027 Structured sentence feedback and sentence skill persistence

Status: **Accepted.** Closeout on branch `phase19.5b/structured-feedback-sentence-skill`. Review checkpoint `b37afac6a7627e9f9d9191e59fe08fc9f6220a95`. Architect: `APP_19D5B_FOUNDATION_ACCEPTED_CLOSEOUT_CORRECTIONS_REQUIRED`. Merged, unreleased development functionality. Not in the installed v1.5.0 download.

## Context

Phase 19.5A delivered progressive Dutch A1 sentence practice with session-memory results and a provisional simulated AI adapter. Phase 19.1 / 19.5B require structured, evidence-aware feedback and persistent local sentence-skill history without changing the deployed `GradeResult` / `/api/grade` wire or conflating sentence skill with vocabulary SRS.

## Decision

### Structured feedback (App-domain)

Introduce `StructuredSentenceFeedback` format version **1** in the App domain. It is validated at the trust boundary before UI or persistence use. It carries grading status, grading source and provenance, primary error class (including `unknown` / `unclassified`), original and corrected segments, corrected sentence, optional curated grammar rule id, learner-facing explanation, provisional flag, and certainty in `[0, 1]`.

Validation rejects malformed field types (exact integer versions, real booleans, finite numeric ranges, bounded strings, supported enums). Source/status/provisional semantics are enforced: a model response cannot declare itself authoritative local evidence or reviewed correctness. Original segments must appear in the submitted answer; corrected segments must appear in the correction context. Grammar references must resolve to the current exercise allow-list. Malformed structured feedback never becomes authoritative acceptance.

Model certainty is never treated as linguistic proof. Score alone must never invent an error class.

`GradeResult` required fields and meaning stay unchanged. One GradeResult call per submission; optional structured feedback is compatibility-mapped against that result. Unsupported structured capability degrades from `GradeResult`. A future additive wire mapping is documented only; `C-APP-AI-001` v0.2.0 and the deployed `/api/grade` contract are not revised in this phase.

### Session plan and completion

Adaptive cross-session selection may start above Word Bank. The session plan is the set of ladder levels from the adaptive start through independent writing. Skipped lower levels are not claimed as demonstrated skill. Progress is achieved planned levels / plan size. Stepping down expands the plan. Completion requires the plan to be achieved in the current session — not all four ladder levels when the start was nonzero.

### Evidence precedence and selection

1. Reviewed local correct and reliably diagnosed local incorrect evidence may influence selection.
2. Provisional AI acceptance/correction may be recorded but must not drive family/support selection.
3. Incomplete, empty, unlisted, ungraded, and unavailable grading are not learner failures for selection.
4. At most one grammar skill reference is stored for an incorrect event, and only when diagnosis is certain and matched — never the first available rule for an unclassified failure.
5. A later assisted/reviewed success at an easier level does not clear harder-level difficulty. Resolution requires a later reviewed correct at the same or harder support rank with compatible family/skill evidence.
6. Recency window for selection is 14 days; future-dated rows are excluded. Policy id: `sentence-skill-family-support-v1`. No numeric mastery formula.

### SentenceSkillRecord persistence

`SentenceSkillRecord` format version **1** is a separate append-only local record. It does not store raw learner sentences, raw AI responses, or corrected text. The file is `sentence_skill_records.db` under the captured guest language or account data root. It is not `practice_records.db` and not `account_study.db`.

Safety mirrors PracticeStore: explicit isolated data root, refuse production AppData / protected RC / recovery, idempotent submission insert, contradictory replay rejection, transactional writes, parsed UTC ordering, account/guest/language isolation, validated versions, invalid-row skip on read, honest storage failure feedback, correct connection lifecycle, no implicit guest-to-account import.

Intentionally disabled persistence (no store) is distinct from unavailable storage. Init/history failure shows honest learner-facing feedback, closes any partial store, and continues practice without claiming history is saved. Owned SQLite resources close on completion, leave, account/language switch, constructor failure, and window destruction. Closed-store operations raise `SentenceSkillStoreError`.

### Growth, retention, deletion

Growth is one small metadata row per recordable sentence submission. This phase does not delete rows automatically. Future account or guest deletion must remove the sentence-skill file with that data root. A future retention pass may drop old rows and must not rewrite the rows it keeps. Cloud sync of sentence skill events is not authorized here.

## Why

Sentence feedback can become actionable and reusable for scaffolding without pretending AI provisional notes are reviewed correctness, and without touching vocabulary progress or the deployed AI wire.

## Consequences

Easier: Grammar Companion can show segments and curated rules; a later session can open related scaffolding from saved evidence; nonzero adaptive starts can finish. Harder: a third local evidence file now exists beside AttemptHistory and practice records; future deletion and sync designs must know about it.

## Do not

Do not change deployed `/api/grade` or `GradeResult` required fields. Do not write sentence skill rows into `account_study.db` or `practice_records.db`. Do not sync SentenceSkillRecord yet. Do not invent grammar rules from untrusted model text. Do not let provisional AI drive selection. Do not write vocabulary LearningAttempt / Progress / SRS / PracticeRecord / outbox events from sentence practice. Do not claim skipped adaptive levels as demonstrated skill.
