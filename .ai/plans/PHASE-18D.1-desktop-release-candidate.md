# Phase 18D.1 — Desktop release candidate

Status: **incident reconciled and contained. Release-security review is ready.** Public release remains blocked. Containment baseline: `5bd5791c364f283e163d87e175f9ee5abe525c23`.  
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
| No production auto-update prompt | Pass. No updater dialog. RC smoke does not call the updater. No production updater process was running |
| Installed EXE and Startup shortcut unchanged | Pass, rechecked after logout. EXE `36,050,859` bytes, `2026-11-08T16:18:07Z`, SHA-256 `bbcd5e9a8bb22c72acdf863c94b68f6dbb7cc76717b737c6b93b0e50b28d58c3`. Shortcut `1,273` bytes, `2026-11-08T17:16:53Z` |
| Candidate EXE and ZIP unchanged | Pass. The hashes in the table above match the files after the smoke |
| Signed-in identity | Pass. Home showed `syncpilot_18c4p`, user id 3 |
| Effective data root | Pass for this process. Settings and `accounts\3\account_study.db` are under `.local\data\18d1-v1.5.0-rc`. This process started at `2026-11-24T13:09:26Z` |
| Home Dashboard and Dutch | Pass. Header `Language Guard — PRODUCTION BACKEND`, language `Tiếng Hà Lan`, vocabulary count `2 mục` while signed in |
| Vocabulary download | Pass in the isolated account database. `syncprobe` / `lab-marker-a` revision 4, and the existing `groot` / `big` revision 1. The vocabulary list window was not opened |
| Two attempts and SRS | Pass. Sequences 1 and 2, both exact. Both SRS rows are seen 1, correct 1, wrong 0, streak 1, interval 1 day, state version 1. Outbox 0, conflicts 0, caught up |
| Cloud Sync reaches Synced | Pass. Home label `Cloud Sync: Synced — Máy chủ đã nhận và client đã bắt kịp.` |
| Close and reopen | Pass. The same EXE was closed with `WM_CLOSE` and opened again with the same isolated environment. No rebuild |
| Persistence | Pass. After reopen, the same account, the same device-id SHA-256 prefix `4a6b88fefe82e9c1`, the same two vocabulary rows, the same two attempts, and the same SRS rows |
| Tk callback error | No error dialog on the signed-in home, the reopen, or the logout screen. The windowed EXE has no console log |
| Logout keeps the local database | Pass. The confirmation dialog title was `Đăng xuất`. After the affirmative answer, settings have no token, username, or user id. The home shows `Khách / Chưa đăng nhập` and `Đăng nhập`. `accounts\3\account_study.db` remains, `118,784` bytes, with the same two vocabulary rows, two attempts, and two SRS rows. Logged-out Home then shows the local Dutch library, not the account store |
| Real RC account database untouched | **Fail.** See below |
| Recovery files untouched | Pass. `LanguageGuard-Recovery\vocab-114-20261119-232144` is still `2026-11-19T23:21:44Z` |

The candidate was not rebuilt. No new quiz answer was submitted. The session token was not copied.

## Protected learner database

`%APPDATA%\langstudyguard-rc\accounts\1\account_study.db` is no longer the untouched snapshot. It is now `221,184` bytes, last write `2026-11-24T13:04:32Z`. Integrity is ok. It contains 115 vocabulary rows (114 learner rows plus the existing `groot` row), 6 local attempts from `2026-11-22`, 92 acknowledged `vocab_put` rows, 23 still-pending `vocab_put` rows, and 6 pending progress rows. The acknowledgements were written from `2026-11-24T13:04:21Z` through `13:04:32Z`.

That write is earlier than this isolated process, which started at `2026-11-24T13:09:26Z`. The isolated directory has no file written at `13:04`. The real RC `settings.json` is still the `2026-11-22` account id 1 session. Recovery files were not opened.

Production `study_sync.db` was also rewritten at `2026-11-24T13:04:40Z` and is now `151,552` bytes. `sync_http.py` is still `aa88f693764912f589a5945d7b3f154b587363311130b01295127cb600ddd5d1`. `language-guard.service` is active and its start time is still `2026-11-23T16:43:33Z`. `language-guard-sync-backup.timer` is still disabled and inactive. This check did not restart the service, enable the timer, or edit server files. The sync database change itself is a server-record change and was not reversed.

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

## Public-release gates

These remain explicit gates. None is cleared by this smoke.

- The already-built v1.5.0 candidate was not rebuilt. It still contains the synthetic emergency password and must not be published.
- Source packaging no longer writes an emergency password. The local credential is Phase 18D.2A. `bundle_secrets.py` keeps the account-server URL only.
- The repository `sync_http.py` correction remains undeployed. Source SHA-256 `3de5c413064240ff8036df9c314006201c302be32003cbeb76db502b2612ca6d`. Production remains `aa88f693764912f589a5945d7b3f154b587363311130b01295127cb600ddd5d1`.
- The recurring Sync backup timer remains disabled.
- The final public ZIP must be named `langstudyguard.zip` and must contain `langstudyguard.exe`. This private ZIP contains `langstudyguard-rc.exe`.

`APP_18D1_DESKTOP_RELEASE_CANDIDATE_READY_FOR_REVIEW` was not returned. The isolated signed-in smoke passed, and the protected account id 1 database did not stay untouched.

## Data incident reconciliation

No running process had `%APPDATA%\langstudyguard-rc\accounts\1\account_study.db` open, so no process was closed. The installed Startup shortcut was not changed. The candidate was not launched again and was not rebuilt.

The protected database did not change during preservation. Its size stayed `221,184` bytes and its mtime stayed `2026-11-24T13:04:32.935533Z`. A consistent SQLite backup is `D:\EnglishApp\.local\backups\18d1-data-incident\account-1-20261124T141119Z.db`, `221,184` bytes, SHA-256 `75fff1bfd23cc7c6a7e95c87ba848fade76ea1c555fa6b1f4fb91e1878e6a7cb`, integrity `ok`. The 2026-11-19 recovery copy was not overwritten. Its guest vocabulary SHA-256 is still `ca387ab1bf13a95dd39dd033b0034dfc498fd4fc0e7450ea260161a75d805946`, and the pre-import database SHA-256 is still `9efe5eb7cab7b5f2347a6dda13112809e6cd6493268ada32b421349c8aecb72c`.

One production backup was published with the existing online backup procedure and then verified: `study-sync-20261124-141131-698592.db`, `151,552` bytes, mode `0600`, SHA-256 `fc76ffe479424deb77150e96d461bfa7710220c4ced3e244a6bd2416f32bf2d9`, integrity `ok`, schema 3. The verifier returned `study_sync restore verification verified`. `language-guard.service` still started at `2026-11-23T16:43:33Z`. The sync backup timer remains disabled and inactive.

### Counts

The recovery source has 114 vocabulary ids. The pre-import account database had 0 vocabulary entities. The current protected database has all 114, with no lexical mismatch and no deleted row. It also has one extra entity, id `242e5e4c-4345-447c-a777-44df6132b2da`, revision 0, last updated `2026-11-22T10:40:48Z`. That entity is not in the recovery source and was not uploaded. There are no duplicate logical entities and no sync conflicts.

The 92 acknowledged vocabulary operations are 92 distinct ids. All 92 are among the original 114. Each one is present on the production server for account id 1 at the same revision and the same lexical hash, and none is deleted. The server has 92 vocabulary entities, 92 vocabulary change rows, 0 learning attempts, and 0 SRS rows for account id 1. No acknowledged id is missing, and the server has no account id 1 vocabulary outside those 92.

Twenty-two of the original 114 are still pending locally. All 22 have their vocabulary bodies in the outbox, still exist locally, and are absent from the server. The extra Nov 22 entity is the 23rd pending vocabulary operation and is also absent from the server. Those 23 operations remain recoverable. They were not marked acknowledged.

Six local learning attempts from `2026-11-22` match six pending progress events by event id. None of those attempts is for the extra entity. Local SRS for those six is provisional only. The server has accepted none of them. They remain recoverable. No new stored learning attempt was created by this incident. Three `/api/grade` requests were logged between `13:04:29Z` and `13:09:42Z`; account id 1 still has no server attempt rows.

All original learner vocabulary is preserved locally, and the uploaded subset matches the server. The partial synchronization can be continued later from the protected database. It must not be continued from the isolated copy described below, because that copy has the 92 downloaded entities and does not have the pending operations.

### Origin

Confirmed facts: the acknowledgements were written into this computer's protected database from `13:04:21Z` through `13:04:32Z`, and the server entities were updated at `13:04:40Z`. Windows records a shell launch of `D:\EnglishApp\.local\builds\18d1-v1.5.0-rc\langstudyguard-rc.exe` at `13:04:16.766Z`. The older `dist-rc` executable's last recorded launch is `2026-11-22T10:40:20Z`. The installed production executable's last recorded launch is `2026-11-08T17:08:23Z`. The same-machine lab databases were last written at `11:29Z`. The protected `settings.json` was not rewritten, so the uploading client used the account id 1 session already stored on `2026-11-22`. No retained command line identifies the parent of the `13:04:16Z` launch.

Hypothesis, not a confirmed command: that launch used the default RC data root because `LG_DATA_DIR` was not set. An RC-named executable did that by design, and the stored session would start sync without a new login. A separate window of the same executable was signed in as user 3 at `13:06Z`, so the upload and the isolated smoke were not the same visible session.

This upload was not produced by another computer. Another computer cannot write this local outbox file. There is no evidence for a different local executable.

At `14:07:35Z` the still-running candidate, using the isolated data root, logged in as account id 1 and issued one preferences put. It then polled. That preferences put is a separate server write from the vocabulary upload. It was not reversed. Account id 1 vocabulary on the server was not changed by it.

## Containment

On 2026-11-24 the isolated v1.5.0 candidate was no longer running. Its last writes to the isolated settings file and to `.local\data\18d1-v1.5.0-rc\accounts\1\account_study.db` were `2026-11-24T14:50:43Z`. No `langstudyguard` process was present, so nothing was closed and the candidate was not launched again.

The isolated account id 1 database remains incident evidence: `147,456` bytes, 92 vocabulary entities, 0 deleted, 0 attempts, and an empty outbox. It was not copied or merged into the protected database. The isolated settings file still holds the account id 1 session. That session was not cleared and must not be used to resume synchronization.

The protected database is unchanged: `221,184` bytes, mtime `2026-11-24T13:04:32.935533Z`, 115 vocabulary entities, 0 deleted, 92 acknowledged vocabulary operations, 23 pending vocabulary operations, 6 pending progress events, 6 learning attempts, 0 confirmed progress rows, and 0 conflicts. The installed production EXE and Startup shortcut were not changed.

Future RC smoke now fails closed in source. `config.data_dir()` requires `LG_DATA_DIR` when RC smoke is active and refuses the protected RC AppData directory, production AppData, the production install directory, and `LanguageGuard-Recovery`, including overlapping or redirected paths. The check runs before settings are read and `main()` returns before install and before Sync Engine start. A genuine production EXE still resolves `%APPDATA%\langstudyguard` without `LG_DATA_DIR`.

`tests/test_rc_smoke_isolation.py` and `tests/test_app_environment_isolation.py`: 31 passed. The tests use temporary directories only. The guarded launcher `.local\labs\18d1\launch_rc_smoke.py` refused the four protected directories, the incident root, and a path outside the workspace, and accepted an unused workspace path without creating it or starting the EXE. The v1.5.0 candidate was not rebuilt, so that binary gets the check only through the launcher until a later build.

## Emergency-exit security decision

This is a recommendation. It is not implemented.

The bundled password is read in two places. A source run takes `EMERGENCY_PASSWORD` from the developer environment in `config.reload()`. A frozen run reads `bundled_secrets.json` through `config.bundled_password()`. `bundle_secrets.py` copies that environment value into the JSON file, and the build packs the file into the executable. `config.is_ready()` returns false when the password is empty, so a frozen build without one cannot finish setup.

Emergency Exit is offline. `LockScreen.confirm_emergency_exit` pauses screen-lock enforcement and calls `confirm_developer_exit`, which compares the typed value with `config.EMERGENCY_PASSWORD` using `hmac.compare_digest`. No network call is involved. Account save and clear remove `emergency_password` from settings, so the secret is not stored in AppData.

An upgrade replaces the installed EXE and leaves the AppData session and databases in place. The Startup shortcut still launches with `--lock`. The password that opens Emergency Exit is the one inside the EXE that is running. Replacing that EXE with a build that embeds a different shared password changes the password without a local acknowledgement.

The developer password can be extracted from a distributed executable. It is stored as plaintext JSON inside the package, so every copy of that build shares the same secret.

Recommended replacement, one step, compatible with the current release: keep accepting the bundled secret on an existing installation until that installation has acknowledged a local secret. On first run of a new public build, generate a per-user secret, protect it with Windows DPAPI for the current Windows user, and show it once. Do not create the Startup `--lock` shortcut until that acknowledgement. Emergency Exit stays a local comparison against the acknowledged secret, so it still works offline. The same Windows user can reveal the DPAPI-protected secret again without a server. Until acknowledgement, the previous bundled password remains valid, so an upgrade cannot lock the owner out. A new public build should stop embedding a shared password once that local path exists. Do not implement this in the current candidate.
