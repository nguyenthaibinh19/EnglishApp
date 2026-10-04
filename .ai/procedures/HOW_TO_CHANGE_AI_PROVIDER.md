# How to change / add an AI provider

See [ADR-003](../decisions/ADR-003-ai-provider-boundary.md), [invariants.md](../invariants.md).

## Architecture

```text
quiz / reading / account_server
        ↓
   ai_teacher facade
        ↓
      AIService
        ↓
     AIProvider   ← implement this
        ↓
  OpenAIProvider / future providers
```

## Steps

1. Implement the `AIProvider` interface (grade sentence, generate reading, enrich vocabulary, etc. as currently required).
2. Wire it through `AIService` (inject/select provider) — do not bypass the facade from UI.
3. Keep quiz/reading/vocab enrichment UI free of provider-specific SDKs.
4. Production secrets remain **server-side**; desktop uses account HTTP + token (`/api/grade`, `/api/reading`, `/api/enrich`).
5. Add a fake/provider stub test — no live OpenAI calls.
6. Run pytest (+ smoke if AI smoke paths are involved).
7. Update architecture/roadmap memory if a new production provider becomes real.
8. Vocabulary enrichment must remain advisory (draft → review → Apply); see ADR-012 / ADR-013.

## Do not

- Embed the server OpenAI API key in the desktop executable, settings, logs, or fixtures.
- Call OpenAI (or any cloud AI) directly from random Tk modules.
- Change mastery/SRS semantics inside an AI provider.
