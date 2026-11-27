# ADR-016 Listening audio is local-first and language-capability-aware

Status: Accepted

## Context

Phase 17A defined the `ListeningAudioProvider` seam with production resolve returning `None`. Phase 17B needs the first real playback backend. Cloud/Edge TTS would change privacy and network boundaries; machines also differ in which Windows voices are installed.

## Decision

- Production Listening audio uses **Windows installed System.Speech voices** (`WindowsLocalTTSProvider`) via a fixed PowerShell script.
- Learner text and voice names are passed only as **environment-variable data**, never interpolated into PowerShell source.
- Provider capability is **per study language** (`supports(language_code)`). Missing local voice → Listening **unavailable** for that language only; no silent wrong-language voice; no silent cloud/Edge fallback.
- Speech-locale preference order lives on the Windows TTS provider mapping (not StudyLanguage persistence). Listening remains settings-default **OFF**.
- StudyMaster must not enumerate Windows voices at construction time. Discovery runs off the Tk thread on first Listening open when the activity is enabled; the provider/catalog is reused for that StudyMaster lifetime. Async completion auto-opens only when still safe (no other study child; pending language still active). Listening session callbacks are bound to the window's language code.
- Phase 17B does **not** change Listening content generation (sample items remain for playback validation).

## Why

Local-first keeps lock-mode study offline/private. Language-aware unavailable keeps ScreenGuard finishable without shipping fake or wrong-language audio.

## Consequences

Easier: frozen exe uses OS speech without Python TTS packages. Harder: learners must install Windows language/TTS packs for each study language they want to hear.

## Do not

Do not silently fall back to online Edge TTS. Do not auto-install language packs. Do not persist generated audio files. Do not treat Listening answers as vocabulary mastery.

## Amendment — 2026-11-25 — Phase 19.3

- The speech rate is an integer from -10 to 10, passed only as the `STUDYGUARD_TTS_RATE` environment value. The UI uses 0 for normal and -4 for slow. A boolean is rejected.
- Gender is kept only when System.Speech reports Male, Female, or Neutral.
- The selected voice is stored on this PC under `device_voices`, one name per study language. It is not an account preference and it is not synced.
- An explicit voice is used only when that voice belongs to the requested language. A missing name falls back to another voice of the same language. A voice from another language is never selected, and there is no online fallback.
- On 2026-11-25, `Windows.Media.SpeechSynthesis` returned no voices. A later probe on 2026-11-27 found WinRT voices that System.Speech does not list, including Dutch and Portuguese. That probe did not integrate WinRT. The R2 amendment below is the integration. No paid speech service is added.

## Amendment — 2026-11-27 — Phase 19.3 R1

- Listening, Voice Settings, Vocabulary Library, Word Detail, and Study Feedback share one playback slot.
- A playback callback is delivered only when the originating window is open and the caller's language and exercise identity still match.
- Voice discovery and catalog refresh stay off the Tk thread, including the failure path.
- Missing-voice guidance names the selected language's Windows speech pack.

## Amendment — 2026-11-27 — Phase 19.3 R2

- `WindowsSpeechProvider` is the shared local catalog. System.Speech remains the voice used when it can speak the language.
- `Windows.Media.SpeechSynthesis` is used for the same language when System.Speech has no voice, and when the learner explicitly selects a WinRT voice. The voice id and the spoken text stay in environment data. The PowerShell script is fixed. Audio is played from memory and disposed. The registry is not modified.
- A saved System.Speech voice name still selects that System.Speech voice. A WinRT choice is stored as `winrt:` plus the voice id, on this PC only.
- No Python speech package is added. A frozen build keeps using PowerShell and does not need a new hidden import. This phase did not rebuild the executable.
