"""One local playback at a time, off the Tk thread.

Listening, Voice Settings, Vocabulary Library, Word Detail, and Study Feedback
all take the same gate. A callback runs only when the window is still open and
the caller's scope still matches the exercise that started the clip.
"""

from __future__ import annotations

import threading
from typing import Callable, Optional

from listening import ListeningAudioError
from listening_windows_tts import NORMAL_RATE, WindowsLocalTTSProvider

_lock = threading.Lock()
_busy = False
_generation = 0
_provider: Optional[WindowsLocalTTSProvider] = None


def playback_busy() -> bool:
    with _lock:
        return _busy


def reset_playback_state() -> None:
    """Drop the shared slot. Tests use this so one case cannot block the next."""
    global _busy, _generation, _provider
    with _lock:
        _busy = False
        _generation += 1
        _provider = None


def invalidate_playback() -> None:
    """Drop UI callbacks for playback that is already running."""
    global _generation
    with _lock:
        _generation += 1


def reserve_playback() -> Optional[int]:
    """Take the single playback slot. None means another clip owns it."""
    global _busy
    with _lock:
        if _busy:
            return None
        _busy = True
        return _generation


def finish_playback(token: int) -> bool:
    """Release the slot. False means the callback must not touch the UI."""
    global _busy
    with _lock:
        current = token == _generation
        _busy = False
        return current


def shared_provider() -> WindowsLocalTTSProvider:
    global _provider
    with _lock:
        if _provider is None:
            _provider = WindowsLocalTTSProvider()
        return _provider


def refresh_voices() -> tuple:
    provider = shared_provider()
    return provider.refresh()


def play_async(
    window,
    *,
    text: str,
    language_code: str,
    rate: int = NORMAL_RATE,
    voice_name: Optional[str] = None,
    provider=None,
    scope: Optional[Callable[[], bool]] = None,
    on_done: Optional[Callable[[], None]] = None,
    on_error: Optional[Callable[[Exception], None]] = None,
    on_settled: Optional[Callable[[], None]] = None,
) -> bool:
    """Start playback. Return False when another clip is already speaking.

    ``scope`` is checked on the UI thread at delivery. When it is false, the
    done and error callbacks are skipped. ``on_settled`` still runs so the
    originating window can clear a stale Playing line.
    """
    token = reserve_playback()
    if token is None:
        return False
    engine = provider if provider is not None else shared_provider()
    spoken_language = str(language_code or "")

    def runner():
        error: Optional[Exception] = None
        try:
            engine.play(
                text,
                spoken_language,
                rate=rate,
                voice_name=voice_name or None,
            )
        except Exception as exc:  # noqa: BLE001 - deliver to the UI callback
            error = exc if isinstance(exc, ListeningAudioError) else ListeningAudioError(str(exc))
        finally:
            current = finish_playback(token)

        def deliver():
            alive = True
            try:
                if window is None or not window.winfo_exists():
                    alive = False
            except Exception:
                alive = False
            if not alive:
                return
            in_scope = current and (scope is None or bool(scope()))
            if in_scope:
                if error is None:
                    if on_done is not None:
                        on_done()
                elif on_error is not None:
                    on_error(error)
            if on_settled is not None:
                on_settled()

        try:
            window.after(0, deliver)
        except Exception:
            pass

    threading.Thread(target=runner, name="languageguard-speech", daemon=True).start()
    return True
