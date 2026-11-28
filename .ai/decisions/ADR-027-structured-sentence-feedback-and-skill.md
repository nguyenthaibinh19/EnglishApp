# ADR-027 Structured sentence feedback and sentence skill persistence

Status: **Proposed for review** on branch `phase19.5b/structured-feedback-sentence-skill`. Base main `e37fea87cedb38466d804e2294d3eb1b0a4136c7`. Not merged. Not a release. Not in the installed v1.5.0 download.

## Context

Phase 19.5A delivered progressive Dutch A1 sentence practice with session-memory results and a provisional simulated AI adapter. Phase 19.1 / 19.5B require structured, evidence-aware feedback and persistent local sentence-skill history without changing the deployed `GradeResult` / `/api/grade` wire or conflating sentence skill with vocabulary SRS.

## Decision

### Structured feedback (App-domain)

Introduce `StructuredSentenceFeedback` format version **1** in the App domain. It is validated at the trust boundary before UI or persistence use. It carries grading status, grading source and provenance, primary error class (including `unknown` / `unclassified`), original and corrected segments, corrected sentence, optional curated grammar rule id, learner-facing explanation, provisional flag, and certainty in `[0, 1]`.

Model certainty is never treated as linguistic proof. Score alone must never invent an error class. Malformed booleans or non-finite scores must not be silently coerced into acceptance.

`GradeResult` required fields and meaning stay unchanged. A future additive wire mapping (for example a nested `structured_feedback` object) is documented only; `C-APP-AI-001` v0.2.0 and the deployed `/api/grade` contract are not revised in this phase. Providers may optionally expose structured feedback via duck typing. An old provider is not required to implement a new abstract method. Unsupported structured capability degrades from `GradeResult`.

### Evidence precedence

1. Reviewed local correct and reliably diagnosed local incorrect evidence may influence selection.
2. Provisional AI acceptance/correction may be recorded but must not drive family/support selection.
3. Incomplete, empty, unlisted, ungraded, and unavailable grading are not learner failures for selection; unavailable may be recorded as metadata only.
4. At most one grammar skill reference is stored for an incorrect event.
5. Recency window for selection is 14 days; older rows stay stored but are ignored by the start policy.

### SentenceSkillRecord persistence

`SentenceSkillRecord` format version **1** is a separate append-only local record. It does not store raw learner sentences, raw AI responses, or corrected text. The file is `sentence_skill_records.db` under the captured guest language or account data root. It is not `practice_records.db` and not `account_study.db`.

Safety mirrors PracticeStore: explicit isolated data root, refuse production AppData / protected RC / recovery, idempotent submission insert, contradictory replay rejection, transactional writes, parsed UTC ordering, account/guest/language isolation, validated versions, invalid-row skip on read, honest storage failure feedback, correct connection lifecycle, no implicit guest-to-account import.

### Selection policy

Policy id `sentence-skill-family-support-v1` is conservative and deterministic. A recent reliable incorrect event prefers a related exercise family at a lower ladder kind (scaffolding). There is no numeric grammar mastery formula and no claim of statistically validated learning performance.

### Growth, retention, deletion

Growth is one small metadata row per recordable sentence submission. This phase does not delete rows automatically. Future account or guest deletion must remove the sentence-skill file with that data root. A future retention pass may drop old rows and must not rewrite the rows it keeps. Cloud sync of sentence skill events is not authorized here.

## Why

Sentence feedback can become actionable and reusable for scaffolding without pretending AI provisional notes are reviewed correctness, and without touching vocabulary progress or the deployed AI wire.

## Consequences

Easier: Grammar Companion can show segments and curated rules; a later session can open related scaffolding from saved evidence. Harder: a third local evidence file now exists beside AttemptHistory and practice records; future deletion and sync designs must know about it.

## Do not

Do not change deployed `/api/grade` or `GradeResult` required fields. Do not write sentence skill rows into `account_study.db` or `practice_records.db`. Do not sync SentenceSkillRecord yet. Do not invent grammar rules from untrusted model text. Do not let provisional AI drive selection. Do not write vocabulary LearningAttempt / Progress / SRS / PracticeRecord / outbox events from sentence practice.
