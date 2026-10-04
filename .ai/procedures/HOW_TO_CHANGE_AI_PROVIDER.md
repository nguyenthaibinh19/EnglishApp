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

1. Implement the `AIProvider` interface (grade sentence, generate reading, etc. as currently required).
2. Wire it through `AIService` (inject/select provider) — do not bypass the facade from UI.
3. Keep quiz/reading free of provider-specific SDKs.
4. Production secrets remain **server-side**; desktop uses account HTTP + token.
5. Add a fake/provider stub test — no live OpenAI calls.
6. Run pytest (+ smoke if AI smoke paths are involved).
7. Update architecture/roadmap memory if a new production provider becomes real.

## Do not

- Embed the server OpenAI API key in the desktop executable, settings, logs, or fixtures.
- Call OpenAI (or any cloud AI) directly from random Tk modules.
- Change mastery/SRS semantics inside an AI provider.
