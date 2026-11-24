# Active handoff

Rolling coordination checkpoint. See [current_state.md](../current_state.md) and [PHASE-18C.4-two-device-sync-acceptance.md](../plans/PHASE-18C.4-two-device-sync-acceptance.md).

## 1. Checkpoint metadata

- Written: 2026-11-24.
- Tag: `APP_18D3_V150_RELEASED_OWNER_UPGRADE_COMPLETE`. Release: https://github.com/nguyenthaibinh19/EnglishApp/releases/tag/v1.5.0.
- Source baseline: `154bf03c6856667cf1322cfe4e6f31996e05e09f`. Installed EXE SHA-256 `6954dbdadec226140ac35e55395ffda0c20a31b1ebaffde643c7edcd6d6ee1e9`. ZIP SHA-256 `b6e73009b832b26d5119fec40d402b78335b628e7759d97d67b54ef1da15d3d0`.
- Active priority: **v1.5.0 is installed and open in normal unlocked mode. Do not start real-account migration and do not upload the pending account id 1 operations.** The home shows the account panel, Study Settings, and Cloud Sync Synced. No production emergency credential is saved. Production `sync_http.py` remains `d173ad179ca9039a13489df0ce8ca81473ddfd711897fd803af96f60920f0dd2`. `language-guard-sync-backup.timer` is enabled. Next elapse: `2026-11-25 04:47:46 UTC`. The timer has not run a backup. The manual backup `study-sync-20261124-174104-409289.db` is still `VERIFIED`. The protected database still preserves all 114 original vocabulary entities. 92 match the server. 23 vocabulary operations and 6 progress events remain pending.
- Application source baseline: `d6578c0f579d7ee9bd02aec855193339a7d8c124`.
- Remote main at start: `2ef0552d6cda58ff94dc02c680b2dd391b77aaef`.
- 18C.1, 18C.2, and 18C.3B remain CLOSED. The Sync Engine was not rebuilt.
- Phase 18B.10A: **AUDIT ACCEPTED, IMPLEMENTATION DEFERRED.** 18B.10B–E are **NOT AUTHORIZED.**
- Phase 18B.9: **PAUSED, NOT CLOSED.**
- Cloud Sync production: **ON**, supervised pilot. The verifier service completed `VERIFIED`.
- Staging deployment: **NOT STARTED.**
- Real two-PC vocabulary A → VPS → B: **PASS — Owner confirmed**. Same-machine restart persistence passed. Production conflict, production offline, and production replay are not claimed.
- Sync pilot: closed within the approved pilot scope. Full physical-device acceptance beyond the owner-confirmed vocabulary direction is not complete.
- Account id 1 reconciliation is in [PHASE-18D.1-desktop-release-candidate.md](../plans/PHASE-18D.1-desktop-release-candidate.md). The 2026-11-19 recovery copy was read and not overwritten. Local and production incident backups are under `.local\backups\18d1-data-incident\` and `/var/backups/language-guard/study-sync/`; neither is in Git.

## 2. Evidence

- Shared source: `D:\EnglishApp\.local\clients\18c4p-r3`. Client A data: `.local\data\18c4p-r3`. Client B data: `.local\data\18c4p-r3-b`. Launcher: `.local\labs\18c4p-r3\launch_client.py`.
- Both clients are `syncpilot_18c4p`, user id 3, with distinct unchanged device ids. `syncprobe` remains revision 4, meaning `lab-marker-a`. Two accepted attempts are preserved, sequences 1 and 2. SRS counts are unchanged. Details: [PHASE-18C.4-two-device-sync-acceptance.md](../plans/PHASE-18C.4-two-device-sync-acceptance.md).
- The focused Account Sync suite passed, 88 tests, on a temporary localhost backend. That count includes `test_f2_keep_local_converges_both_clients`. The three Tk lifecycle tests passed. This evidence is separate from production.
- The full application suite after the screen-lock guard correction: **970 passed, 25 skipped, 0 failed**. Details: [PHASE-18D.2A-emergency-exit-security.md](../plans/PHASE-18D.2A-emergency-exit-security.md).

## 3. Next

1. Leave the installed v1.5.0 window unlocked. The Owner sets an emergency code privately from Study Settings. Do not turn on screen lock.
2. Real-account migration stays a separate operation. Do not upload the pending account id 1 operations. The first natural Sync backup has not occurred.
3. Do not point RC smoke at `.local\data\18d1-v1.5.0-rc`. Rollback of the EXE is the copy at `.local\builds\18d3-v1.5.0-final\rollback-1.4.0\langstudyguard.exe`.

## 4. STOP

- Do not paste the synthetic password into chat.
- Do not follow the historical LAN, SSH, or staging-lab steps in the 18C.4 acceptance plan.
- Do not disable the Sync backup timer and do not treat the manual `study-sync-20261124-174104-409289.db` snapshot as the first natural 04:45 UTC run.
- Do not upload the preserved 114-word account.
- Do not resume 18B.9 or implement 18B.10B–E.
- Put disposable artifacts in `D:\EnglishApp\.local`. Do not create a new `D:\lg-*` directory. See [LOCAL_WORKSPACE_POLICY.md](../procedures/LOCAL_WORKSPACE_POLICY.md).
