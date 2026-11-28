# PHASE-19.5A — Progressive Sentence Practice and Grammar Companion Foundation

**Status:** Corrected ready for review (`APP_19D5A_SENTENCE_PRACTICE_CORRECTED_READY_FOR_REVIEW`)  
**Branch:** `phase19.5a/sentence-practice`  
**Baseline:** `a21f8c9e2ab314cdfcb31a223fc0bab1727768fd`  
**Foundation checkpoint:** `9c8bfe14b7304ae659a982202d88e29a369802e1`  
**Architect:** `APP_19D5A_FOUNDATION_ACCEPTED_CORRECTION_REQUIRED`  
**Spec anchors:** Phase 19.1 §§7–10, E3

## Goal

Extend Adaptive Study from vocabulary recall to contextual sentence construction: a four-level progressive flow plus an expandable Grammar Companion backed by curated content.

## R1 corrections (summary)

| Area | Correction |
|------|------------|
| Families | `family_id` on exercises; step-down prefers same family; NL A1 ships one complete four-level family (`nl-a1-family-lezen-boek`) |
| Grading | Distinct statuses: `reviewed_correct`, `incorrect`, `incomplete`, `unlisted`, `provisional_accept`, `provisional_correct`, `unavailable`, `ungraded` |
| Open writing | Unlisted answers are not definitive wrong; AI path only |
| Word bank | Incomplete selections do not fail the exercise |
| Fake AI | English rejected for Dutch; malformed score/bool → `ungraded` |
| Grammar | Rule selected by error hint + certainty; uncertain → guidance without diagnosis claim |
| Progress | Distinct achieved levels (max 4/4); repeats do not false-complete |
| Binding | `instance_id` + `submission_id`; stale AI ignored |
| Completion | Abandon / missing content never celebrate; `take_completion` requires all levels |
| StudyMaster | Sentence CTA parent = continue_button master; defers Reading/Listening; resumes once |
| Audio | Reviewed-sentence speech gate; saved voice; missing/busy feedback |

### Provisional acceptance progression

See `provisional_acceptance_progression_policy()`: `provisional_accept` may advance the ladder, but session results and learner feedback keep it distinct from `reviewed_correct`.

## Content contract

Versioned model in `app/sentence_content.py` (`CONTENT_FORMAT_VERSION = 1`):

| Field | Role |
|-------|------|
| `exercise_id` | Stable content id |
| `family_id` | Links related scaffolding across levels |
| `content_version` | Pack/exercise version |
| `language_code` / `cefr` | Study language + level |
| `target_lemma` / `target_vocab_id` | Lexical reference (optional) |
| `prompt` + `translation_en` / `translation_vi` | Prompt and learner-language support |
| `kind` / `support_level` | Ladder step + assisted/independent |
| `accepted_answers` | Reviewed answer keys (multiple allowed) |
| `word_bank` / `blank_sentence` / `grammar_template` | Level-specific support |
| `grammar_rule_ids` | Pointers into curated `GrammarRule` rows |
| `components` | Color-coded S/V/O (and article) segments |
| `provenance` / `review_status` | Source + review honesty |

Arbitrary AI output and vocabulary `examples` are **not** answer keys. Multiple reviewed answers are first-class. Unlisted but potentially valid sentences use the AI adapter as **provisional** only and never mutate the pack.

Contract is language-aware for all seven study languages; only **Dutch A1** ships a curated pack (`app/sentence_packs/nl_a1.py`).

### Review honesty

- Pack review status: `curated_author` / `pending_expert_validation`.
- Checklist is recorded on the pack. Do **not** claim independent expert linguistic certification.
- Native explanations ship in English and Vietnamese for the initial pack.

## Progressive engine

`app/sentence_practice.py` — ladder:

1. Word-bank arrangement  
2. Fill-in-the-blank  
3. Guided writing  
4. Independent writing  

Local deterministic grading for reviewed answers (`app/sentence_grading.py`): punctuation, Unicode, capitalization, token multiplicity, and multiple accepted strings.

- Success advances one level (reviewed or provisional accept).  
- Repeated failure (`MAX_FAILURES_PER_LEVEL = 2`) steps down one level within the active family.  
- Incomplete word-bank input is not a failure.  
- No infinite retry completion; abandon is safe.  
- Sentence practice is **never** forced after a wrong vocabulary answer.

## Grammar Companion

`app/grammar_companion.py` + expandable UI in `SentencePracticeApp`:

- Selects curated rule from error hint when diagnosis is certain  
- Uncertain → learning guidance without claiming a specific diagnosis  
- Color-coded components + reviewed corrected sentence (not AI suggestion as rule/example)  
- Pending expert-validation status remains visible  
- Continue remains available while expanded  
- Hidden on independent vocabulary recall cards  
- Full Grammar Library browser **not** in this wave

## AI boundary

Reuses `AIService` / `GradeRequest` / `GradeResult` with `use_account_proxy=False`.

- Reviewed answers: local only.  
- Independent writing outside the reviewed set: async adapter; FakeSentenceGradeProvider for demos/tests.  
- GradeResult validation: `is_correct_usage` must be bool; score finite in `[0, 1]` — else `ungraded`.  
- Unavailable / malformed / uncertain → not definitive wrong.  
- AI feedback never becomes a reviewed answer key or grammar rule.  
- Score alone does not invent linguistic error classes.

Documented future extensions: `future_ai_feedback_contract_extensions()` and `future_sentence_skill_record_contract()`.

No production AI calls, no new endpoints, no new credentials, no GradeResult wire-protocol changes.

## UI and integration

- CustomTkinter `StudyCardShell`, warm cream/green design.  
- Word-bank with undo, blank input, grammar template, independent input, Check / Continue, Why?, Normal + Slow hear (reviewed sentences only).  
- Optional **Sentence** action on StudyMaster language row and optional post-adaptive complete CTA — same opt-in as Adaptive (`LG_ADAPTIVE_STUDY=1` + isolated `LG_DATA_DIR`).  
- Post-vocab sentence defers Reading/Listening; after sentence complete/skip/leave resumes StudySession flow exactly once.  
- Account switch / language change / exit invalidate sentence windows.  
- Separate from required vocabulary completion.  
- No installed Study-button activation; no locked-session adaptive; no EXE rebuild.

## Learning data boundaries

Sentence performance is a **separate skill**. This wave keeps results in **session memory only**.

Must **not**:

- Create vocabulary `LearningAttempt` rows  
- Call `Progress.record`  
- Increment vocabulary mastery / streak  
- Change SRS intervals  
- Clear Mistake Book attention  
- Create vocabulary progress outbox events  
- Store results in PracticeRecord v1  

Future persistence requires a separate `SentenceSkillRecord` contract (documented, not implemented).

## Content coverage (Dutch A1)

Family `nl-a1-family-lezen-boek` (all four levels):

| Kind | Exercise id |
|------|-------------|
| Word bank | `nl-a1-wb-leest-boek` |
| Fill blank | `nl-a1-fb-zij-leest` |
| Guided | `nl-a1-gw-leest-boek` |
| Independent | `nl-a1-iw-leest-boek` |

Rules: SVO main clause, present `-t`, basic articles. Zij/Ze variants reviewed.

## Preview

```bat
set LG_DATA_DIR=D:\EnglishApp\.local\19d5a-preview
set LG_ADAPTIVE_STUDY=1
set LOCK_SCREEN=0
python scripts/sentence_practice_demo.py
```

Screenshots under `D:\EnglishApp\.local\19d5a-preview\screenshots\` (conjugation, Grammar Companion, provisional AI, completion).

## Verification

- Focused: `tests/test_sentence_practice.py`  
- Adjacent: adaptive vocabulary + UI + integration  
- Demo evidence: `sentence-evidence.json` (isolation flags all true)

## Limitations (unresolved / deferred)

- Only Dutch A1 curated pack; other languages have contract only.  
- Grammar rules are author-curated, pending expert validation.  
- No persistent sentence skill history.  
- No Grammar Library browser.  
- Structured AI error classes require a future GradeResult extension.  
- Fake provider is deterministic; no live AI in this wave.  
- Not in public v1.5.0; not on installed Study button.

## STOP

Do not merge until Architect/Leader review. No production access, schema migration, Cloud Sync changes, or executable rebuild.
