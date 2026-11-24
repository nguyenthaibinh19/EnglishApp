# Phase 18D.3 — Final v1.5.0 release preparation

Status: the emergency-code choice is in the rebuilt v1.5.0 artifact. Frozen sign-in is open and waiting for the synthetic account password. Publication and the installed-app upgrade are held at that sign-in. Baseline `154bf03c6856667cf1322cfe4e6f31996e05e09f`. No public release was created and no release tag was pushed.

## Final artifacts

Built with `build_exe.bat` from the accepted main source. A leftover gitignored `build_manifest.json` would have stamped version 1.4.0, so that file was removed and the production build was run again. The published artifacts are the second build.

| File | Bytes | SHA-256 |
|---|---:|---|
| `D:\EnglishApp\.local\builds\18d3-v1.5.0-final\langstudyguard.exe` | 36,250,260 | `6954dbdadec226140ac35e55395ffda0c20a31b1ebaffde643c7edcd6d6ee1e9` |
| `D:\EnglishApp\.local\builds\18d3-v1.5.0-final\langstudyguard.zip` | 35,779,585 | `b6e73009b832b26d5119fec40d402b78335b628e7759d97d67b54ef1da15d3d0` |

The ZIP contains one entry, `langstudyguard.exe`, and that entry is the same size as the executable.

The previous candidate is archived at `D:\EnglishApp\.local\builds\18d3-v1.5.0-final\archive-2d01446\`. Its EXE SHA-256 remains `9d4e6ae49d4545e195fc12a7e9b7e4face9bb5165293d16f70781d475f1ae199`.

Embedded `build_manifest.json`: channel `production`, version `1.5.0`, commit `154bf03c6856667cf1322cfe4e6f31996e05e09f`, built `2026-11-24T19:03:08Z`. The packaged enrollment dialog offers "Set my own emergency code" and "Generate a secure random emergency code". A weak or empty chosen code is rejected before the current credential is replaced.

Embedded `bundled_secrets.json`: `account_server_url` is `https://langstudyguard.com`. It has no other key. The executable does not contain the old placeholder emergency password, `EMERGENCY_PASSWORD`, an `sk-` key, an SSH private key, or a SQLite database. The packaged bytecode includes `CryptProtectData`, `lock_allowed`, `disarm_lost_credential`, `allows_unlocked_leave`, `langstudyguard-rc`, and `LanguageGuard-Recovery`.

Build tools: Python 3.13.13, PyInstaller 6.22.3, altgraph 0.17.5, pefile 2024.8.26, packaging 26.0, setuptools 82.0.1.

Preserved without replacement:

| File | Bytes | SHA-256 |
|---|---:|---|
| Installed EXE | 36,050,859 | `bbcd5e9a8bb22c72acdf863c94b68f6dbb7cc76717b737c6b93b0e50b28d58c3` |
| Startup shortcut | 1,273 | `6e8100b7a9b1e4faa151c0ac9cfc8c4eff41f453cffe1311a1a243acb2b8a93e` |
| `D:\EnglishApp\dist\langstudyguard.exe` | 36,168,317 | `4a9a5ef52972f9560ee9db40374bcef6f54ccdebc20002cea480041e91327695` |
| v1.5.0 RC candidate | 36,228,757 | `284f96460279e5812cac74fcefe2c2f407ea98d73502e255a02cf5ce28ffd3f5` |

## Frozen smoke so far

The rebuilt EXE was started only through `D:\EnglishApp\.local\labs\18d1\launch_rc_smoke.py`, with a fresh data root `D:\EnglishApp\.local\data\18d3-release-smoke`. The window title is `Language Guard — PRODUCTION BACKEND · RC TEST DATA`. The sign-in form shows that banner. It is a small window, not a screen lock. No updater dialog appeared. The username `syncpilot_18c4p` is filled. The password field is empty.

The same EXE, with `LG_RC_SMOKE=1`, stopped before opening data for a missing root, production AppData, the protected RC AppData folder, the production install directory, and the recovery directory. The guarded launcher also refuses the 18D.1 incident root and production AppData. A direct launch at the incident root is not part of the guarded procedure. One such launch wrote `emergency_credential.json` there. That new file was removed. The incident account databases were not rewritten.

Not yet done on this binary: emergency-code enrollment, cancelled enrollment, credential persistence across restart, password login, logout, and the account id 3 vocabulary, attempt, and SRS download. Screen lock was not activated.

## Compatibility

The installed v1.4.0 updater and this build have the same bytecode for `parse_version`, `is_newer`, `_pick_asset`, and `_extract_exe_from_zip`. `is_newer("v1.5.0", "1.4.0")` is true. `_pick_asset` selects `langstudyguard.zip`. Extracting this ZIP in a temporary directory produced an EXE larger than 8 MB and left a sibling data file unchanged.

The updater replaces the installed executable path and does not call `install.prepare`. Learner data stays in the roaming data directory, so an upgrade or a rollback of the EXE does not replace that data. This task did not replace the installed EXE.

Clean full suite after the emergency-code choice, and before the production manifest was written: **978 passed, 24 skipped, 0 failed**.

## Backup observation

`language-guard-sync-backup.timer` is still enabled and active. `LastTriggerUSec` is empty. The next elapse remains `2026-11-25 04:47:46 UTC`. The verifier's next elapse remains `2026-11-25 07:00:00 UTC`. The first natural backup has not occurred. The timer was not changed and no manual backup was run for this task.

## Release notes

Language Guard 1.5.0 is a production-channel desktop build from `154bf03c6856667cf1322cfe4e6f31996e05e09f`. It talks to `https://langstudyguard.com`. Enrollment and Study Settings let the learner set their own emergency code or generate a random one. Screen lock stays off until that code is confirmed on that computer. Release packaging does not embed a shared emergency password. RC smoke refuses a missing or protected data root. Cloud Sync for the supervised pilot stays available. The recurring on-server Sync backup timer is enabled. Its first natural run is still pending.

Remaining limitations:

- The executable is unsigned. Windows SmartScreen can warn.
- The pilot is the approved synthetic account and the already accepted account id 1 records. Real-account migration is a separate operation.
- Google Drive off-box backup stays paused.
- Public API rate limits and storage quotas stay deferred.
- The first natural Sync backup has not been observed.
- The deployed Sync body timeout is an inactivity timeout, not an absolute total-body deadline.
- The 23 pending vocabulary operations and 6 pending progress events are still local.

## Publish after Owner approval

Do not run these steps until the frozen smoke is finished and the Owner approves publication.

1. Confirm the ZIP SHA-256 is still `b6e73009b832b26d5119fec40d402b78335b628e7759d97d67b54ef1da15d3d0`.
2. From the accepted commit, create a GitHub Release titled `v1.5.0`. The tag is created only with that approval.
3. Upload `langstudyguard.zip` as an asset with that exact name. The updater selects that name and extracts `langstudyguard.exe`.
4. Paste the release notes above. Do not attach learner databases, `.env`, or the private RC candidate.
5. Leave the installed EXE in place until the Owner installs through the updater or a separate replacement approval. Rollback is restoring the previous EXE bytes `bbcd5e9a8bb22c72acdf863c94b68f6dbb7cc76717b737c6b93b0e50b28d58c3`. Do not restore a database over live learner data as part of that EXE rollback.
