# Active handoff

Rolling coordination checkpoint. See [current_state.md](../current_state.md), [roadmap.md](../roadmap.md), [PHASE-18C.2-acceptance.md](../plans/PHASE-18C.2-acceptance.md), and [PHASE-18B.9-offbox-status.md](../plans/PHASE-18B.9-offbox-status.md). Do not treat a commit/merge as a live activation.

## 1. Checkpoint metadata

- Written: 2026-11-19 (18C.2 Architect R1 corrections).
- **18C.1 CLOSED — Architect Accepted** (PR #20, merge `8e94f77491cc2f318c93fc511e258d0299ff4d03`).
- **18C.2 ACTIVE — Under Review** (PR #21; R1 prefs/tombstone/in-flight/GUI corrections). Not merged. Not deployed.
- **18B.9 Off-box Recovery — PAUSED, NOT CLOSED**
- Production Cloud Sync remains **OFF**.

## 2. Last results

- **18C.1** Architect Accepted: schema v3, progress HTTP (default-off), per-account store/engine, conflict freeze, localhost demo.
- **18C.2 R1:** remote-prefs dirty-loop fixed; tombstone-safe conflict resolution (`local_as_new`); late in-flight vocab ack rebases newer local edit; real Tkinter two-profile walkthrough evidence under `qa-evidence/phase18c2-gui-sync/gui-walkthrough/`.
- Full ADR-022 AttemptHistory ledger import remains outstanding (documented).

## 3. Next after Architect review

1. Architect re-review of PR #21 (no merge/deploy until accepted).
2. Resume 18B.9 only under new Owner authorization.
3. Production Cloud Sync activation remains separately gated.

## 4. STOP / boundaries

- No VPS/SSH, production DB, production `STUDY_SYNC_ENABLED=1`, Google Drive/OAuth, or off-box changes without new Owner approval.
- No real-user guest→account auto-import on login (consent UI only; attempt ledger deferred).
- Phase 18B.9 **OPEN but PAUSED**. Drive **NOT CONFIGURED**. Cloud Sync **OFF**.
