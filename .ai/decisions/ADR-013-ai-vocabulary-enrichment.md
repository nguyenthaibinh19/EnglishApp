# ADR-013 AI vocabulary enrichment (advisory, server-mediated)

Status: Accepted

## Context

Phase 15B established review-before-apply drafts ([ADR-012](ADR-012-enrichment-review-before-apply.md)). Learners need a real production source for POS / forms / examples without weakening the AI secret boundary ([ADR-003](ADR-003-ai-provider-boundary.md)) or silently mutating canonical vocabulary.

## Decision

AI vocabulary enrichment v1 is:

- **Advisory only** — returns an ephemeral `EnrichmentDraft`; canonical `VocabularyEntry` changes only after explicit Apply.
- **Server-mediated in production** — desktop → authenticated account-server `/api/enrich` → `AIService` → `AIProvider` → `OpenAIProvider`. The production OpenAI key stays server-side.
- **Scoped** — proposes `part_of_speech`, controlled `forms`, and up to 2 `examples` only. Does **not** generate IPA, article/gender, CEFR, or rewrite `word` / `meaning`.
- **Validated** — model JSON is untrusted; unsupported POS / unknown form keys / excess examples are omitted or rejected.

Desktop implements `AccountServerVocabularyEnrichmentProvider` as a `VocabularyEnrichmentProvider`. Dev machines with a local `.env` OpenAI key may call `OpenAIProvider` through `AIService` (same grade/reading pattern).

## Why

Keeps learner-owned lexical data safe, reuses the existing AI abstraction, and avoids embedding production secrets in the desktop app.

## Consequences

Easier: Word Detail Enrich → review → Apply. Harder: old servers without `/api/enrich` must fail gracefully (no vocab corruption). IPA remains storage-capable but uses a future authoritative source, not AI v1.

## Do not

Do not auto-enrich on add/edit/open. Do not return the OpenAI key to the desktop. Do not bypass review-before-apply. Do not send Progress / Attempts / Mistake Book history to the model.
