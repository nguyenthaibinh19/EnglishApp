# ADR-010 Vocabulary Model v2

Status: Accepted

## Context

Entries used `vi` for meaning (Vietnamese-named) while the app supports Vietnamese or English UI/native language and seven study languages. `alt`/`type` were inconsistently shaped; `type` was unused in bundled data.

## Decision

Canonical local lexical model: `VocabularyEntry` with persisted fields `id`, `word`, `meaning`, optional `alternatives`, `example`, `note`, `part_of_speech`. Legacy `vi`/`alt`/`type`/`nl`/`en` still load; canonical values win when both exist. New writes use canonical fields. Account HTTP may still wire meaning as `vi` for compatibility. Article/gender metadata deferred (articles remain in headword + language profiles).

## Why

`meaning` is language-neutral. Stable lexical names unblock enrichment without another rename crisis. Unknown legacy `type` values must be preserved, not dropped.

## Consequences

Easier: multi-native UI and future dictionary enrichment. Harder: dual read paths until user files fully migrate.

## Do not

Do not make `vi` the primary local field again. Do not discard unknown POS/`type` data. Do not add CEFR/IPA/TTS in the same change as a silent schema rename.
