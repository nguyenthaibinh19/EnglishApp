# Phase 19.5B — Structured AI Feedback and Persistent Sentence Skill

**Status:** Closed (`APP_19D5B_CLOSED_STRUCTURED_FEEDBACK_SENTENCE_SKILL`)  
**Branch:** `phase19.5b/structured-feedback-sentence-skill`  
**Base main:** `e37fea87cedb38466d804e2294d3eb1b0a4136c7`  
**Review checkpoint:** `b37afac6a7627e9f9d9191e59fe08fc9f6220a95`  
**Architect:** `APP_19D5B_FOUNDATION_ACCEPTED_CLOSEOUT_CORRECTIONS_REQUIRED`  
**ADR:** [ADR-027](../decisions/ADR-027-structured-sentence-feedback-and-skill.md) (Accepted)  
**Merged, unreleased development functionality.** Not in v1.5.0.

## Objective

Make sentence feedback structured, evidence-aware, and reusable for future personalized grammar practice — inside the existing integrated development application (not a standalone learning app).

## Delivered

### A. Structured feedback contract (App-domain)

- `app/sentence_feedback.py` — `StructuredSentenceFeedback` format version **1**
- Trust-boundary validation: exact types, enums, segment direction, correction context, source/status/provisional semantics
- **Does not change** `GradeResult` meaning or required fields
- One GradeResult per submission; structured mapped for compatibility; contradictions discarded
- Future `/api/grade` transport mapping documented only

### B–C. Session plan + Grammar Companion

- Explicit session plan from adaptive start; skipped levels not claimed as demonstrated
- Progress = achieved planned levels / plan size; finite completion from Fill Blank / Guided starts
- Segment highlights; curated rule when validated; model suggestions distinct from reviewed examples
- Dutch A1 remains pending expert validation

### D–E. SentenceSkillRecord + selection

- Append-only `sentence_skill_records.db`; no raw answers/AI text
- Policy `sentence-skill-family-support-v1`: harder incorrect not cleared by easier success
- Unavailable storage distinct from disabled; honest feedback; store closed on lifecycle events

### F. AI compatibility

- Optional duck-typed structured capability; old providers need no new ABC method
- No live AI; no LocalAIProvider; `C-APP-AI-001` v0.2.0 unchanged

## Closeout corrections

- Session completion for nonzero adaptive starts
- Strict feedback field types and AI/local consistency
- Selection resolution requires same/harder reviewed correct
- Store init failure + resource cleanup
- Grammar Companion rule correspondence

## Demo evidence

Root: `D:\EnglishApp\.local\19d5b-preview`  
Script: `scripts/sentence_skill_feedback_demo.py`  
Restart: conjugation miss → reopen selects `word_bank` / `nl-a1-family-lezen-boek`

## Tests (closeout verification)

| Suite | Count |
| --- | ---: |
| `tests/test_sentence_skill_closeout.py` | **10** |
| `tests/test_sentence_skill_feedback.py` | **14** |
| `tests/test_sentence_practice.py` | **26** |
| `tests/test_practice_records.py` | **8** |
| `tests/test_adaptive_study_integration.py` | **12** |
| `tests/test_adaptive_vocabulary.py` | **18** |
| **Total** | **88 passed** |

## Production AI requirements (future — not this phase)

1. Shared-contract revision before any additive `structured_feedback` wire field on `/api/grade`.
2. Server/provider must emit validated format_version + provisional flags; App remains the trust boundary.
3. No automatic promotion of provisional AI into reviewed answer keys without a content-review workflow.
4. SentenceSkillRecord cloud sync requires a separate additive sync design.
5. Do not implement LocalAIProvider or silent cloud fallback as part of structured feedback.

## Next product priority

Phase 19.6 Library, Progress and Settings — pending a separate Architect brief.
