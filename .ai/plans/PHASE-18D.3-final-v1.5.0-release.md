# Phase 18D.3 — Final v1.5.0 release preparation

Status: build and compatibility checks are complete. Frozen sign-in smoke is open and waiting for the synthetic account password. The publication-ready tag is not returned. Baseline `2d014462759b2c98fe7beb246c9654800e26898a`. No public release was created and no release tag was pushed.

## Final artifacts

Built with `build_exe.bat` from the accepted main source. A leftover gitignored `build_manifest.json` would have stamped version 1.4.0, so that file was removed and the production build was run again. The published artifacts are the second build.

| File | Bytes | SHA-256 |
|---|---:|---|
| `D:\EnglishApp\.local\builds\18d3-v1.5.0-final\langstudyguard.exe` | 36,247,427 | `9d4e6ae49d4545e195fc12a7e9b7e4face9bb5165293d16f70781d475f1ae199` |
| `D:\EnglishApp\.local\builds\18d3-v1.5.0-final\langstudyguard.zip` | 35,776,293 | `e4d0d687ff08b9f4a2ce61cfa5f18b3011432fac5322799d1ab09bda55038e59` |

The ZIP contains one entry, `langstudyguard.exe`, and that entry is the same size as the executable.

Embedded `build_manifest.json`: channel `production`, version `1.5.0`, commit `2d014462759b2c98fe7beb246c9654800e26898a`, built `2026-11-24T18:22:53Z`.

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

The final EXE was started only through `D:\EnglishApp\.local\labs\18d1\launch_rc_smoke.py` for the signed-in path, with data root `D:\EnglishApp\.local\data\18d3-final-smoke`. The window title is `Language Guard — PRODUCTION BACKEND · RC TEST DATA`. The sign-in form shows that banner. It is a small window, not a screen lock. No updater dialog appeared. The username `syncpilot_18c4p` is filled. The password field is empty.

The same EXE, with `LG_RC_SMOKE=1`, stopped before opening data for a missing root, production AppData, the protected RC AppData folder, the production install directory, and the recovery directory. The guarded launcher also refuses the 18D.1 incident root and production AppData. A direct launch at the incident root is not part of the guarded procedure. One such launch wrote `emergency_credential.json` there. That new file was removed. The incident account databases were not rewritten.

Not yet done on this binary: emergency-code enrollment, cancelled enrollment, credential persistence across restart, password login, logout, and the account id 3 vocabulary, attempt, and SRS download. Screen lock was not activated.

## Compatibility

The installed v1.4.0 updater and this build have the same bytecode for `parse_version`, `is_newer`, `_pick_asset`, and `_extract_exe_from_zip`. `is_newer("v1.5.0", "1.4.0")` is true. `_pick_asset` selects `langstudyguard.zip`. Extracting this ZIP in a temporary directory produced an EXE larger than 8 MB and left a sibling data file unchanged.

The updater replaces the installed executable path and does not call `install.prepare`. Learner data stays in the roaming data directory, so an upgrade or a rollback of the EXE does not replace that data. This task did not replace the installed EXE.

Clean full suite, after the gitignored production manifest was removed from the source tree: **974 passed, 24 skipped, 0 failed**.

## Backup observation

`language-guard-sync-backup.timer` is still enabled and active. `LastTriggerUSec` is empty. The next elapse remains `2026-11-25 04:47:46 UTC`. The verifier's next elapse remains `2026-11-25 07:00:00 UTC`. The first natural backup has not occurred. The timer was not changed and no manual backup was run for this task.

## Release notes

Language Guard 1.5.0 is a production-channel desktop build from `2d014462759b2c98fe7beb246c9654800e26898a`. It talks to `https://langstudyguard.com`. Screen lock stays off until the learner saves a local emergency code on that computer. Release packaging does not embed a shared emergency password. RC smoke refuses a missing or protected data root. Cloud Sync for the supervised pilot stays available. The recurring on-server Sync backup timer is enabled. Its first natural run is still pending.

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

1. Confirm the ZIP SHA-256 is still `e4d0d687ff08b9f4a2ce61cfa5f18b3011432fac5322799d1ab09bda55038e59`.
2. From the accepted commit, create a GitHub Release titled `v1.5.0`. The tag is created only with that approval.
3. Upload `langstudyguard.zip` as an asset with that exact name. The updater selects that name and extracts `langstudyguard.exe`.
4. Paste the release notes above. Do not attach learner databases, `.env`, or the private RC candidate.
5. Leave the installed EXE in place until the Owner installs through the updater or a separate replacement approval. Rollback is restoring the previous EXE bytes `bbcd5e9a8bb22c72acdf863c94b68f6dbb7cc76717b737c6b93b0e50b28d58c3`. Do not restore a database over live learner data as part of that EXE rollback.
