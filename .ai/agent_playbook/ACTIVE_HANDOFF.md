# Active handoff

Rolling coordination checkpoint. See [current_state.md](../current_state.md) and [PHASE-18C.4-two-device-sync-acceptance.md](../plans/PHASE-18C.4-two-device-sync-acceptance.md).

## 1. Checkpoint metadata

- Written: 2026-11-24.
- Tag: 18D.1 candidate built. `APP_18D1_DESKTOP_RELEASE_CANDIDATE_READY_FOR_REVIEW` was not returned.
- Source baseline: `54f452da36211e419ef51a105009c1428b2525a9`. Packaged commit: `29292749da54b0035833321a80e2776007b6ee8e`.
- Active priority: **v1.5.0 RC is built and waiting for the Owner to sign in on the open window.** Data root is `D:\EnglishApp\.local\data\18d1-v1.5.0-rc`. Do not paste the password into chat. Production `sync_http.py` is still `aa88f693764912f589a5945d7b3f154b587363311130b01295127cb600ddd5d1`.
- Application source baseline: `d6578c0f579d7ee9bd02aec855193339a7d8c124`.
- Remote main at start: `2ef0552d6cda58ff94dc02c680b2dd391b77aaef`.
- 18C.1, 18C.2, and 18C.3B remain CLOSED. The Sync Engine was not rebuilt.
- Phase 18B.10A: **AUDIT ACCEPTED, IMPLEMENTATION DEFERRED.** 18B.10B–E are **NOT AUTHORIZED.**
- Phase 18B.9: **PAUSED, NOT CLOSED.**
- Cloud Sync production: **ON**, supervised pilot. The verifier service completed `VERIFIED`.
- Staging deployment: **NOT STARTED.**
- Real two-PC vocabulary A → VPS → B: **PASS — Owner confirmed**. Same-machine restart persistence passed. Production conflict, production offline, and production replay are not claimed.
- Sync pilot: closed within the approved pilot scope. Full physical-device acceptance beyond the owner-confirmed vocabulary direction is not complete.
- RC account id 1, the 114 Dutch words, the 114 pending outbox rows, and recovery backups were not opened.

## 2. Evidence

- Shared source: `D:\EnglishApp\.local\clients\18c4p-r3`. Client A data: `.local\data\18c4p-r3`. Client B data: `.local\data\18c4p-r3-b`. Launcher: `.local\labs\18c4p-r3\launch_client.py`.
- Both clients are `syncpilot_18c4p`, user id 3, with distinct unchanged device ids. `syncprobe` remains revision 4, meaning `lab-marker-a`. Two accepted attempts are preserved, sequences 1 and 2. SRS counts are unchanged. Details: [PHASE-18C.4-two-device-sync-acceptance.md](../plans/PHASE-18C.4-two-device-sync-acceptance.md).
- The focused Account Sync suite passed, 88 tests, on a temporary localhost backend. That count includes `test_f2_keep_local_converges_both_clients`. The three Tk lifecycle tests passed. This evidence is separate from production.

## 3. Next

1. Sign in on the open `langstudyguard-rc` window as the existing synthetic account. Type the password only in that window.
2. After sign-in, finish language selection, vocabulary sync, Progress and SRS download, then close and reopen. Do not submit another quiz answer.
3. Do not publish the RC ZIP. The public asset must be `langstudyguard.zip` containing `langstudyguard.exe`.

## 4. STOP

- Do not paste the synthetic password into chat.
- Do not follow the historical LAN, SSH, or staging-lab steps in the 18C.4 acceptance plan.
- Do not enable the sync backup timer.
- Do not upload the preserved 114-word account.
- Do not resume 18B.9 or implement 18B.10B–E.
- Put disposable artifacts in `D:\EnglishApp\.local`. Do not create a new `D:\lg-*` directory. See [LOCAL_WORKSPACE_POLICY.md](../procedures/LOCAL_WORKSPACE_POLICY.md).
