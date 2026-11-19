# Active handoff

Rolling coordination checkpoint. See [current_state.md](../current_state.md), [roadmap.md](../roadmap.md), [PHASE-18C.2-acceptance.md](../plans/PHASE-18C.2-acceptance.md), and [PHASE-18B.9-offbox-status.md](../plans/PHASE-18B.9-offbox-status.md). Do not treat a commit/merge as a live activation.

## 1. Checkpoint metadata

- Written: 2026-11-19 (18C.2 Architect Accepted merge).
- **18C.1 CLOSED — Architect Accepted** (PR #20).
- **18C.2 CLOSED — Architect Accepted** (PR #21). Signed-in GUI account sync in source; production Cloud Sync remains OFF.
- **18B.9 Off-box Recovery — PAUSED, NOT CLOSED**
- Production Cloud Sync remains **OFF**.

## 2. Last results

- **18C.2** Architect Accepted: signed-in Tkinter data path via `study_data.open_study_data()`; preferences optimistic concurrency; UTC `occurred_at` / UTC Today alignment; tombstone-safe vocab resolve; in-flight late-ack rebase; two-profile demo + GUI walkthrough evidence.
- Guest AttemptHistory ledger/overlap import remains **deferred**.

## 3. Next

1. Do not auto-start a new milestone from this handoff.
2. Resume 18B.9 only under new Owner authorization.
3. Production Cloud Sync activation remains separately gated.

## 4. STOP / boundaries

- No VPS/SSH, production DB, production `STUDY_SYNC_ENABLED=1`, Google Drive/OAuth, or off-box changes without new Owner approval.
- Phase 18B.9 **OPEN but PAUSED**. Drive **NOT CONFIGURED**. Cloud Sync **OFF**.
