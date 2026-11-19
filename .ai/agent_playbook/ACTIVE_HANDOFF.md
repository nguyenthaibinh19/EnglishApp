# Active handoff

Rolling coordination checkpoint. The detailed history remains in [current_state.md](../current_state.md), [roadmap.md](../roadmap.md), [Phase 18B.9 status](../plans/PHASE-18B.9-offbox-status.md), [Phase 18C.1 GUI boundary](../plans/PHASE-18C.1-gui-boundary.md), [Phase 18C.2 acceptance](../plans/PHASE-18C.2-acceptance.md), and [ADR-024](../decisions/ADR-024-offbox-age-drive.md). Do not treat a commit/merge as a live activation.

## 1. Checkpoint metadata

- Written: 2026-11-19 (18C.2 ready for Architect review).
- **18C.1 CLOSED — Architect Accepted** (PR #20, merge `8e94f77491cc2f318c93fc511e258d0299ff4d03`).
- **18C.2 ACTIVE — Ready for Architect review** (signed-in GUI data path + prefs/streak/conflict/legacy-consent). Not merged. Not deployed.
- **18B.9 Off-box Recovery — PAUSED, NOT CLOSED**
- Production Cloud Sync remains **OFF**.

## 2. Last completed / accepted results

- **18C.1** Architect Accepted: schema v3, progress HTTP (default-off), per-account store, sync engine, conflict freeze, localhost two-device demo.
- **18C.2 (this PR, pending Architect):** `study_data.open_study_data()` wires Vocabulary / Quiz / Progress / Mistake Book / Daily Study / Reading-Listening add / StudyMaster when signed in; preferences contract v1; account day streak; conflict + legacy-import dialogs; demo `tools/demo_18c2_signed_in_gui_sync.py`. See [PHASE-18C.2-acceptance.md](../plans/PHASE-18C.2-acceptance.md).
- 18B.9 packaging sync remains historically PASS (static/inactive only). **No** daemon-reload / start / enable / OAuth / Drive.

## 3. Next after Architect review

1. Architect review of 18C.2 (no merge/deploy until accepted).
2. Any required corrections on the review PR.
3. Resume 18B.9 only under new Owner authorization.
4. Production Cloud Sync activation remains separately gated.

## 4. STOP / boundaries

- No VPS/SSH, production DB, production `STUDY_SYNC_ENABLED=1`, Google Drive/OAuth, or off-box changes without new Owner approval.
- No real-user guest→account auto-import on login (consent UI only).
- Phase 18B.9 **OPEN but PAUSED / PRODUCTION NOT READY**. Drive **NOT CONFIGURED**. Cloud Sync **OFF**.
