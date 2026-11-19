# Active handoff

Rolling coordination checkpoint. The detailed history remains in [current_state.md](../current_state.md), [roadmap.md](../roadmap.md), [Phase 18B.9 status](../plans/PHASE-18B.9-offbox-status.md), [Phase 18C.1 GUI boundary](../plans/PHASE-18C.1-gui-boundary.md), and [ADR-024](../decisions/ADR-024-offbox-age-drive.md). Do not treat a commit/merge as a live activation.

## 1. Checkpoint metadata

- Written: 2026-11-19 (Architect Accepted merge of 18C.1).
- **18C.1 CLOSED — Architect Accepted** (PR #20, reviewed SHA `d2493c881335c046290555af5e6a9f6d8d480c72`). Local core Account Sync demonstration only.
- **Next active milestone: 18C.2** (signed-in GUI integration and related UX/safety — not started in this handoff).
- **18B.9 Off-box Recovery — PAUSED, NOT CLOSED**
- Production Cloud Sync remains **OFF**. GUI integration remains **not complete**.
- Historical 18B.9 note: SOURCE INSTALLED INACTIVE — NOT ACTIVATED; VPS units remain disabled. Historical pre-fix audit **UNSAFE**; D5A2D2/D5A2D3 **FAIL** preserved.

## 2. Last completed / accepted results

- **18C.1** Architect Accepted: schema v3, progress HTTP (default-off), per-account store, sync engine, conflict freeze, localhost two-device demo.
- GUI boundary unchanged: primary Tkinter study/vocab/progress/Mistake Book paths remain guest-file based. See [PHASE-18C.1-gui-boundary.md](../plans/PHASE-18C.1-gui-boundary.md).
- 18B.9 packaging sync remains historically PASS (static/inactive only). **No** daemon-reload / start / enable / OAuth / Drive.

## 3. Next App task — 18C.2

1. Real signed-in Tkinter Vocabulary / Quiz / Progress / Mistake Book integration.
2. Account preferences and study language sync.
3. Account-wide daily activity / learning streak.
4. Conflict resolution UX and blocked-conflict safety.
5. In-flight vocabulary upload versus newer local edits, with a deterministic race regression.
6. Safe engine shutdown, logout and account switching.
7. Legacy guest-data import with explicit user consent.
8. End-to-end GUI demonstration with two isolated profiles.

Do not claim the 18C.1 local demo proves full GUI integration. Production activation stays separately gated.

## 4. STOP / boundaries

- No VPS/SSH, production DB, production `STUDY_SYNC_ENABLED=1`, Google Drive/OAuth, or off-box changes without new Owner approval.
- No real-user guest→account auto-import on login.
- Phase 18B.9 **OPEN but PAUSED / PRODUCTION NOT READY**. Drive **NOT CONFIGURED**. Cloud Sync **OFF**.
