# ADR-003 AI provider boundary

Status: Accepted

## Context

Quiz/reading risked depending on OpenAI SDK details. Production keys must never ship inside the desktop executable.

## Decision

Architecture: consumers → `ai_teacher` facade → `AIService` → `AIProvider` → `OpenAIProvider`. Future `StudyGuardAIProvider` / `LocalModelProvider` implement the same domain interface. Desktop production calls go through the account server.

## Why

OpenAI is one implementation, not the product architecture. Local/self-hosted AI must plug in without rewriting quiz/reading business logic.

## Consequences

Easier: fake providers in tests; swap backends. Harder: cannot “just call OpenAI” from random UI modules.

## Do not

Do not embed the server OpenAI API key in the frozen app, settings, logs, or fixtures. Do not make quiz/reading import provider SDKs directly.
