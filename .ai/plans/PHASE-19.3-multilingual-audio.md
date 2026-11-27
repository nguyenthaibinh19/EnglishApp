# Phase 19.3 multilingual audio

Branch `phase19.3/multilingual-audio`, created from main `5f8f3c0ad175a82ad61866e23eac64af1bfe47ed` (PR #31). Not merged.

## What speaks

`WindowsSpeechProvider` is the shared playback path. System.Speech remains the preferred engine. WinRT speaks a language only when System.Speech cannot, or when that WinRT voice was explicitly saved. Learner text, the voice id, and the rate travel as environment data. The PowerShell scripts stay fixed source.

Normal rate is 0. Slow rate is -4. Both are inside the validated range -10..10. A removed voice falls back to another voice of the same language. A voice from another language is refused. There is no online fallback.

The selected name is stored in `settings.json` under `device_voices`, per language, on this PC. `ACCOUNT_PREF_KEYS` is unchanged, and saving a voice does not mark account preferences dirty.

Voice Settings opens from Study Settings. Discovery and playback run off the Tk thread. One clip plays at a time. Closing the window or switching language drops a stale callback.

Listening keeps Play, Slow, and Replay. A missing voice opens the existing unavailable screen with Continue, so a locked session is not trapped. Grading, completion, and SRS are unchanged.

Vocabulary pronunciation uses the same provider where the word is already visible: the library row, the word detail (word and example), and study feedback after the answer. The hear control is hidden while the learner is still answering.

## R2 WinRT speech — 2026-11-27

Review baseline `9cefcf3831f12f2cf080fdc1c0fcc92ce3f09963`.

`WindowsSpeechProvider` lists System.Speech and Windows.Media.SpeechSynthesis together. A saved System.Speech name still selects that voice. When nothing is saved, System.Speech is used if it has a voice for the language. WinRT fills the same language only when System.Speech cannot. An explicit WinRT choice is stored as `winrt:` plus the voice id returned by Windows. That id is data. The app does not read or write the registry.

There is no new Python dependency. Synthesis runs in the existing PowerShell host. PyInstaller does not need a new hidden import or a speech wheel. No executable was rebuilt.

Audible playback through this provider, with the fixed preview sentence:

| Language | Voice used | Result |
| --- | --- | --- |
| Dutch | Microsoft Frank, nl-NL, Male, WinRT | Normal 4.40 s, slow 5.32 s. Same voice and text. |
| Portuguese | Microsoft Helia, pt-PT, Female, WinRT | Normal 4.47 s, slow 5.31 s. Same voice and text. |
| English | Microsoft David Desktop, en-US, Male, System.Speech | Normal 4.18 s. |
| Spanish | Microsoft Helena Desktop, es-ES, Female, System.Speech | Normal 4.22 s. |
| German | Microsoft Hedda Desktop, de-DE, Female, System.Speech | Normal 4.64 s. |
| French | none | Missing-voice path. Not played. |
| Italian | none | Missing-voice path. Not played. |

A Dutch WinRT token requested for English resolved to David, not Frank.

Voice Settings re-enables preview after another window releases the shared playback slot. The menu selection and playback use the same saved token.

## R1 corrections — 2026-11-27

Review baseline `17a96921c743cc688991bccfc29f927838b52783`.

Listening now takes the same playback slot as Voice Settings, the vocabulary library, word detail, and study feedback. A second window gets a busy message instead of a second clip. Callbacks are checked again at delivery against the window, the language, and the exercise that started them. Advancing a study card drops a late error onto the next question. Discovery failure does not call `voices_for()` on the Tk thread. Installation guidance names the selected language.

## Voice inventory on this PC — 2026-11-27

System.Speech, played with the fixed preview sentence. Normal rate 0 and slow rate -4 used the same voice and the same text. These timings are audible playback, not mocked tests.

| Language | System.Speech | Audible result |
| --- | --- | --- |
| English | Microsoft David Desktop, en-US, Male; Microsoft Zira Desktop, en-US, Female | David normal 4.39 s, slow 6.11 s. Saved selection Zira normal 4.09 s, slow 5.95 s. |
| Spanish | Microsoft Helena Desktop, es-ES, Female | Normal 4.33 s, slow 6.24 s. |
| German | Microsoft Hedda Desktop, de-DE, Female | Normal 4.75 s, slow 6.88 s. |
| Dutch | none | Not played. A request that names David is refused. |
| French | none | Not played. |
| Italian | none | Not played. |
| Portuguese | none | Not played. |

`Windows.Media.SpeechSynthesis` on the same PC also lists Microsoft Frank, nl-NL, and Microsoft Helia, pt-PT, plus extra Spanish, German, and English voices. Those WinRT voices do not appear in System.Speech, so the app cannot play them. Dutch is installed for WinRT and remains unavailable to LanguageGuard. French and Italian are absent from both catalogs.

The saved voice name is what Listening, the vocabulary surfaces, and study feedback pass into playback. Zira was resolved and played when English was saved as Zira, rather than the alphabetical default David.

## Future local neural speech — not implemented

`Windows.Media.SpeechSynthesis` is the smallest next local provider. It is offline, uses voices Windows already installed, and adds no model files to the package. On this PC it is the only catalog that can see Dutch and Portuguese. A separate review would put it behind the existing provider seam. It is not a cloud service.

Piper is the practical offline neural alternative if Windows voices stay split. The archived `rhasspy/piper` engine was MIT. The active `piper-tts` package and `OHF-Voice/piper1-gpl` are GPL-3.0. The `rhasspy/piper-voices` files are MIT and include Dutch, English, Spanish, French, German, Italian, and Portuguese. A medium voice is about 63 MB. One medium voice for each of the seven languages is on the order of 440 MB, plus an ONNX runtime. That size and the GPL engine are the packaging constraints. This correction does not add Piper.

## Earlier probe — 2026-11-25

This inventory is historical. The 2026-11-27 table above is the current one.

System.Speech, read by the app probe:

| Language | System.Speech voice | Audible playback |
| --- | --- | --- |
| English | Microsoft David Desktop (en-US, Male); Microsoft Zira Desktop (en-US, Female) | Yes. Normal 4.55 s, slow 6.07 s, on the fixed English preview sentence. |
| Dutch | none | Not played. A Dutch request that names David is refused. |
| Spanish | none | Not played. |
| French | none | Not played. |
| German | none | Not played. |
| Italian | none | Not played. |
| Portuguese | none | Not played. |

Windows user languages on this PC are en-US and ja. Japanese is not a study language and is not used as a fallback. `Windows.Media.SpeechSynthesis.AllVoices` returned an empty list. A locale listed in `SPEECH_LOCALE_PREFERENCES` is not an operational voice.

## Owner action still open

Spanish and German now play through System.Speech. Dutch does not. Microsoft Frank, nl-NL, is visible to Windows.Media.SpeechSynthesis and invisible to System.Speech. Refresh voices cannot select Frank. The same split hides Microsoft Helia, pt-PT. French and Italian are not in either catalog.

The app will not install a language pack, change the display language, or edit the registry. A further System.Speech download for Dutch (Netherlands), French (France), Italian (Italy), or Portuguese (Portugal) is the Owner's choice. If Windows asks for an administrator, that choice belongs to the Owner. Until System.Speech lists the voice, LanguageGuard reports it as missing.

## Carried limits

A second `Tk()` in the same process, after the first root is destroyed, can leave `focus_get()` as `None` or fail to read `panedwindow.tcl`. GUI tests were run in separate processes. That is not a combined-suite pass.

The earlier frozen staging executable included CustomTkinter assets. Its manifest names parent `baf501351dc0b326df1a286ea64b5572bfa2f7bb`, not `fd18a1d` and not this branch. That remains preliminary packaging evidence. This phase did not rebuild or publish an executable.

Windows display scaling above 100% was not measured. A 150% widget-scaling probe is not a DPI check.

## Tests

Injected providers cover the shared playback slot, a stale exercise callback, missing-voice feedback, a catalog read that does not discover, per-language guidance, the saved voice name on Listening, vocabulary, and study feedback, rate bounds, and slow or replay playback that does not complete a listening session twice. Those tests do not prove the speakers made sound. The audible results are in the 2026-11-27 table.
