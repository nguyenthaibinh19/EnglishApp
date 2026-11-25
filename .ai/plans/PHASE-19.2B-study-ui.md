# Phase 19.2B study card

Branch `phase19.2b/study-session-ui`, based on the accepted Home trial `baf501351dc0b326df1a286ea64b5572bfa2f7bb`.

The Tkinter fallback `phase19.2a/ui-foundation-today` stays at `7c566027d393ae6753592b67a17c83ddb1b08c3d`. Neither branch is merged.

## Dependency

`customtkinter==5.2.2` and `darkdetect==0.8.0` are in `requirements.txt`. The license notice is `licenses/customtkinter.MIT.txt` (MIT, Copyright 2023 Tom Schimansky). Both PyInstaller specs collect CustomTkinter's package data and that notice. The window remains `tk.Tk` with one main loop.

## Study card

The vocabulary question uses one card: progress, a counter from the session target, the meaning, one answer field, Hint, Check, then Continue. Leave is shown when the screen is unlocked. Emergency exit is shown only while the lock is active. Manage vocabulary and Go to reading are not on this card. Voluntary sentence practice is a secondary action on the feedback card, not beside Check.

Later exercise kinds are named in `study_presentation.py` and are not built.

Grading, hint mastery, SRS, and attempt recording are unchanged. A second Enter does not record the same answer again.

## R1 corrections

Architect decision `APP_19D2B_STUDY_UI_CORRECTION_REQUIRED`. Review baseline `78d05275d06a462bd3ff79c4a00ce98cdb3b48ee`.

- The completion button uses its own command. Mouse click, Enter, Space, and the window close call the completion callback once. Leave on an unfinished session does not mark it complete.
- A wrong answer still opens the existing forced sentence screen after explicit Continue, when `FORCE_SENTENCE_ON_WRONG` is on and AI is configured. Exact and near answers do not. Skip, AI feedback, errors, and return to the quiz are the existing practice screen.
- The counter shows session-correct answers over the session target. A wrong answer does not advance it. A hinted exact answer or a near miss advances the session score and is still not mastery.
- Tab reaches Hint, Check, and Leave, and the focused control draws a visible border. A disabled Check ignores Enter, Space, and `invoke`.

## Tests

`tests/test_study_card_ui.py` and `tests/test_study_card_corrections.py` passed in separate Python processes. `tests/test_ctk_keyboard.py` passes in its own process. Running `test_study_card_ui.py` and `test_ctk_keyboard.py` in one pytest process fails: after the first root is destroyed, the next test's `focus_get()` is `None`. That is not a combined-suite pass. An earlier failure in the same situation was Tcl being unable to read `panedwindow.tcl`.

## Packaging evidence

An isolated staging executable was started before this correction. It included CustomTkinter's theme files and the MIT notice. Its bundled manifest names the parent commit `baf501351dc0b326df1a286ea64b5572bfa2f7bb`, not `78d05275d06a462bd3ff79c4a00ce98cdb3b48ee` and not this correction. That is preliminary packaging evidence, not verification of the exact source. Do not rebuild only to refresh the manifest. Exact source identity belongs to the next release build.

Windows display scaling above 100% was not changed. A 150% `set_widget_scaling` probe is not a DPI check.
