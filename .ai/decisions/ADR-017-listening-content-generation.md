# ADR-017 Listening content generation is target-language-first and StudyGuard-selected

Status: Accepted

## Context

Phase 17B delivered local Windows TTS behind `ListeningAudioProvider`. Listening still used tiny bundled samples. Production Listening needs AI-written short comprehension items without letting the model choose which vocabulary to reinforce, without cloud TTS, and without treating Listening answers as vocabulary mastery.

## Decision

- **StudyGuard selects target vocabulary** locally (today → Mistake Book → weakest → stable fill; max 2). AI does **not** choose targets.
- AI generates **one** structured `ListeningItem` only: study-language `text` / `question` / `answer` / `alternatives`; native-language `meaning`.
- Native help is **on demand** (word/sentence lookup). No automatic question translation field.
- **Answer must be grounded** in the spoken transcript (phrase present after case/whitespace fold). Question must not leak the answer phrase and should not exceed transcript difficulty unnecessarily.
- One reusable validator (`normalize_listening_item`) gates AI, account-server, and cache.
- Local validated JSON cache + bundled sample fallback. Audio remains the separate Windows TTS provider seam ([ADR-016](ADR-016-listening-local-tts.md)).
- Production desktop uses authenticated `POST /api/listening` (canonical `meaning` wire). No OpenAI key in the frozen app.
- Question/transcript word lookup reuses an in-window overlay helper (no ScreenGuard pause / no fullscreen flicker).
- Phase 17C does **not** persist Listening attempts, SRS, or mastery.

## Why

Keeps Listening language-first and deterministic to grade, while reinforcing StudyGuard-chosen vocabulary and preserving the local-first audio/privacy boundary.

## Consequences

Easier: cache/offline fallback; future `StudyGuardAIProvider` can implement the same capability. Harder: grounded-answer rule rejects some creative AI questions; machines still need a Windows voice for the study language.

## Do not

Do not add cloud/Edge TTS as silent fallback. Do not let AI pick vocabulary targets. Do not auto-translate the question. Do not record Listening mastery/attempt history in 17C. Do not grade Listening answers with AI.
