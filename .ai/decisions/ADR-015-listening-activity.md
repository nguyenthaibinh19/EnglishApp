# ADR-015 Listening activity and audio-provider seam

Status: Accepted

## Context

StudyGuard needs Listening as a real optional study activity inside StudySession (Vocabulary → Reading → Listening). Production TTS / STT / microphone are out of scope for Phase 17A, but Listening must not become an ad-hoc utility window or trap ScreenGuard when audio cannot play.

## Decision

- Listening is an **optional** StudySession activity when `listening_enabled` is true on `DailyStudyPlan` (settings `activities.listening`; **default OFF** until a production audio provider exists).
- Domain model: `ListeningItem` (`text` / `question` / `answer` / optional `alternatives` / `meaning`) + `ListeningSession` controller (play → submit → finish / unavailable). No Progress / SRS / AttemptHistory mutation in 17A.
- Audio boundary: `ListeningAudioProvider.play(text, language_code)`. Production `resolve_listening_audio_provider()` returns `None`. Tests/dev inject `FakeListeningAudioProvider`. Missing/unavailable provider → activity **unavailable** (does not block session finish after required work).
- Answer checking reuses `text_utils.match_answer` for deterministic comprehension feedback (`exact`/`near` count as correct feedback); not vocabulary mastery.

## Why

Keeps Listening language-aware and Session-orchestrated without shipping fake production audio or coupling the UI to a future TTS engine.

## Consequences

Easier: Phase 17B can plug a real provider behind the same seam. Harder: enabled Listening with no provider always resolves as unavailable until TTS lands.

## Do not

Do not embed production TTS keys in the desktop app. Do not treat Listening answers as vocab mastery / SRS events in 17A. Do not block ScreenGuard completion on audio failure.
