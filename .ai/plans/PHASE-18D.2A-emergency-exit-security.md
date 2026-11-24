# Phase 18D.2A — Emergency exit security

Status: **lock guard corrected and ready for review.** No EXE was built or published. Correction baseline: `26fd5c4c7acb3d44c6ac1029b858338f8b80ece7`.  
Date: 2026-11-24

Screen lock now depends on a local emergency credential. Future production packaging does not embed a shared emergency password.

## Lifecycle

1. When no credential file exists, the app generates a code with `secrets.token_urlsafe` and protects it with the current protection interface.
2. The protected blob is written under the validated data root as `emergency_credential.json`, with `acknowledged` false. The plaintext is not stored.
3. The app unprotects the blob and checks it before showing the code. The user must type it back.
4. Acknowledgement is stored only after that local check succeeds. Screen lock stays off until then.
5. Cancel, or closing the dialog, deletes an unacknowledged file and leaves the app unlocked. An acknowledged credential is not deleted by cancel.
6. An interrupted enrollment keeps the same unacknowledged code and shows it again on the next attempt. It does not generate a replacement by itself.
7. Login, logout, account switch, restart, and upgrade do not move the file. It is outside `settings.json` and outside the synced preference keys `study_languages`, `reading_level`, `native`, and `activities`.
8. Emergency Exit compares the typed code with the unprotected local secret using `hmac.compare_digest`. It does not use the network.

## Upgrade

A new build does not contain the old bundled password and does not require it. An existing v1.4.0 installation has no local credential, so `--lock` from the existing Startup shortcut does not engage. The shortcut file is left unchanged. The app stays in setup or the normal unlocked window until the user acknowledges a local code.

A fresh installation may copy the EXE before enrollment. Startup registration and screen lock both wait until that acknowledgement. The copy launches the installed EXE and does not create a Startup `--lock` shortcut. The shortcut is created only after acknowledgement, and only when one does not already exist. Registration failure does not delete the installed EXE or an existing shortcut.

A usable acknowledged credential is not replaced automatically. Replacing an unreadable file, or choosing a new code from the unlocked settings screen, writes a pending file and commits it only after the new code is typed back.

## Recovery

Recovery is available from the unlocked study settings screen. It is refused while screen lock is active.

- Show the current code again. DPAPI unprotects it for the same Windows user.
- Create a new code. The previous code remains valid until the new one is confirmed.
- If the file is missing or cannot be read, screen lock stays off. A new code replaces it only after confirmation.

## DPAPI limits

Production protection is `CryptProtectData` / `CryptUnprotectData` with `CRYPTPROTECT_UI_FORBIDDEN` (0x01). The machine-wide flag `CRYPTPROTECT_LOCAL_MACHINE` (0x04) is not set. The guard tests inject a protection double. One separate test performs a native DPAPI round trip on a temporary directory and does not enable screen lock.

The blob can be decrypted by the same Windows user, including other programs running as that user. Another Windows user cannot decrypt it. A copy of the file on another profile or computer does not decrypt. If the Windows profile is lost, the blob cannot be recovered; the app remains unlocked and the user can enroll a new code. This is current-user DPAPI, not a server secret and not a custom cipher.

## Packaging

`bundle_secrets.py` writes `account_server_url` only. `config.bundled_password()` returns an empty string and is not used for Emergency Exit. `config.is_ready()` means account setup is complete. It does not treat a missing emergency code as a failed account setup. The already-built v1.5.0 candidate was not rebuilt, so that private EXE still contains the old placeholder and must not be published.

## Screen-lock guard

`ScreenGuard` is the only place enforcement turns on. `enabled=True` is not enough. The guard also requires `emergency_credential.lock_allowed()`, so a missing, unacknowledged, or unreadable credential leaves the window unlocked. That covers StudyMasterApp, Vocabulary, Reading, Listening, and language setup, including Start today's study after enrollment is cancelled.

While the credential is unavailable, closing the window returns home or closes the child activity. It does not demand the missing code, and it does not mark the unfinished session complete. A credential that disappears during an active lock is disarmed on the next focus or close, so the user can leave.

When an acknowledged credential exists and lock is requested, fullscreen enforcement and the existing close restrictions stay in place. Emergency Exit still accepts only the local code. A wrong code leaves the lock up.

A fresh installation may copy the EXE before enrollment. Startup registration and screen lock both wait until acknowledgement. An existing Startup shortcut is not rewritten. `--lock` from that shortcut does not engage until the local code is acknowledged.

A native Windows DPAPI round trip succeeded on a temporary data root. The generated code was not recorded, and that check did not turn on screen lock.

## Regression

Full application suite: **970 passed, 25 skipped, 0 failed.** That run includes the screen-lock guard tests, the emergency-credential tests, and the existing installation, environment-isolation, screen-lock, and updater tests. The tests use temporary directories and fake windows. One native DPAPI round trip used a temporary data root and did not turn on screen lock. The suite does not open the protected learner database or build an EXE.
