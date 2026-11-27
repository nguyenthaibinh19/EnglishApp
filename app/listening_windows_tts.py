"""Windows local TTS backend for Listening (Phase 17B).

Uses System.Speech via a fixed PowerShell script. Learner text and voice names
are passed only as environment-variable *data*, never interpolated into script
source (injection safety).

No Python TTS packages. No cloud/Edge TTS. No audio file persistence.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from listening import ListeningAudioError, ListeningAudioProvider

# Preferred Windows culture tags per StudyGuard study-language code.
# Kept on the Windows provider (not StudyLanguage) — only this backend needs them.
SPEECH_LOCALE_PREFERENCES: Dict[str, Tuple[str, ...]] = {
    "nl": ("nl-NL",),
    "en": ("en-US", "en-GB"),
    "fr": ("fr-FR", "fr-CA"),
    "de": ("de-DE",),
    "es": ("es-ES", "es-MX"),
    "it": ("it-IT",),
    "pt": ("pt-PT", "pt-BR"),
}

_ENV_TEXT = "STUDYGUARD_TTS_TEXT"
_ENV_VOICE = "STUDYGUARD_TTS_VOICE"
_ENV_RATE = "STUDYGUARD_TTS_RATE"

# System.Speech rate is an integer from -10 (slow) to 10 (fast).
RATE_MIN = -10
RATE_MAX = 10
NORMAL_RATE = 0
SLOW_RATE = -4

# Fixed preview lines. These are not learner answers.
PREVIEW_TEXT = {
    "nl": "Goedemorgen. Dit is een stemvoorbeeld.",
    "en": "Good morning. This is a voice preview.",
    "fr": "Bonjour. Ceci est un exemple de voix.",
    "de": "Guten Morgen. Dies ist eine Stimmprobe.",
    "es": "Buenos días. Esta es una muestra de voz.",
    "it": "Buongiorno. Questo è un esempio di voce.",
    "pt": "Bom dia. Esta é uma amostra de voz.",
}

# Fixed scripts — no placeholders for learner text, voice names, or rate.
_DISCOVER_SCRIPT = r"""
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
foreach ($voice in $synth.GetInstalledVoices()) {
    if (-not $voice.Enabled) { continue }
    $info = $voice.VoiceInfo
    $gender = ""
    try { $gender = [string]$info.Gender } catch { $gender = "" }
    Write-Output ($info.Name + [char]9 + $info.Culture.Name + [char]9 + $info.Culture.TwoLetterISOLanguageName + [char]9 + $gender)
}
"""

_SPEAK_SCRIPT = r"""
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voice = [Environment]::GetEnvironmentVariable('STUDYGUARD_TTS_VOICE')
$text = [Environment]::GetEnvironmentVariable('STUDYGUARD_TTS_TEXT')
$rateRaw = [Environment]::GetEnvironmentVariable('STUDYGUARD_TTS_RATE')
if ([string]::IsNullOrEmpty($voice) -or $null -eq $text) { exit 2 }
$rate = 0
if (-not [string]::IsNullOrEmpty($rateRaw)) {
    $parsed = 0
    if (-not [int]::TryParse($rateRaw, [ref]$parsed)) { exit 4 }
    if ($parsed -lt -10 -or $parsed -gt 10) { exit 4 }
    $rate = $parsed
}
try {
    $synth.SelectVoice($voice)
} catch {
    Write-Error $_.Exception.Message
    exit 3
}
$synth.Rate = $rate
$synth.Speak($text)
exit 0
"""

PowerShellRunner = Callable[..., subprocess.CompletedProcess]


@dataclass(frozen=True)
class WindowsVoiceInfo:
    name: str
    culture: str
    language: str  # TwoLetterISOLanguageName, lowercased
    gender: str = ""  # Male, Female, Neutral, or empty when the OS does not say


def _normalize_culture(value: str) -> str:
    return str(value or "").strip().replace("_", "-")


def _normalize_gender(value: str) -> str:
    key = str(value or "").strip().lower()
    if key in {"male", "female", "neutral"}:
        return key.capitalize() if key != "neutral" else "Neutral"
    return ""


def validate_rate(rate: int) -> int:
    """Accept only a real integer inside the System.Speech range."""
    if isinstance(rate, bool) or not isinstance(rate, int):
        raise ListeningAudioError("Speech rate is not valid.")
    if rate < RATE_MIN or rate > RATE_MAX:
        raise ListeningAudioError("Speech rate is not valid.")
    return rate


def parse_voice_discovery_output(raw: str) -> Tuple[WindowsVoiceInfo, ...]:
    """Parse discovery stdout lines: name<TAB>culture<TAB>lang[<TAB>gender]."""
    voices: List[WindowsVoiceInfo] = []
    for line in str(raw or "").splitlines():
        line = line.strip()
        if not line or "\t" not in line:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        name, culture, lang = parts[0].strip(), parts[1].strip(), parts[2].strip()
        gender = _normalize_gender(parts[3]) if len(parts) > 3 else ""
        if not name or not culture:
            continue
        voices.append(
            WindowsVoiceInfo(
                name=name,
                culture=_normalize_culture(culture),
                language=str(lang or "").strip().lower()
                or _normalize_culture(culture).split("-")[0].lower(),
                gender=gender,
            )
        )
    # Deterministic order for stable selection.
    voices.sort(key=lambda item: (item.language, item.culture.lower(), item.name.lower()))
    return tuple(voices)


def select_voice_for_language(
    language_code: str,
    voices: Sequence[WindowsVoiceInfo],
) -> Optional[WindowsVoiceInfo]:
    """Deterministic voice pick: preferred cultures, then same base language."""
    code = str(language_code or "").strip().lower()
    if not code or not voices:
        return None
    preferred = SPEECH_LOCALE_PREFERENCES.get(code, ())
    by_culture: Dict[str, List[WindowsVoiceInfo]] = {}
    for voice in voices:
        key = voice.culture.lower()
        by_culture.setdefault(key, []).append(voice)
    for culture in preferred:
        matches = by_culture.get(culture.lower())
        if matches:
            return sorted(matches, key=lambda item: item.name.lower())[0]
    # Same-language fallback (e.g. es-MX when only es-AR installed).
    same_lang = [voice for voice in voices if voice.language == code]
    if same_lang:
        return sorted(
            same_lang,
            key=lambda item: (item.culture.lower(), item.name.lower()),
        )[0]
    return None


def voices_for_language(
    language_code: str,
    voices: Sequence[WindowsVoiceInfo],
) -> Tuple[WindowsVoiceInfo, ...]:
    """Voices whose culture or two-letter language matches. Never another language."""
    code = str(language_code or "").strip().lower()
    if not code:
        return ()
    preferred = {item.lower() for item in SPEECH_LOCALE_PREFERENCES.get(code, ())}
    matched = [
        voice
        for voice in voices
        if voice.language == code or voice.culture.lower() in preferred
    ]
    return tuple(sorted(matched, key=lambda item: (item.culture.lower(), item.name.lower())))


def find_powershell_executable() -> Optional[str]:
    """Locate powershell.exe without requiring PATH mutations."""
    if sys.platform != "win32":
        return None
    found = shutil.which("powershell") or shutil.which("powershell.exe")
    if found:
        return found
    system_root = os.environ.get("SystemRoot") or os.environ.get("WINDIR") or r"C:\Windows"
    candidate = os.path.join(system_root, "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
    if os.path.isfile(candidate):
        return candidate
    return None


def default_powershell_runner(
    script: str,
    *,
    env: Optional[Dict[str, str]] = None,
    timeout: float = 30.0,
) -> subprocess.CompletedProcess:
    """Run a fixed PowerShell script with CREATE_NO_WINDOW; no console flash."""
    exe = find_powershell_executable()
    if not exe:
        raise ListeningAudioError("Windows PowerShell is not available.")
    merged = os.environ.copy()
    if env:
        merged.update(env)
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        return subprocess.run(
            [
                exe,
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            env=merged,
            timeout=timeout,
            creationflags=flags,
        )
    except subprocess.TimeoutExpired as error:
        raise ListeningAudioError("Speech playback timed out.") from error
    except FileNotFoundError as error:
        raise ListeningAudioError("Windows PowerShell is not available.") from error
    except OSError as error:
        raise ListeningAudioError("Could not start Windows speech process.") from error


class WindowsLocalTTSProvider(ListeningAudioProvider):
    """Production Listening audio via Windows installed System.Speech voices."""

    DISCOVER_TIMEOUT_SEC = 20.0
    SPEAK_TIMEOUT_SEC = 90.0

    def __init__(
        self,
        *,
        runner: Optional[PowerShellRunner] = None,
        voices: Optional[Sequence[WindowsVoiceInfo]] = None,
        platform: Optional[str] = None,
    ):
        self._runner = runner or default_powershell_runner
        self._platform = sys.platform if platform is None else platform
        self._voices: Optional[Tuple[WindowsVoiceInfo, ...]] = (
            tuple(voices) if voices is not None else None
        )
        self._init_error: Optional[str] = None
        self._voice_cache: Dict[str, Optional[WindowsVoiceInfo]] = {}

    def is_available(self) -> bool:
        if self._platform != "win32":
            return False
        try:
            voices = self._ensure_voices()
        except ListeningAudioError as error:
            self._init_error = str(error)
            return False
        except Exception as error:  # noqa: BLE001
            self._init_error = str(error)
            return False
        return True  # backend works even if no StudyGuard language has a voice yet

    def supports(self, language_code: str) -> bool:
        if not self.is_available():
            return False
        return self.resolve_voice(language_code) is not None

    def resolve_voice(
        self,
        language_code: str,
        voice_name: Optional[str] = None,
    ) -> Optional[WindowsVoiceInfo]:
        code = str(language_code or "").strip().lower()
        if not code:
            return None
        requested = str(voice_name or "").strip()
        cache_key = code if not requested else f"{code}\n{requested}"
        if cache_key in self._voice_cache:
            return self._voice_cache[cache_key]
        try:
            voices = self._ensure_voices()
        except ListeningAudioError:
            self._voice_cache[cache_key] = None
            return None
        pool = voices_for_language(code, voices)
        chosen: Optional[WindowsVoiceInfo] = None
        if requested:
            for voice in pool:
                if voice.name == requested:
                    chosen = voice
                    break
            # A saved voice from another language, or a removed voice, never wins.
            # A remaining same-language voice is the safe default.
            if chosen is None:
                chosen = select_voice_for_language(code, pool)
        else:
            chosen = select_voice_for_language(code, pool)
        self._voice_cache[cache_key] = chosen
        return chosen

    def voices_for(self, language_code: str) -> Tuple[WindowsVoiceInfo, ...]:
        return voices_for_language(language_code, self._ensure_voices())

    def cached_voices_for(
        self, language_code: str
    ) -> Optional[Tuple[WindowsVoiceInfo, ...]]:
        """Voices already discovered. None means discovery has not finished.

        This never starts PowerShell. Call it from the Tk thread.
        """
        if self._voices is None:
            return None
        return voices_for_language(language_code, self._voices)

    def refresh(self) -> Tuple[WindowsVoiceInfo, ...]:
        """Drop the catalog and discover again. Safe after the learner installs a voice."""
        self._voices = None
        self._voice_cache.clear()
        self._init_error = None
        return self._ensure_voices()

    def play(
        self,
        text: str,
        language_code: str,
        *,
        rate: int = NORMAL_RATE,
        voice_name: Optional[str] = None,
    ) -> None:
        if self._platform != "win32":
            raise ListeningAudioError("Windows speech is only available on Windows.")
        spoken = str(text or "")
        if not spoken.strip():
            raise ListeningAudioError("Nothing to speak.")
        chosen_rate = validate_rate(rate)
        voice = self.resolve_voice(language_code, voice_name=voice_name)
        if voice is None:
            raise ListeningAudioError(
                self.missing_voice_message(language_code)
            )
        # Data channel only — never splice text, voice, or rate into PowerShell source.
        env = {
            _ENV_VOICE: voice.name,
            _ENV_TEXT: spoken,
            _ENV_RATE: str(chosen_rate),
        }
        try:
            result = self._runner(
                _SPEAK_SCRIPT,
                env=env,
                timeout=self.SPEAK_TIMEOUT_SEC,
            )
        except ListeningAudioError:
            raise
        except Exception as error:  # noqa: BLE001
            raise ListeningAudioError("Speech playback failed.") from error
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            if result.returncode == 3:
                raise ListeningAudioError(
                    self.missing_voice_message(language_code)
                )
            raise ListeningAudioError(
                "Speech playback failed."
                + (f" ({detail})" if detail and len(detail) < 180 else "")
            )

    def missing_voice_message(self, language_code: str) -> str:
        """Safe learner-facing explanation (no shell commands)."""
        import config

        name = config.language_name(language_code) or str(language_code or "").upper()
        return config.ui(
            f"Chưa cài giọng đọc Windows cho {name}. "
            "Hãy cài gói ngôn ngữ / Text-to-speech trong Cài đặt Windows, "
            "rồi mở lại StudyGuard.",
            f"No Windows text-to-speech voice is installed for {name}. "
            "Install a text-to-speech voice in Windows Language/Speech settings, "
            "then reopen StudyGuard.",
        )

    def discovered_voices(self) -> Tuple[WindowsVoiceInfo, ...]:
        return self._ensure_voices()

    def _ensure_voices(self) -> Tuple[WindowsVoiceInfo, ...]:
        if self._voices is not None:
            return self._voices
        if self._platform != "win32":
            raise ListeningAudioError("Windows speech is only available on Windows.")
        if find_powershell_executable() is None and self._runner is default_powershell_runner:
            raise ListeningAudioError("Windows PowerShell is not available.")
        try:
            result = self._runner(
                _DISCOVER_SCRIPT,
                env=None,
                timeout=self.DISCOVER_TIMEOUT_SEC,
            )
        except ListeningAudioError:
            raise
        except Exception as error:  # noqa: BLE001
            raise ListeningAudioError("Could not discover Windows speech voices.") from error
        if result.returncode != 0:
            err = (result.stderr or "").strip()
            if "System.Speech" in err or "assembly" in err.lower():
                raise ListeningAudioError(
                    "Windows System.Speech is not available on this machine."
                )
            raise ListeningAudioError("Could not discover Windows speech voices.")
        self._voices = parse_voice_discovery_output(result.stdout or "")
        self._voice_cache.clear()
        return self._voices


def try_create_windows_tts_provider() -> Optional[WindowsLocalTTSProvider]:
    """Return a usable provider, or None when the backend cannot initialize."""
    if sys.platform != "win32":
        return None
    try:
        provider = WindowsLocalTTSProvider()
        if not provider.is_available():
            return None
        return provider
    except Exception:  # noqa: BLE001 - startup must stay safe
        return None
