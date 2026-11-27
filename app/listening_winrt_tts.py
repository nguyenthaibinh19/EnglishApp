"""Windows.Media.SpeechSynthesis voices that System.Speech cannot select.

Learner text, the voice id, and the speed travel as environment data.
The PowerShell scripts are fixed source. Nothing is written to the registry.
Synthesized audio stays in memory and is disposed after playback.
"""

from __future__ import annotations

import sys
from typing import List, Optional, Sequence, Tuple

from listening import ListeningAudioError
from listening_windows_tts import (
    NORMAL_RATE,
    WindowsVoiceInfo,
    _ENV_RATE,
    _ENV_TEXT,
    _ENV_VOICE,
    _normalize_culture,
    _normalize_gender,
    default_powershell_runner,
    validate_rate,
)

_ENV_SPEED = "STUDYGUARD_TTS_SPEED"

# id<TAB>display name<TAB>language tag<TAB>gender
_DISCOVER_SCRIPT = r"""
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media, ContentType=WindowsRuntime]
foreach ($voice in [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices) {
    $gender = ""
    try { $gender = [string]$voice.Gender } catch { $gender = "" }
    Write-Output ($voice.Id + [char]9 + $voice.DisplayName + [char]9 + $voice.Language + [char]9 + $gender)
}
exit 0
"""

# Fixed script. Text, voice id, and speed are environment values, never spliced in.
_SPEAK_SCRIPT = r"""
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq "AsTask" -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq "IAsyncOperation``1"
})[0]
function Await-WinRT($operation, $resultType) {
    $method = $asTaskGeneric.MakeGenericMethod($resultType)
    $task = $method.Invoke($null, @($operation))
    if (-not $task.Wait(20000)) { exit 5 }
    if ($task.IsFaulted) { exit 1 }
    return $task.Result
}
$null = [Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media, ContentType=WindowsRuntime]
$null = [Windows.Media.SpeechSynthesis.SpeechSynthesisStream, Windows.Media, ContentType=WindowsRuntime]
$null = [Windows.Storage.Streams.DataReader, Windows.Storage.Streams, ContentType=WindowsRuntime]
$synth = $null
$stream = $null
$reader = $null
$player = $null
$memory = $null
try {
    $voiceId = [Environment]::GetEnvironmentVariable("STUDYGUARD_TTS_VOICE")
    $text = [Environment]::GetEnvironmentVariable("STUDYGUARD_TTS_TEXT")
    $speedRaw = [Environment]::GetEnvironmentVariable("STUDYGUARD_TTS_SPEED")
    if ([string]::IsNullOrEmpty($voiceId) -or $null -eq $text) { exit 2 }
    $millis = 0
    if (-not [int]::TryParse($speedRaw, [ref]$millis)) { exit 4 }
    if ($millis -lt 500 -or $millis -gt 1500) { exit 4 }
    $match = $null
    foreach ($voice in [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices) {
        if ($voice.Id -eq $voiceId) { $match = $voice; break }
    }
    if ($null -eq $match) { exit 3 }
    $synth = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::new()
    $synth.Voice = $match
    $synth.Options.SpeakingRate = $millis / 1000.0
    $stream = Await-WinRT ($synth.SynthesizeTextToStreamAsync($text)) ([Windows.Media.SpeechSynthesis.SpeechSynthesisStream])
    $size = [int]$stream.Size
    if ($size -le 44) { exit 1 }
    $reader = [Windows.Storage.Streams.DataReader]::new($stream.GetInputStreamAt(0))
    $loaded = Await-WinRT ($reader.LoadAsync([uint32]$size)) ([uint32])
    $bytes = New-Object byte[] $loaded
    $reader.ReadBytes($bytes)
    $memory = New-Object System.IO.MemoryStream(,$bytes)
    $player = New-Object System.Media.SoundPlayer($memory)
    $player.PlaySync()
    exit 0
} catch {
    exit 1
} finally {
    if ($null -ne $player) { $player.Dispose() }
    if ($null -ne $memory) { $memory.Dispose() }
    if ($null -ne $reader) { $reader.Dispose() }
    if ($null -ne $stream) { $stream.Dispose() }
    if ($null -ne $synth) { $synth.Dispose() }
}
"""


def winrt_speed_millis(rate: int) -> str:
    """Map the shared -10..10 rate onto a WinRT SpeakingRate in thousandths.

    0 is normal (1.00). -4 is slow (0.80). The result stays inside 500..1500.
    """
    chosen = validate_rate(rate)
    speed = 1.0 + (chosen * 0.05)
    if speed < 0.5:
        speed = 0.5
    if speed > 1.5:
        speed = 1.5
    return str(int(round(speed * 1000)))


def parse_winrt_discovery_output(raw: str) -> Tuple[WindowsVoiceInfo, ...]:
    """Parse id<TAB>name<TAB>culture<TAB>gender lines."""
    voices: List[WindowsVoiceInfo] = []
    for line in str(raw or "").splitlines():
        if "\t" not in line:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        voice_id, name, culture = parts[0].strip(), parts[1].strip(), parts[2].strip()
        gender = _normalize_gender(parts[3]) if len(parts) > 3 else ""
        if not voice_id or not name or not culture:
            continue
        culture = _normalize_culture(culture)
        language = culture.split("-")[0].lower()
        voices.append(
            WindowsVoiceInfo(
                name=name,
                culture=culture,
                language=language,
                gender=gender,
                provider="winrt",
                voice_id=voice_id,
            )
        )
    voices.sort(key=lambda item: (item.language, item.culture.lower(), item.name.lower()))
    return tuple(voices)


class WindowsWinRTProvider:
    """Speak with an already installed Windows.Media.SpeechSynthesis voice."""

    DISCOVER_TIMEOUT_SEC = 20.0
    SPEAK_TIMEOUT_SEC = 90.0

    def __init__(
        self,
        *,
        runner=None,
        voices: Optional[Sequence[WindowsVoiceInfo]] = None,
        platform: Optional[str] = None,
    ):
        self._runner = runner or default_powershell_runner
        self._platform = sys.platform if platform is None else platform
        self._voices: Optional[Tuple[WindowsVoiceInfo, ...]] = (
            tuple(voices) if voices is not None else None
        )

    def discover(self) -> Tuple[WindowsVoiceInfo, ...]:
        if self._voices is not None:
            return self._voices
        if self._platform != "win32":
            self._voices = ()
            return self._voices
        result = self._runner(_DISCOVER_SCRIPT, env=None, timeout=self.DISCOVER_TIMEOUT_SEC)
        if getattr(result, "returncode", 1) != 0:
            raise ListeningAudioError("Could not discover Windows media voices.")
        self._voices = parse_winrt_discovery_output(getattr(result, "stdout", "") or "")
        return self._voices

    def refresh(self) -> Tuple[WindowsVoiceInfo, ...]:
        self._voices = None
        return self.discover()

    def play(
        self,
        text: str,
        voice_id: str,
        rate: int = NORMAL_RATE,
    ) -> None:
        if self._platform != "win32":
            raise ListeningAudioError("Windows speech is only available on Windows.")
        spoken = str(text or "")
        ident = str(voice_id or "").strip()
        if not spoken.strip():
            raise ListeningAudioError("Nothing to speak.")
        if not ident:
            raise ListeningAudioError("No Windows text-to-speech voice is installed.")
        speed = winrt_speed_millis(rate)
        env = {
            _ENV_VOICE: ident,
            _ENV_TEXT: spoken,
            _ENV_RATE: str(validate_rate(rate)),
            _ENV_SPEED: speed,
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
        code = getattr(result, "returncode", 1)
        if code == 0:
            return
        if code == 3:
            raise ListeningAudioError("No Windows text-to-speech voice is installed.")
        if code == 5:
            raise ListeningAudioError("Speech playback timed out.")
        raise ListeningAudioError("Speech playback failed.")
