# ADR-023 Windows installation safety

Status: **Accepted — source implemented in the `fix/windows-install-safety` worktree; not committed.**

This decision is the uncommitted `app/install.py` behavior and `tests/test_install.py`. It is not on `main` until a later, separate Git operation. It does not authorize a GitHub Release, a VPS change, or Cloud Sync.

Baseline before the patch: `09556f909b0ce6d8dcc27816800ef6bcd308f1ab`.

## Context

The frozen Windows app copies itself to `%LOCALAPPDATA%\langstudyguard\langstudyguard.exe` on first install and creates one user Startup shortcut whose arguments are `--lock`.

The previous installer used `shutil.copy2`. That preserves the source timestamp, so an older executable launched from another directory could replace a newer installed file and leave the old timestamp in place. The child then rewrote the Startup shortcut. A launch from the repository `dist` tree did that on 2026-11-06.

## Decision

- A non-frozen source run does not copy, seed, or touch Startup.
- When the running frozen executable is already the installed path, seed missing sample vocabularies only. Do not copy and do not call Startup registration.
- When the installed file already exists and this executable is a different path, stop. Do not overwrite the installed file, do not start it, and do not create or change Startup. The refusal message stays non-sensitive.
- First install runs only when the destination file is absent and `langstudyguard.lnk` is absent. The copy is an exclusive create with a size check and fsync.
- Startup registration creates `langstudyguard.lnk` only when that name is absent. It does not delete `Dutch Guard.lnk` or any unrelated shortcut. The shortcut target is the installed executable, the arguments are `--lock`, and the working directory is the install directory.
- If first-install launch fails, remove only the executable and Startup link created by that attempt. Leave a pre-existing shortcut byte-for-byte.
- A successful process spawn does not prove the child finished initializing. If the child exits after spawn, the new executable and shortcut can remain. That limitation is accepted for this decision.

The in-app updater is unchanged. It can still replace the installed executable when the learner accepts an update from the installed app. An external copy cannot take that path.

## Local binary evidence (2026-11-08)

These hashes were checked in the authorized host procedure. This ADR does not launch the app.

| Location | SHA-256 |
|---|---|
| Isolated build, official `dist\langstudyguard.exe`, ZIP entry `langstudyguard.exe`, and the installed executable | `bbcd5e9a8bb22c72acdf863c94b68f6dbb7cc76717b737c6b93b0e50b28d58c3` |

The user confirmed a normal Home Dashboard open and close. That launch did not create a Startup shortcut. Afterward, one new user Startup shortcut was created with target `%LOCALAPPDATA%\langstudyguard\langstudyguard.exe`, arguments `--lock`, and that install directory as the working directory. The shortcut was not launched. Emergency Exit under `--lock` has not been confirmed on this build.

## Consequences

- Windows installation safety is not closed. Source integration, automatic Startup `--lock`, and Emergency Exit under `--lock` remain separate decisions.
- Future installer edits must keep the tests in `tests/test_install.py` aligned with this decision.
- See [current_state.md](../current_state.md) and [invariants.md](../invariants.md).
