# ADR-011 Vocabulary enrichment data model

Status: Accepted

## Context

Phase 14 established language-neutral lexical fields (`meaning`, `alternatives`, optional `part_of_speech`). Future dictionary/AI enrichment needs a place to store structured examples, IPA, and a few inflected forms without inventing providers yet. A single string `example` cannot hold multiple examples or optional translations.

This extends [ADR-010](ADR-010-vocabulary-model-v2.md); it does not supersede it.

## Decision

Add optional enrichment structures on `VocabularyEntry`:

- `examples[]` with `{text, meaning?}` (legacy string `example` migrates here)
- `pronunciation.ipa` (omit empty objects)
- `forms` with a small controlled set: `plural`, `past`, `past_participle`, `comparative`, `superlative`

Article/gender, CEFR, frequency, audio/TTS, synonyms, and provider pipelines remain out of scope.

## Why

Storage/domain readiness must precede enrichment providers. Structured optional fields avoid another breaking rename and keep quiz/SRS unaffected.

## Consequences

Easier: Phase 15B+ can fill these fields from dictionary/AI. Harder: dual read of legacy `example` until user files migrate; UI should only show populated enrichment.

## Do not

Do not auto-enrich from the network in this model-only phase. Do not regenerate vocab UUIDs. Do not use enrichment fields for answer matching. Do not rewrite ADR-010 history to pretend enrichment always existed.
