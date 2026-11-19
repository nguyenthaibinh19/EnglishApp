# Active handoff

Rolling coordination checkpoint. The detailed history remains in [current_state.md](../current_state.md), [roadmap.md](../roadmap.md), [Phase 18B.9 status](../plans/PHASE-18B.9-offbox-status.md), [Phase 18C.1 GUI boundary](../plans/PHASE-18C.1-gui-boundary.md), and [ADR-024](../decisions/ADR-024-offbox-age-drive.md). Do not treat a commit/merge as a live activation.

## 1. Checkpoint metadata

- Written: 2026-11-19 (Owner priority redirect).
- **18C Account Data Sync — ACTIVE**
- **18B.9 Off-box Recovery — PAUSED, NOT CLOSED**
- Active review PR: [#20](https://github.com/nguyenthaibinh19/EnglishApp/pull/20) (18C.1). Production Cloud Sync remains **OFF**.
- Historical 18B.9 note: SOURCE INSTALLED INACTIVE — NOT ACTIVATED (`APP_18B9_INACTIVE_VPS_PACKAGING_SYNC`); approved main `eb869eaf310504862a10c902ea2e8803fbab0b53`; VPS units remain disabled. Historical pre-fix audit **UNSAFE**; D5A2D2/D5A2D3 **FAIL** preserved.

## 2. Last completed / accepted results

- **18C.1 local vertical slice** in source for Architect review: schema v3, progress HTTP (default-off), per-account store, sync engine, localhost two-device demo.
- GUI boundary documented: primary Tkinter study/vocab paths remain guest-file based; account store is engine/demo until **18C.2**. See [PHASE-18C.1-gui-boundary.md](../plans/PHASE-18C.1-gui-boundary.md).
- 18B.9 packaging sync remains historically PASS (static/inactive only). **No** daemon-reload / start / enable / OAuth / Drive.

## 3. Next App task

1. Architect acceptance of PR #20 corrections (F1–F4). **Do not merge** without Architect acceptance.
2. **18C.2** (after acceptance): signed-in GUI integration, account preferences, daily activity/streak UX, remaining ADR-022 consent/migration — still no production activation by default.
3. **18B.9** remains paused: no VPS/Drive/OAuth/activation without new Owner approval.

## 4. STOP / boundaries

- No PR merge without Architect acceptance.
- No VPS/SSH, production DB, production `STUDY_SYNC_ENABLED=1`, Google Drive/OAuth, or off-box changes from the 18C.1 workstream.
- No real-user guest→account auto-import on login.
- Phase 18B.9 **OPEN but PAUSED / PRODUCTION NOT READY**. Drive **NOT CONFIGURED**. Cloud Sync **OFF**.
