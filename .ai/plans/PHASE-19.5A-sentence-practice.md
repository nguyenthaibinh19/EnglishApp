# PHASE-19.5A — Progressive Sentence Practice and Grammar Companion Foundation

**Status:** Closed (`APP_19D5A_CLOSED_SENTENCE_PRACTICE`)  
**Branch:** `phase19.5a/sentence-practice` (merged)  
**Baseline:** `a21f8c9e2ab314cdfcb31a223fc0bab1727768fd`  
**R1 accepted checkpoint:** `ad169f871181a0525f0e1145ed115c200272ddb1`  
**Architect:** `APP_19D5A_R1_ACCEPTED_FOR_CLOSEOUT`  
**Spec anchors:** Phase 19.1 §§7–10, E3

## Goal

Extend Adaptive Study from vocabulary recall to contextual sentence construction: a four-level progressive flow plus an expandable Grammar Companion backed by curated content.

## Closeout corrections (final)

| Area | Correction |
|------|------------|
| Diagnosis | Conjugation/article/word-order claimed only with sufficient evidence; random verb-blank tokens stay neutral |
| Guided writing | Evidenced template violations → incorrect; other alternatives → unlisted (not automatic wrong) |
| Recovery | Explicit easier related exercise; unavailable AI is not a learner failure |
| Fake provider | Labeled simulated development grading — not a live AI call |
| Lifecycle | Sentence windows closed on app exit; deferred Reading/Listening invalidated on destroy/account/language/Home |

## Content contract

Versioned model in `app/sentence_content.py` (`CONTENT_FORMAT_VERSION = 1`) including `family_id`.

Reviewed `accepted_answers` are content. AI drafts are not answer keys. Dutch A1 pack remains **author-curated** and **pending independent expert linguistic validation**.

Contract is language-aware for all seven study languages; only Dutch A1 ships.

## Progressive engine

Ladder: word bank → fill blank → guided writing → independent writing.

Outcomes: `reviewed_correct`, `incorrect`, `incomplete`, `unlisted`, `provisional_accept`, `provisional_correct`, `unavailable`, `ungraded`.

Progress = distinct achieved levels. Incomplete word-bank is not a failure. Provisional acceptance may advance but stays distinct from reviewed correctness (`provisional_acceptance_progression_policy()`).

## Grammar Companion

Contextual curated rule selection; uncertain → guidance without diagnosis claim. No Grammar Library browser.

## AI boundary

`AIService` + FakeSentenceGradeProvider (simulated). No live AI. No GradeResult wire-protocol changes. No persistent SentenceSkillRecord.

## Integration

Unlocked opt-in only (`LG_ADAPTIVE_STUDY=1` + isolated `LG_DATA_DIR`). Optional StudyMaster Sentence + post-adaptive CTA. Defers Reading/Listening until sentence ends. Not on installed Study button. Not locked-session. Not in v1.5.0 EXE.

## Learning data

Session-memory only. Zero vocabulary LearningAttempt, Progress, SRS, PracticeRecord v1, sync-outbox writes.

## Verification (closeout)

- Focused: `tests/test_sentence_practice.py` — **26 passed**
- Adjacent: adaptive vocabulary (18) + UI (10) + integration (12) — **40 passed**
- Combined focused+adjacent: **66 passed, 0 failed**

## Remaining limitations

- Dutch A1 only; author-curated pending expert validation  
- Session-memory only; no SentenceSkillRecord  
- No Grammar Library; no live AI; no additional languages  
- Not in public v1.5.0; not on installed Study button  

## Next

**Phase 19.5B Structured AI Feedback and Sentence Skill** — pending a separate Architect brief.

## STOP

Merged unreleased development functionality. No executable rebuild or release from this closeout.
