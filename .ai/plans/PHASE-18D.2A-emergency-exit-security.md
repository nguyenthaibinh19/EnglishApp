# Phase 18D.2A — Emergency exit security

Status: **ready for review.** No EXE was built or published. Baseline: `3fad3da6a1b735b803d57dcd6d9b122142fcaefc`.  
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

A fresh install copies the EXE and launches it. It does not create a Startup `--lock` shortcut during that copy. The shortcut is created only after acknowledgement, and only when one does not already exist. Registration failure does not delete the installed EXE or an existing shortcut.

A usable acknowledged credential is not replaced automatically. Replacing an unreadable file, or choosing a new code from the unlocked settings screen, writes a pending file and commits it only after the new code is typed back.

## Recovery

Recovery is available from the unlocked study settings screen. It is refused while screen lock is active.

- Show the current code again. DPAPI unprotects it for the same Windows user.
- Create a new code. The previous code remains valid until the new one is confirmed.
- If the file is missing or cannot be read, screen lock stays off. A new code replaces it only after confirmation.

## DPAPI limits

Production protection is `CryptProtectData` / `CryptUnprotectData` with `CRYPTPROTECT_UI_FORBIDDEN` (0x01). The machine-wide flag `CRYPTPROTECT_LOCAL_MACHINE` (0x04) is not set. Tests inject a protection double and do not call DPAPI.

The blob can be decrypted by the same Windows user, including other programs running as that user. Another Windows user cannot decrypt it. A copy of the file on another profile or computer does not decrypt. If the Windows profile is lost, the blob cannot be recovered; the app remains unlocked and the user can enroll a new code. This is current-user DPAPI, not a server secret and not a custom cipher.

## Packaging

`bundle_secrets.py` writes `account_server_url` only. `config.bundled_password()` returns an empty string and is not used for Emergency Exit. `config.is_ready()` means account setup is complete. It does not treat a missing emergency code as a failed account setup. The already-built v1.5.0 candidate was not rebuilt, so that private EXE still contains the old placeholder and must not be published.

## Regression

Full application suite: **961 passed, 23 skipped, 0 failed.** That run includes the new emergency-credential tests and the existing installation, environment-isolation, screen-lock, and updater tests. The tests use temporary directories and an injected protection double. They do not start screen lock, open the protected learner database, or build an EXE.
