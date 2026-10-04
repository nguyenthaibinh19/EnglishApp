# ADR-009 Stable vocabulary identity

Status: Accepted

## Context

Learning state was keyed by `normalize(word)`. Renaming a headword orphaned Progress, SRS, attempts, and Mistake Book. Duplicate meanings for the same spelling were impossible to model safely.

## Decision

Every vocabulary item has an immutable UUID (`id` / `vocab_id`), generated once with `str(uuid.uuid4())`. Spelling is editable display content. Progress v3 keys by UUID; attempts store `vocab_id` when known and keep `word` as a snapshot. Migration is idempotent with legacy compatibility (`legacy_index`, word fallback).

## Why

Required for rename safety, consistent Mistake Book/Library detail, and future cloud sync / AI datasets.

## Consequences

Easier: rename and enrichment. Harder: migrations must never regenerate IDs; ambiguous legacy duplicates need conservative first-match rules.

## Do not

Do not use hash(normalized_word) as identity. Do not regenerate IDs on edit. Do not invent UUID migration twice.
