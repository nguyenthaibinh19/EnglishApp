# ADR-002 Canonical study languages

Status: Accepted

## Context

The app grew from a Dutch-first product. Language metadata and “native/UI language” were easy to conflate with the language being studied.

## Decision

One canonical `StudyLanguage` registry for study codes (`nl`, `en`, `fr`, `de`, `es`, `it`, `pt`). Study language is separate from UI/native language (`vi` / `en`). Dutch may remain a compatibility default where required.

## Why

Multi-language learning needs a single registry for articles, elisions, labels, and data paths — without baking Dutch into every module.

## Consequences

Easier: add languages at the registry. Harder: leftover Dutch-specific copy in docs/UI may still exist and should be cleaned carefully.

## Do not

Do not hard-code study-language checks throughout core. Do not treat UI language as a study language.
