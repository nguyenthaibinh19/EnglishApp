# Phase 18D.3 — Final v1.5.0 release preparation

Status: v1.5.0 is published and the installed application was upgraded through the existing updater. Baseline `154bf03c6856667cf1322cfe4e6f31996e05e09f`. Release: https://github.com/nguyenthaibinh19/EnglishApp/releases/tag/v1.5.0. Real-account migration was not started.

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
| Installed EXE before upgrade, now the rollback copy | 36,050,859 | `bbcd5e9a8bb22c72acdf863c94b68f6dbb7cc76717b737c6b93b0e50b28d58c3` |
| Startup shortcut, unchanged | 1,273 | `6e8100b7a9b1e4faa151c0ac9cfc8c4eff41f453cffe1311a1a243acb2b8a93e` |
| `D:\EnglishApp\dist\langstudyguard.exe` | 36,168,317 | `4a9a5ef52972f9560ee9db40374bcef6f54ccdebc20002cea480041e91327695` |
| v1.5.0 RC candidate | 36,228,757 | `284f96460279e5812cac74fcefe2c2f407ea98d73502e255a02cf5ce28ffd3f5` |

## Frozen smoke

The rebuilt EXE was started only through `D:\EnglishApp\.local\labs\18d1\launch_rc_smoke.py`, with data root `D:\EnglishApp\.local\data\18d3-release-smoke`. The window title was `Language Guard — PRODUCTION BACKEND · RC TEST DATA`. It stayed a normal window. No updater dialog appeared. Screen lock was not activated.

Synthetic account id 3 signed in and signed out. The isolated account database then held 2 vocabulary entities, 2 attempts at sequences 1 and 2, and an empty outbox. Logout removed the session token. The earlier refusal checks still stand: a missing root, production AppData, the protected RC AppData folder, the install directory, and the recovery directory stop before opening data. The guarded launcher also refuses the 18D.1 incident root.

Emergency-code checks on that isolated root:

- Cancel left the existing acknowledged credential in place and did not lock the screen.
- A chosen code replaced it only after both fields matched. The file stayed DPAPI current-user, acknowledged, and did not contain the code in plaintext.
- That credential was still valid after the smoke process was restarted.
- A mismatched confirmation of a generated code left the chosen code in place.
- A matching confirmation replaced the chosen code. The generated value validated offline, the chosen value did not, and the file still had no plaintext secret.

During this smoke the installed EXE and the Startup shortcut hashes stayed at the pre-upgrade values below.

## Compatibility

The installed v1.4.0 updater and this build have the same bytecode for `parse_version`, `is_newer`, `_pick_asset`, and `_extract_exe_from_zip`. `is_newer("v1.5.0", "1.4.0")` is true. `_pick_asset` selects `langstudyguard.zip`. Extracting this ZIP in a temporary directory produced an EXE larger than 8 MB and left a sibling data file unchanged.

The updater replaces the installed executable path and does not call `install.prepare`. Learner data stays in the roaming data directory, so an upgrade or a rollback of the EXE does not replace that data.

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

## Published release and installed upgrade

The Owner's earlier authorization was used after the smoke passed. GitHub Release `v1.5.0`, title `v1.5.0 — Account Cloud Sync Update`, target `154bf03c6856667cf1322cfe4e6f31996e05e09f`: https://github.com/nguyenthaibinh19/EnglishApp/releases/tag/v1.5.0

The published asset `langstudyguard.zip` is 35,779,585 bytes, SHA-256 `b6e73009b832b26d5119fec40d402b78335b628e7759d97d67b54ef1da15d3d0`, and its only entry is `langstudyguard.exe` at 36,250,260 bytes. A downloaded copy matched that size and hash.

The installed v1.4.0 application was launched without `--lock`. Its updater offered v1.5.0, and accepting that offer replaced `%LOCALAPPDATA%\langstudyguard\langstudyguard.exe`. The installed file is now 36,250,260 bytes, SHA-256 `6954dbdadec226140ac35e55395ffda0c20a31b1ebaffde643c7edcd6d6ee1e9`. The previous EXE is kept at `D:\EnglishApp\.local\builds\18d3-v1.5.0-final\rollback-1.4.0\langstudyguard.exe`. The Startup shortcut was not rewritten.

The updater's first restart showed a PyInstaller bootloader dialog, `Failed to load Python DLL`, and did not open the home. The same installed file opened on the next launch. The binary was not rebuilt.

The open window is a normal unlocked `Language Guard — PRODUCTION` home. It shows the account panel, Study Settings, and Cloud Sync Synced. The study line shows 92 new words. Enrollment was cancelled, so no production emergency credential was saved and screen lock stayed off. The Owner can set a code from Study Settings.

Guest learner files were not resized. `settings.json` grew from 306 bytes to 385 bytes when the new version wrote its identity fields. A new production account database, 147,456 bytes, holds the 92 already accepted vocabulary entities, 0 attempts, an empty outbox, and no legacy-import rows. The server account still has 92 vocabulary entities, 0 attempts, max `updated_at` `2026-11-24 13:04:40`, and the database is still 151,552 bytes. The protected RC database is still 221,184 bytes with mtime `2026-11-24T13:04:32.9355334Z`. The 23 pending vocabulary operations and 6 pending progress events were not uploaded. Real-account migration was not started.
