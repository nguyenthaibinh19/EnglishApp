# Phase 19.5B — Structured AI Feedback and Persistent Sentence Skill

**Status:** Ready for review (`APP_19D5B_STRUCTURED_FEEDBACK_SENTENCE_SKILL_READY_FOR_REVIEW`)  
**Branch:** `phase19.5b/structured-feedback-sentence-skill`  
**Base main:** `e37fea87cedb38466d804e2294d3eb1b0a4136c7`  
**Architect:** `APP_19D5A_ARCHITECT_ACCEPTED_CLOSED`  
**ADR:** [ADR-027](../decisions/ADR-027-structured-sentence-feedback-and-skill.md)

## Objective

Make sentence feedback structured, evidence-aware, and reusable for future personalized grammar practice — inside the existing integrated development application (not a standalone learning app).

## Delivered

### A. Structured feedback contract (App-domain)

- `app/sentence_feedback.py` — `StructuredSentenceFeedback` format version **1**
- Fields: format version, grading status, grading source/provenance, primary error class (incl. unknown/unclassified), original/corrected segments, corrected sentence, optional grammar rule id, learner-facing explanation, provisional + certainty
- Distinguishes reviewed local matches, reliably detected local errors, AI-provisional acceptance/corrections, and ungraded/unavailable
- **Does not change** `GradeResult` meaning or required fields
- Future `/api/grade` transport mapping documented only (`future_structured_feedback_transport_mapping`)

### B. Trust-boundary validation

- Schema/version, types, finite certainty in [0,1], supported error classes, bounded lengths
- Original segment must correspond to the submitted answer
- Grammar rule ids must be in the exercise/pack allow-list
- No silent boolean/score coercion; no error class invented from score alone
- Instruction-like payloads rejected; invalid/uncertain feedback degrades gracefully
- AI output never mutates accepted answers, grammar packs, or vocabulary data

### C. Grammar Companion integration

- Segment highlights (original vs correction)
- Curated rule when validated; general guidance otherwise
- Provisional diagnosis labeled; model suggestions visually distinct from reviewed examples
- Check / Continue / easier-related recovery preserved
- Dutch A1 remains pending expert validation

### D–E. SentenceSkillRecord + SQLite

- Separate append-only `sentence_skill_records.db` under guest/account data root
- No raw learner sentences, raw AI responses, or corrected text
- Idempotent submission insert; contradictory replay rejected; transactional writes; parsed UTC order
- Account / guest / language isolation; refuse production AppData / RC / recovery
- No automatic retention deletion; growth/retention/deletion documented in ADR
- No guest→account import; no `account_study.db` migration

### F. Cross-session selection

- Policy `sentence-skill-family-support-v1`: recent reliable local incorrect → related family scaffolding (lower ladder kind)
- Provisional AI evidence does not drive selection
- At most one grammar skill ref recorded per incorrect event
- No numeric mastery formula

### G. AI compatibility

- Optional duck-typed `supports_structured_feedback` / `structured_sentence_feedback` on Fake provider
- Old providers need no new ABC method; unsupported capability degrades from `GradeResult`
- No live AI; no LocalAIProvider; no hidden cloud fallback
- `C-APP-AI-001` v0.2.0 and deployed `/api/grade` unchanged

## Demo evidence

Root: `D:\EnglishApp\.local\19d5b-preview`  
Script: `scripts/sentence_skill_feedback_demo.py`  
Evidence JSON: `sentence-skill-evidence.json`  
Screenshots: conjugation structured feedback, grammar segments, restart scaffolding, provisional AI accept.

## Tests

| Suite | Count |
| --- | ---: |
| `tests/test_sentence_skill_feedback.py` | **14** |
| `tests/test_sentence_practice.py` (adjacent) | **26** |
| `tests/test_practice_records.py` (adjacent) | **8** |
| **Total this verification** | **48 passed** |

## Production AI requirements (future — not this phase)

1. Shared-contract revision before any additive `structured_feedback` wire field on `/api/grade`.
2. Server/provider must emit validated format_version + provisional flags; App remains the trust boundary.
3. No automatic promotion of provisional AI into reviewed answer keys without a content-review workflow.
4. SentenceSkillRecord cloud sync requires a separate additive sync design (not PracticeRecord, not progress events).
5. Do not implement LocalAIProvider or silent cloud fallback as part of structured feedback.

## Restrictions honored

No production access, no live AI, no deployed API/wire changes, no account_study migration, no server DB changes, no SentenceSkillRecord/PracticeRecord cloud sync, no mastery formula, no Grammar Library browser, no extra language packs, no installed Study-button activation, no locked adaptive activation, no EXE rebuild.
