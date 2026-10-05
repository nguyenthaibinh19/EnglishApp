# ADR-015 Listening activity and audio-provider seam

Status: Accepted

## Context

StudyGuard needs Listening as a real optional study activity inside StudySession (Vocabulary → Reading → Listening). Production TTS / STT / microphone are out of scope for Phase 17A, but Listening must not become an ad-hoc utility window or trap ScreenGuard when audio cannot play.

## Decision

- Listening is an **optional** StudySession activity when `listening_enabled` is true on `DailyStudyPlan` (settings `activities.listening`; **default OFF** until a production audio provider exists).
- Domain model: `ListeningItem` (`text` / `question` / `answer` / optional `alternatives` / `meaning`) + `ListeningSession` controller (**successful play → submit → finish** / unavailable). Submit before play and finish before answer are rejected. No Progress / SRS / AttemptHistory mutation in 17A.
- Audio boundary: `ListeningAudioProvider.play(text, language_code)` plus optional `supports(language_code)`. Production resolve returns `WindowsLocalTTSProvider` on Windows when System.Speech initializes; otherwise `None`. Tests/dev may inject `FakeListeningAudioProvider`. Missing provider or missing voice for the active language → activity **unavailable** (does not block session finish). Tk must call provider work via `ui_common.run_async`.
- Local-first Windows TTS policy: [ADR-016](ADR-016-listening-local-tts.md).
- When locked, ListeningApp owns ScreenGuard like Reading/Vocabulary. Tk `required` must not treat unresolved optional Listening as required. Skip resolves **only the active study language**.
- Answer checking reuses `text_utils.match_answer` for deterministic comprehension feedback (`exact`/`near` count as correct feedback); not vocabulary mastery.

## Why

Keeps Listening language-aware and Session-orchestrated without shipping fake production audio or coupling the UI to a future TTS engine.

## Consequences

Easier: Phase 17B plugs a real local provider behind the same seam. Harder: languages without an installed Windows voice stay unavailable until the learner installs a TTS pack (or a future explicit cloud provider is added).

## Do not

Do not embed production TTS keys in the desktop app. Do not treat Listening answers as vocab mastery / SRS events in 17A. Do not block ScreenGuard completion on audio failure.
