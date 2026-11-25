# Phase 19.3 multilingual audio

Branch `phase19.3/multilingual-audio`, created from main `5f8f3c0ad175a82ad61866e23eac64af1bfe47ed` (PR #31). Not merged.

## What speaks

`WindowsLocalTTSProvider` remains the only playback path. Learner text, the voice name, and the rate travel as environment data. The PowerShell scripts stay fixed source.

Normal rate is 0. Slow rate is -4. Both are inside the validated range -10..10. A removed voice falls back to another voice of the same language. A voice from another language is refused. There is no online fallback.

The selected name is stored in `settings.json` under `device_voices`, per language, on this PC. `ACCOUNT_PREF_KEYS` is unchanged, and saving a voice does not mark account preferences dirty.

Voice Settings opens from Study Settings. Discovery and playback run off the Tk thread. One clip plays at a time. Closing the window or switching language drops a stale callback.

Listening keeps Play, Slow, and Replay. A missing voice opens the existing unavailable screen with Continue, so a locked session is not trapped. Grading, completion, and SRS are unchanged.

Vocabulary pronunciation uses the same provider where the word is already visible: the library row, the word detail (word and example), and study feedback after the answer. The hear control is hidden while the learner is still answering.

## Voice inventory on this PC — 2026-11-25

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

## Owner install, not performed by the app

Settings - Time & language - Language & region - Add a language. Add Dutch (Netherlands) and Spanish (Spain). Include Text-to-speech if Windows offers that checkbox. Do not make either language the display language. Open the language menu - Language options - Speech - Download. Then LanguageGuard - Study settings - Voices - Refresh voices.

If Windows asks for an administrator, that choice belongs to the Owner. The app does not request elevation, does not edit the registry, and does not change the display language.

If those packs install and System.Speech still cannot select the voice, the next review should consider `Windows.Media.SpeechSynthesis` as a local provider. It is not a substitute on this PC today, because its catalog was empty. Do not add a paid speech service.

## Carried limits

A second `Tk()` in the same process, after the first root is destroyed, can leave `focus_get()` as `None` or fail to read `panedwindow.tcl`. GUI tests were run in separate processes. That is not a combined-suite pass.

The earlier frozen staging executable included CustomTkinter assets. Its manifest names parent `baf501351dc0b326df1a286ea64b5572bfa2f7bb`, not `fd18a1d` and not this branch. That remains preliminary packaging evidence. This phase did not rebuild or publish an executable.

Windows display scaling above 100% was not measured. A 150% widget-scaling probe is not a DPI check.

## Tests

Injected providers cover voice selection, rate bounds, a missing language, a removed voice, device-local preferences staying out of account sync, and slow or replay playback that does not complete a listening session twice. Those tests do not prove the speakers made sound. The audible result is the English timing above.
