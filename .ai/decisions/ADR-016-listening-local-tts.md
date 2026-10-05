# ADR-016 Listening audio is local-first and language-capability-aware

Status: Accepted

## Context

Phase 17A defined the `ListeningAudioProvider` seam with production resolve returning `None`. Phase 17B needs the first real playback backend. Cloud/Edge TTS would change privacy and network boundaries; machines also differ in which Windows voices are installed.

## Decision

- Production Listening audio uses **Windows installed System.Speech voices** (`WindowsLocalTTSProvider`) via a fixed PowerShell script.
- Learner text and voice names are passed only as **environment-variable data**, never interpolated into PowerShell source.
- Provider capability is **per study language** (`supports(language_code)`). Missing local voice → Listening **unavailable** for that language only; no silent wrong-language voice; no silent cloud/Edge fallback.
- Speech-locale preference order lives on the Windows TTS provider mapping (not StudyLanguage persistence). Listening remains settings-default **OFF**.
- StudyMaster must not enumerate Windows voices at construction time. Discovery runs off the Tk thread on first Listening open when the activity is enabled; the provider/catalog is reused for that StudyMaster lifetime.
- Phase 17B does **not** change Listening content generation (sample items remain for playback validation).

## Why

Local-first keeps lock-mode study offline/private. Language-aware unavailable keeps ScreenGuard finishable without shipping fake or wrong-language audio.

## Consequences

Easier: frozen exe uses OS speech without Python TTS packages. Harder: learners must install Windows language/TTS packs for each study language they want to hear.

## Do not

Do not silently fall back to online Edge TTS. Do not auto-install language packs. Do not persist generated audio files. Do not treat Listening answers as vocabulary mastery.
