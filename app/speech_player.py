"""One local playback at a time, off the Tk thread."""

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


def invalidate_playback() -> None:
    """Ignore the UI callback for any playback already running."""
    global _generation
    with _lock:
        _generation += 1


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
    on_done: Optional[Callable[[], None]] = None,
    on_error: Optional[Callable[[Exception], None]] = None,
) -> bool:
    """Start playback. Return False when another clip is already speaking."""
    global _busy, _generation
    with _lock:
        if _busy:
            return False
        _busy = True
        token = _generation
    engine = provider if provider is not None else shared_provider()
    spoken_language = str(language_code or "")

    def runner():
        global _busy
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
            with _lock:
                stale = token != _generation
                _busy = False

        def deliver():
            if stale:
                return
            try:
                if window is None or not window.winfo_exists():
                    return
            except Exception:
                return
            if error is None:
                if on_done is not None:
                    on_done()
            elif on_error is not None:
                on_error(error)

        try:
            window.after(0, deliver)
        except Exception:
            pass

    threading.Thread(target=runner, name="languageguard-speech", daemon=True).start()
    return True
