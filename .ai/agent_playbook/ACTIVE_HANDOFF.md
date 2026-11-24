# Active handoff

Rolling coordination checkpoint. See [current_state.md](../current_state.md) and [PHASE-18C.4-two-device-sync-acceptance.md](../plans/PHASE-18C.4-two-device-sync-acceptance.md).

## 1. Checkpoint metadata

- Written: 2026-11-24.
- Tag: withheld. `APP_18D3_FINAL_V150_READY_FOR_PUBLICATION_REVIEW` is not returned. The final EXE is built. Frozen sign-in is waiting for the synthetic account password.
- Source baseline: `2d014462759b2c98fe7beb246c9654800e26898a`. Final EXE SHA-256 `9d4e6ae49d4545e195fc12a7e9b7e4face9bb5165293d16f70781d475f1ae199`. ZIP SHA-256 `e4d0d687ff08b9f4a2ce61cfa5f18b3011432fac5322799d1ab09bda55038e59`.
- Active priority: **Finish the guarded smoke on the open sign-in window, then review publication. Do not publish yet and do not upload the pending account id 1 operations.** The window title is `Language Guard — PRODUCTION BACKEND · RC TEST DATA`. Username `syncpilot_18c4p` is filled. Data root `D:\EnglishApp\.local\data\18d3-final-smoke`. Production `sync_http.py` remains `d173ad179ca9039a13489df0ce8ca81473ddfd711897fd803af96f60920f0dd2`. `language-guard-sync-backup.timer` is enabled. Next elapse: `2026-11-25 04:47:46 UTC`. The timer has not run a backup. The protected database still preserves all 114 original vocabulary entities. 92 match the server. 23 vocabulary operations and 6 progress events remain pending.
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

1. Type the synthetic account password into the open sign-in window and continue the guarded smoke in [PHASE-18D.3-final-v1.5.0-release.md](../plans/PHASE-18D.3-final-v1.5.0-release.md). Do not publish from this partial smoke.
2. Keep publication closed until that smoke finishes and the Owner approves. The public ZIP name is `langstudyguard.zip` and it must contain `langstudyguard.exe`. The Sync backup timer is enabled, and its first natural run has not occurred.
3. Do not upload the pending account id 1 operations. Do not point RC smoke at `.local\data\18d1-v1.5.0-rc`.

## 4. STOP

- Do not paste the synthetic password into chat.
- Do not follow the historical LAN, SSH, or staging-lab steps in the 18C.4 acceptance plan.
- Do not disable the Sync backup timer and do not treat the manual `study-sync-20261124-174104-409289.db` snapshot as the first natural 04:45 UTC run.
- Do not upload the preserved 114-word account.
- Do not resume 18B.9 or implement 18B.10B–E.
- Put disposable artifacts in `D:\EnglishApp\.local`. Do not create a new `D:\lg-*` directory. See [LOCAL_WORKSPACE_POLICY.md](../procedures/LOCAL_WORKSPACE_POLICY.md).
