# Phase 18D.1 — Desktop release candidate

Status: **built, frozen smoke waiting for private sign-in.** The ready tag was not returned.  
Date: 2026-11-24  
Proposed release: v1.5.0 — Account Cloud Sync Update  
Packaged source: `29292749da54b0035833321a80e2776007b6ee8e`  
Accepted pilot baseline: `54f452da36211e419ef51a105009c1428b2525a9`

No GitHub Release, tag, or publication. The installed production EXE was not replaced.

## Candidate

| File | SHA-256 |
|------|---------|
| `D:\EnglishApp\.local\builds\18d1-v1.5.0-rc\langstudyguard-rc.exe` | `284f96460279e5812cac74fcefe2c2f407ea98d73502e255a02cf5ce28ffd3f5` |
| `D:\EnglishApp\.local\builds\18d1-v1.5.0-rc\langstudyguard-rc.zip` | `348cbe7feb92c1831f9a5cdf6809f5abfcfc795d4fcbbc16f19e402a45b4f226` |

The embedded manifest is channel `production`, version `1.5.0`, commit `29292749da54b0035833321a80e2776007b6ee8e`. The ZIP entry is `langstudyguard-rc.exe`. PyInstaller 6.22.3, Python 3.13.13. Dependency notes are in `dependencies.json` beside the EXE. The repository `dist\` and `dist-rc\` trees were not used.

The bundled account URL is `https://langstudyguard.com`. The bundled emergency password is the synthetic placeholder `18d1-rc-placeholder-not-for-publication`. It is not the owner password and is not suitable for a public release. The existing bundling path still reads `EMERGENCY_PASSWORD` from a developer `.env`. That mechanism needs a separate release security decision before publication. No API key, account token, OAuth token, SSH credential, real database, or developer `.env` is in the archive.

## Frozen smoke

Launched with `LG_DATA_DIR=D:\EnglishApp\.local\data\18d1-v1.5.0-rc` and `LG_RC_SMOKE=1`. The visible window title is `Language Guard — PRODUCTION BACKEND · RC TEST DATA`. The first screen is the account login form. Starter vocabulary was created only under that data directory.

| Check | Result |
|-------|--------|
| Starts without Python source | Pass |
| Production HTTPS identity, RC data banner | Pass |
| No production auto-update prompt | Pass. RC smoke does not call the updater |
| Installed EXE and Startup shortcut unchanged | Pass. EXE `36,050,859` bytes, SHA-256 `bbcd5e9a8bb22c72acdf863c94b68f6dbb7cc76717b737c6b93b0e50b28d58c3`, shortcut `1,273` bytes, `2026-11-08T17:16:53Z` |
| Real RC account database untouched | Pass. `196,608` bytes, `2026-11-22T11:06:28Z` |
| Home Dashboard after sign-in | Not run |
| Language selection | Not run |
| Login, logout, vocabulary sync, Progress and SRS download | Not run. The password stays with the Owner |
| Signed-in close and reopen | Not run |
| Tk callback error after sign-in | Not run |

## Backend

Production `sync_http.py` was read only. Its SHA-256 is still `aa88f693764912f589a5945d7b3f154b587363311130b01295127cb600ddd5d1`. The service is active. `language-guard-sync-backup.timer` is disabled and inactive. The repository file is `3de5c413064240ff8036df9c314006201c302be32003cbeb76db502b2612ca6d` and was not deployed.

The new desktop client uses the same seven sync routes. An authenticated request is read by the current server, so the accepted signed-in sync does not require the new body-drain. That drain is required for clean Windows handling of an early 401 or sync-disabled 404. Those answers currently return before the body is read and can surface as WinError 10053. The client timeout is 15 seconds. The undeployed server change reads at most 32,768 bytes before those early answers and still refuses a larger body without reading it.

If a later approval deploys it: copy only the LF `sync_http.py`, restart `language-guard.service`, and keep the sync flag on. Roll back by restoring the `aa88f693` file. No schema change. This task did not deploy it.

Before real-account migration or wider distribution, enable the already installed sync backup timer only under a separate approval, and keep one verified backup. The timer stays disabled now. Phase 18B.9 stays paused.

## Release notes for v1.5.0

Account Cloud Sync is included for a signed-in learner: vocabulary, learning progress, and explicit conflict handling. The desktop build is 1.5.0.

The public update asset must be named `langstudyguard.zip` and must contain `langstudyguard.exe`. The updater selects that ZIP name first and extracts that EXE name. `langstudyguard-rc.zip` is the private candidate. Publishing it as the update asset would not satisfy the updater.

Upgrade replaces `%LOCALAPPDATA%\langstudyguard\langstudyguard.exe` only after a separate acceptance. Rollback restores the previous EXE, whose current hash is `bbcd5e9a8bb22c72acdf863c94b68f6dbb7cc76717b737c6b93b0e50b28d58c3`. First install copies into that folder and creates `langstudyguard.lnk` with `--lock` only when both are absent. This candidate is named `langstudyguard-rc.exe`, so it runs in place and does not install or change Startup.

The executable is unsigned. Windows SmartScreen can warn. No public release was created.

Remaining blockers: Owner sign-in on the open candidate, the emergency-password publication decision, the optional server body-drain deploy, and the sync backup timer approval before real-account migration.
