# Active handoff

Rolling coordination checkpoint. See [current_state.md](../current_state.md) and [PHASE-18C.4-two-device-sync-acceptance.md](../plans/PHASE-18C.4-two-device-sync-acceptance.md).

## 1. Checkpoint metadata

- Written: 2026-11-24.
- Tag: `APP_18C4P_R6_CORE_SYNC_ACCEPTED`. The close tag was not returned.
- Source baseline: `de9969a36eea1fd0453c887fa8495ea3e9599b18`.
- Active priority: **18C.4P is not closed.** The destroyed-widget refresh callbacks are cancelled, and non-tombstone vocabulary Keep local converges on localhost. The full application suite was 3 failed, 930 passed, 24 skipped, 8 errors. Those failures also fail on the baseline. Production conflict, production offline, and production replay were not run.
- Application source baseline: `d6578c0f579d7ee9bd02aec855193339a7d8c124`.
- Remote main at start: `2ef0552d6cda58ff94dc02c680b2dd391b77aaef`.
- 18C.1, 18C.2, and 18C.3B remain CLOSED. The Sync Engine was not rebuilt.
- Phase 18B.10A: **AUDIT ACCEPTED, IMPLEMENTATION DEFERRED.** 18B.10B–E are **NOT AUTHORIZED.**
- Phase 18B.9: **PAUSED, NOT CLOSED.**
- Cloud Sync production: **ON**, supervised pilot. The verifier service completed `VERIFIED`.
- Staging deployment: **NOT STARTED.**
- Real two-PC vocabulary A → VPS → B: **PASS — Owner confirmed**. Same-machine restart persistence passed. Production conflict, production offline, and production replay are not claimed.
- Sync pilot: core sync is accepted. Full physical-device acceptance is not complete, and the full application suite is not green.
- RC account id 1, the 114 Dutch words, the 114 pending outbox rows, and recovery backups were not opened.

## 2. Evidence

- Shared source: `D:\EnglishApp\.local\clients\18c4p-r3`. Client A data: `.local\data\18c4p-r3`. Client B data: `.local\data\18c4p-r3-b`. Launcher: `.local\labs\18c4p-r3\launch_client.py`.
- Both clients are `syncpilot_18c4p`, user id 3, with distinct unchanged device ids. `syncprobe` remains revision 4, meaning `lab-marker-a`. Two accepted attempts are preserved, sequences 1 and 2. SRS counts are unchanged. Details: [PHASE-18C.4-two-device-sync-acceptance.md](../plans/PHASE-18C.4-two-device-sync-acceptance.md).
- The focused Account Sync suite passed, 88 tests, on a temporary localhost backend. That count includes `test_f2_keep_local_converges_both_clients`. The three Tk lifecycle tests passed. This evidence is separate from production.

## 3. Next

1. The full suite is not green. `test_sqlite_online_backup_preserves_synthetic_records` still expects schema 2. `test_languages_isolated_via_loader` still raises `FileNotFoundError` in `ensure_language_data`. Eight off-box tests still require a restic binary that is not installed.
2. Do not submit another quiz answer on the relaunched clients. Do not build an EXE until the suite result is accepted.

## 4. STOP

- Do not paste the synthetic password into chat.
- Do not follow the historical LAN, SSH, or staging-lab steps in the 18C.4 acceptance plan.
- Do not enable the sync backup timer.
- Do not upload the preserved 114-word account.
- Do not resume 18B.9 or implement 18B.10B–E.
- Put disposable artifacts in `D:\EnglishApp\.local`. Do not create a new `D:\lg-*` directory. See [LOCAL_WORKSPACE_POLICY.md](../procedures/LOCAL_WORKSPACE_POLICY.md).
