# Active handoff

Rolling coordination checkpoint. See [current_state.md](../current_state.md) and [PHASE-18C.4-two-device-sync-acceptance.md](../plans/PHASE-18C.4-two-device-sync-acceptance.md).

## 1. Checkpoint metadata

- Written: 2026-11-25.
- Tag: `APP_19D2A_UI_FOUNDATION_HOME_READY_FOR_REVIEW`. Branch: `phase19.2a/ui-foundation-today`. Not merged. Architect decision: `APP_19D1_ARCHITECT_ACCEPTED_CLOSED`. Waves V1 and V2 only. The Phase 19.1 spec remains on `main` at `26cd368d29679b74a8d32c9a14b10d6d1624b76e`.
- Source baseline: `88239b61e4255e24446bea076486c4411bebdced`. Installed EXE SHA-256 `6954dbdadec226140ac35e55395ffda0c20a31b1ebaffde643c7edcd6d6ee1e9`.
- Active priority: **Review 19.2A waves V1 and V2. Do not merge, and do not start V3–V7 or E1–E4.** Today keeps the existing study, account, vocabulary, progress, mistake-book, and emergency dialogs. Account ID 1 migration remains complete. Do not launch the protected RC database again. Server and installed app: 115 vocabulary entities, 6 attempts, 6 progress rows, empty pending outbox, no conflicts. The 114 recovery IDs match. The extra entity `242e5e4c-4345-447c-a777-44df6132b2da` is present once. Accepted event IDs: `1ac28d33-316d-40e4-b68e-d90be119e734`, `72deb6e9-a3a0-4eb3-835a-40249bf2204d`, `7d67dc07-ac1f-4e6b-b911-0529826c7fd9`, `8f7c5f0a-2665-49fc-9350-6ecaefc6770e`, `ac4d0208-9992-408a-a1dd-19f7dc9d6552`, `cc1a1d73-1e53-44c2-845a-e2413f20519b`. Post-migration backup `study-sync-20261124-204803-765136.db`, SHA-256 `7ed7ad81fa39d8eb6596c8b8b74b64b3ae23dc041da5e4db8fafdb6f2071def6`, checked `2026-11-24T20:48:12Z`, status `VERIFIED`. Preferences were not changed. Account ID 3 is still 2 vocabulary entities and 2 attempts. The installed home is unlocked: 3 due, 109 new, Cloud Sync Synced. Production `sync_http.py` remains `d173ad179ca9039a13489df0ce8ca81473ddfd711897fd803af96f60920f0dd2`. The backup timer is enabled. Next elapse: `2026-11-25 04:47:46 UTC`. It has not fired.
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

1. Review branch `phase19.2a/ui-foundation-today`. Preview with `LG_DATA_DIR` set to `D:\EnglishApp\.local\data\19d2a-ui-preview` and `python app/main.py` from the worktree. Do not point that variable at production AppData.
2. Leave the installed v1.5.0 window unlocked. Do not launch the protected RC database or upload anything further for account ID 1.
3. Do not point RC smoke at `.local\data\18d1-v1.5.0-rc`. Rollback of the EXE is the copy at `.local\builds\18d3-v1.5.0-final\rollback-1.4.0\langstudyguard.exe`.

## 4. STOP

- Do not paste the synthetic password into chat.
- Do not follow the historical LAN, SSH, or staging-lab steps in the 18C.4 acceptance plan.
- Do not disable the Sync backup timer and do not treat the manual `study-sync-20261124-174104-409289.db` snapshot as the first natural 04:45 UTC run.
- Do not upload the preserved 114-word account.
- Do not resume 18B.9 or implement 18B.10B–E.
- Put disposable artifacts in `D:\EnglishApp\.local`. Do not create a new `D:\lg-*` directory. See [LOCAL_WORKSPACE_POLICY.md](../procedures/LOCAL_WORKSPACE_POLICY.md).
