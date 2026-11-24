# Active handoff

Rolling coordination checkpoint. See [current_state.md](../current_state.md) and [PHASE-18C.4-two-device-sync-acceptance.md](../plans/PHASE-18C.4-two-device-sync-acceptance.md).

## 1. Checkpoint metadata

- Written: 2026-11-24.
- Tag: `APP_18D1_DATA_INCIDENT_RECONCILED_READY_FOR_REVIEW`. Public release remains blocked. `APP_18D1_DESKTOP_RELEASE_CANDIDATE_READY_FOR_REVIEW` was not returned.
- Source baseline: `54f452da36211e419ef51a105009c1428b2525a9`. Packaged commit: `29292749da54b0035833321a80e2776007b6ee8e`. Reconciliation baseline: `e9457e3418579d44f51a7ca261a0f89fbf747c82`.
- Active priority: **Do not publish the v1.5.0 candidate and do not continue the account id 1 upload from the isolated copy.** The protected database preserves all 114 original vocabulary entities. 92 match the server. 22 original vocabulary operations and 6 progress events remain pending and recoverable. The candidate process is signed in as account id 1 on the isolated data root and holds a 92-entity download without those pending rows. Do not close it unless a later decision says to. Do not reverse acknowledgements. Production `sync_http.py` is still `aa88f693764912f589a5945d7b3f154b587363311130b01295127cb600ddd5d1`.
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

## 3. Next

1. Review the account id 1 reconciliation. Continue the remaining upload only from the protected database, and only after the isolated account id 1 session is stopped by a separate decision.
2. Keep the five public-release gates closed: synthetic emergency password, bundling architecture review, undeployed `sync_http.py` body-drain, disabled sync backup timer, and a public ZIP named `langstudyguard.zip` containing `langstudyguard.exe`.
3. A future smoke launcher should refuse to start unless `LG_DATA_DIR` is the isolated directory. That guard is not implemented.

## 4. STOP

- Do not paste the synthetic password into chat.
- Do not follow the historical LAN, SSH, or staging-lab steps in the 18C.4 acceptance plan.
- Do not enable the sync backup timer.
- Do not upload the preserved 114-word account.
- Do not resume 18B.9 or implement 18B.10B–E.
- Put disposable artifacts in `D:\EnglishApp\.local`. Do not create a new `D:\lg-*` directory. See [LOCAL_WORKSPACE_POLICY.md](../procedures/LOCAL_WORKSPACE_POLICY.md).
