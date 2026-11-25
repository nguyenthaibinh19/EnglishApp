# Phase 19.2A CustomTkinter visual trial

Branch `phase19.2a/customtkinter-visual-trial`, based on functional checkpoint `7c566027d393ae6753592b67a17c83ddb1b08c3d`.

The Tkinter branch `phase19.2a/ui-foundation-today` stays at that checkpoint and is the fallback. Neither branch is merged.

## Scope

CustomTkinter draws the Home shell only. The window is still `tk.Tk`. Study launch, Settings, account, vocabulary, progress, mistake book, conflict dialogs, and ScreenGuard stay on Tk and ttk.

## Dependency

Pinned in `requirements-ctk-trial.txt`:

- `customtkinter==5.2.2`
- `darkdetect==0.8.0`

License file inside the 5.2.2 wheel: MIT, Copyright 2023 Tom Schimansky. PyPI's short license field also says CC0; the shipped `LICENSE` text is MIT.

## Packaging

Not frozen in this trial. A future PyInstaller build would need `customtkinter/assets` (themes, fonts, icons) collected as data. The current specs do not do that. Frozen compatibility is not claimed.

## DPI

`CTk()` would call `SetProcessDpiAwareness` and later `block_update_dimensions_event` on the root. This trial does not create a `CTk` root, and it calls `deactivate_automatic_dpi_awareness()` so widget geometry stays at 1× inside the existing 560×600 client. CustomTkinter still schedules its scaling check on the same Tk `after` loop. That is not a second main loop.
