# Phase 19.2B study card

Branch `phase19.2b/study-session-ui`, based on the accepted Home trial `baf501351dc0b326df1a286ea64b5572bfa2f7bb`.

The Tkinter fallback `phase19.2a/ui-foundation-today` stays at `7c566027d393ae6753592b67a17c83ddb1b08c3d`. Neither branch is merged.

## Dependency

`customtkinter==5.2.2` and `darkdetect==0.8.0` are in `requirements.txt`. The license notice is `licenses/customtkinter.MIT.txt` (MIT, Copyright 2023 Tom Schimansky). Both PyInstaller specs collect CustomTkinter's package data and that notice. The window remains `tk.Tk` with one main loop.

## Study card

The vocabulary question uses one card: progress, a counter from the session target, the meaning, one answer field, Hint, Check, then Continue. Leave is shown when the screen is unlocked. Emergency exit is shown only while the lock is active. Manage vocabulary, sentence writing, and Go to reading are not on this card. Sentence practice and the word manager remain in the module for their existing entry points.

Later exercise kinds are named in `study_presentation.py` and are not built.

Grading, hint mastery, SRS, and attempt recording are unchanged. A second Enter does not record the same answer again.
