# ADR-012 Enrichment review before apply

Status: Accepted

## Context

Phase 15A added optional enrichment storage (`examples`, `pronunciation.ipa`, controlled `forms`). Dictionary and AI sources will eventually propose values for those fields. Silently writing external suggestions into canonical `VocabularyEntry` would corrupt learner-owned data and break trust.

This extends [ADR-011](ADR-011-vocabulary-enrichment-model.md); it does not supersede identity ([ADR-009](ADR-009-stable-vocabulary-identity.md)) or lexical naming ([ADR-010](ADR-010-vocabulary-model-v2.md)).

## Decision

Enrichment flows through an ephemeral draft and explicit apply:

```text
VocabularyEntry → EnrichmentService → Provider → EnrichmentDraft
    → review / select / edit → apply_enrichment → VocabStore.update → VocabularyEntry
```

- `EnrichmentDraft` is never auto-persisted in `vocab.json`.
- Apply is field-selective; omitted draft fields do not clear canonical data.
- Examples append (with exact-duplicate skip); forms merge by selected keys.
- IPA / POS overwrite only when explicitly selected.
- Production UI does not expose a working Enrich action until a real provider is configured.

## Why

External enrichment must never silently overwrite canonical vocabulary. Review-before-apply keeps lexical metadata learner-owned while still allowing future dictionary/AI assistance.

## Consequences

Easier: safe connection of real providers in Phase 15C. Harder: UI must present current vs suggested state; providers cannot write VocabStore directly.

## Do not

Do not auto-apply network enrichment on Add Word or load. Do not persist draft files. Do not regenerate `vocab_id` when applying enrichment. Do not use enrichment fields for answer matching.
