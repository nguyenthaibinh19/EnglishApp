"""Developer probe: list Windows TTS voices and StudyGuard language support.

Not part of normal pytest. Run manually:

    python app/probe_windows_tts.py
"""

from __future__ import annotations

import os
import sys

# Allow `python app/probe_windows_tts.py` from repo root.
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

from languages import iter_languages  # noqa: E402
from listening_windows_tts import (  # noqa: E402
    WindowsLocalTTSProvider,
    find_powershell_executable,
)


def main() -> int:
    print("StudyGuard Windows TTS probe")
    print(f"platform={sys.platform}")
    print(f"powershell={find_powershell_executable() or '(missing)'}")
    if sys.platform != "win32":
        print("Not Windows — production provider will resolve to None.")
        return 0
    provider = WindowsLocalTTSProvider()
    if not provider.is_available():
        print("Provider unavailable (System.Speech / discovery failed).")
        return 1
    print("\nWindows voices:")
    for voice in provider.discovered_voices():
        print(f"- {voice.name}")
        print(f"  culture={voice.culture} lang={voice.language}")
    print("\nStudyGuard support:")
    for lang in iter_languages():
        voice = provider.resolve_voice(lang.code)
        if voice is None:
            print(f"{lang.code}: missing")
        else:
            print(f"{lang.code}: available ({voice.name}, {voice.culture})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
