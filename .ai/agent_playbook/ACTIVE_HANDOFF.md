# Active handoff

Rolling coordination checkpoint. See [current_state.md](../current_state.md) and [APP-RC-FREEHOME-SYNC-LABEL.md](../plans/APP-RC-FREEHOME-SYNC-LABEL.md).

## 1. Checkpoint metadata

- Written: 2026-11-20 (PR #26 FreeHome Sync-label **Architect Accepted — source merged**).
- Tag: `APP_RC_FREEHOME_SYNC_LABEL_MERGED_ACCEPTED`.
- Merge commit / `main`: `693cc72195fe53bb424a1aa39f528fc9a8298321`.
- Final PR HEAD: `7940509eade0353b4d5d6c92504df175a65bb091`.
- FreeHome polls AccountPanel Cloud Sync on the Tk main thread; panel-frame Destroy cleanup (no root handler stack).
- Local 114-word RC recovery remains intact (account `id 1`; outbox pending preserved; recovery backups untouched).
- Cloud Sync **OFF**. No VPS/Sync flag change. No production EXE replace. No public Release.
- Isolated RC build is for **Owner smoke testing only** (close outdated `account-ux-rc` EXE first).
- **18C.1 / 18C.2 CLOSED**. **18B.9 PAUSED, NOT CLOSED**. Staging **RESERVED**. Sync pilot **NO-GO**.

## 2. Last results

- PR [#26](https://github.com/nguyenthaibinh19/EnglishApp/pull/26) merged to `main` (follows PR #25).
- Focused regressions green (`test_freehome_sync_label_refresh`, sync-unavailable, RC isolation).
- RC EXE (Owner smoke only): `dist-rc/langstudyguard-rc.exe` SHA-256 `cc9cff172f1ae5fdf6f505e440cd7b9411d06538f8202a9a08e662209df9bc4b`.

## 3. Next

1. Owner RC smoke with the post-merge isolated RC build (manual).
2. No further VPS changes unless Owner/Architect authorize.
3. Do not enable `STUDY_SYNC_ENABLED` or resume 18B.9 from this handoff.
4. Do not rerun the 114-word import or reset the RC account DB.

## 4. STOP / boundaries

- STOP after merge report — no new milestone.
