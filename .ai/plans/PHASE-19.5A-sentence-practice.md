# PHASE-19.5A — Progressive Sentence Practice and Grammar Companion Foundation

**Status:** Ready for review (`APP_19D5A_SENTENCE_PRACTICE_READY_FOR_REVIEW`)  
**Branch:** `phase19.5a/sentence-practice`  
**Baseline:** `a21f8c9e2ab314cdfcb31a223fc0bab1727768fd`  
**Architect:** `APP_19D4C_ARCHITECT_ACCEPTED_CLOSED`  
**Spec anchors:** Phase 19.1 §§7–10, E3

## Goal

Extend Adaptive Study from vocabulary recall to contextual sentence construction: a four-level progressive flow plus an expandable Grammar Companion backed by curated content.

## Content contract

Versioned model in `app/sentence_content.py` (`CONTENT_FORMAT_VERSION = 1`):

| Field | Role |
|-------|------|
| `exercise_id` | Stable content id |
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

Local deterministic grading for reviewed answers (`app/sentence_grading.py`): punctuation, Unicode, capitalization, repeated tokens, and multiple accepted strings.

- Success advances one level.  
- Repeated failure (`MAX_FAILURES_PER_LEVEL = 2`) steps down one level.  
- No infinite retry completion; abandon is safe.  
- Sentence practice is **never** forced after a wrong vocabulary answer.

## Grammar Companion

`app/grammar_companion.py` + expandable UI in `SentencePracticeApp`:

- Short beginner explanation + fuller validated rule  
- Color-coded components (stable semantic colors)  
- Corrected sentence + up to two reviewed examples  
- Continue remains available while expanded  
- Hidden on independent vocabulary recall cards  
- No rule invented when none is validated; ordinary feedback only  
- Full Grammar Library browser **not** in this wave

## AI boundary

Reuses `AIService` / `GradeRequest` / `GradeResult` with `use_account_proxy=False`.

- Reviewed answers: local only.  
- Independent writing outside the reviewed set: async adapter; FakeSentenceGradeProvider for demos/tests.  
- Unavailable / malformed / uncertain → provisional or ungraded, **not** definitive wrong.  
- AI feedback never becomes a reviewed answer key or grammar rule.  
- Score alone does not invent linguistic error classes.

Documented future extensions: `future_ai_feedback_contract_extensions()` and `future_sentence_skill_record_contract()` in `sentence_content.py`.

No production AI calls, no new endpoints, no new credentials.

## UI and integration

- CustomTkinter `StudyCardShell`, warm cream/green design.  
- Word-bank with undo, blank input, grammar template, independent input, Check / Continue, Why?, Normal + Slow hear.  
- Optional **Sentence** action on StudyMaster language row and optional post-adaptive complete CTA — same opt-in as Adaptive (`LG_ADAPTIVE_STUDY=1` + isolated `LG_DATA_DIR`).  
- Separate from required vocabulary completion; skip/leave does not undo saved vocab attempts.  
- Reading / Listening orchestration unchanged.  
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

| Kind | Exercise ids (summary) |
|------|-------------------------|
| Word bank | `nl-a1-wb-drink-water`, `nl-a1-wb-leest-boek` |
| Fill blank | `nl-a1-fb-hij-drinkt` (conjugation) |
| Guided | `nl-a1-gw-leest-boek` (Zij/Ze variants) |
| Independent | `nl-a1-iw-koop-fiets` |
| Rules | SVO main clause, present -t, basic articles |

Patterns: SVO, present conjugation, articles, main-clause order.

## Preview

```bat
set LG_DATA_DIR=D:\EnglishApp\.local\19d5a-preview
set LG_ADAPTIVE_STUDY=1
set LOCK_SCREEN=0
python scripts/sentence_practice_demo.py
```

Screenshots under `D:\EnglishApp\.local\19d5a-preview\screenshots\`.

Manual StudyMaster path: same env → Home → Study → **Sentence** (or Adaptive complete → optional sentence CTA).

## Verification

- Focused: `tests/test_sentence_practice.py`  
- Adjacent: `tests/test_adaptive_vocabulary.py`, `test_adaptive_vocabulary_ui.py`, `test_adaptive_study_integration.py`  
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
