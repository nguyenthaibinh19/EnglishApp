# Active handoff

Rolling coordination checkpoint. See [current_state.md](../current_state.md) and [APP-114-VOCAB-RECOVERY-RC-SYNC-STATUS.md](../plans/APP-114-VOCAB-RECOVERY-RC-SYNC-STATUS.md).

## 1. Checkpoint metadata

- Written: 2026-11-19 (APP-114 / PR #25 **Architect Accepted — source merged**).
- Tag: `APP_114_VOCAB_RC_MERGED_ACCEPTED`.
- Merge commit / `main`: `5cf50abcea849fe1edc6aa3e827258fd837f3d77`.
- Approved PR HEAD: `ed50fb1cdc6329b6a082a113d40f78a7594d3b2e`.
- Local 114-word RC recovery remains intact (account `id 1`; Guest JSON unchanged; outbox pending preserved).
- Client Sync 404 → **Server Sync unavailable** (session-scoped; new engine probes once).
- Cloud Sync **OFF**. No VPS/Sync flag change. No production EXE replace. No public Release.
- Isolated RC build is for **Owner smoke testing only**.
- **18C.1 / 18C.2 CLOSED**. **18B.9 PAUSED, NOT CLOSED**. Staging **RESERVED**. Sync pilot **NO-GO**.

## 2. Last results

- PR [#25](https://github.com/nguyenthaibinh19/EnglishApp/pull/25) merged to `main`.
- Focused regressions green at merge (`test_sync_unavailable_status`, `test_rc_smoke_isolation`).
- RC EXE (Owner smoke only): `dist-rc/langstudyguard-rc.exe` SHA-256 `01fa9a587f5040a025c65081bfe5ee5e7550b42dbd8d6568be86f16cd751fe6e`.

## 3. Next

1. Owner RC smoke with the isolated RC build (manual).
2. No further VPS changes unless Owner/Architect authorize.
3. Do not enable `STUDY_SYNC_ENABLED` or resume 18B.9 from this handoff.
4. Do not rerun the 114-word import or reset the RC account DB.

## 4. STOP / boundaries

- STOP after merge report — no new milestone.
