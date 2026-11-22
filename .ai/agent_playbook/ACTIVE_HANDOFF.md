# Active handoff

Rolling coordination checkpoint. See [current_state.md](../current_state.md) and [APP-RC-ADD-WORD-SAVE.md](../plans/APP-RC-ADD-WORD-SAVE.md).

## 1. Checkpoint metadata

- Written: 2026-11-22 (PR #27 signed-in Add Word save **Architect Accepted — source merged**).
- Tag: `APP_RC_ADD_WORD_SAVE_FIX_ARCHITECT_ACCEPTED`.
- Merge commit: `6cfade645dbdd4fbddec9fb83d4d295e632b1e1b`.
- Approved PR HEAD: `26f9c90b465de2b265e79e0daf0832d6c58ab591`.
- Empty `example` on signed-in Add/Edit no longer raises `AttributeError`; Guest and Account share `VocabStore._merge_legacy_example_edit`.
- Local 114-word RC recovery remains intact (account `id 1`; outbox pending preserved; recovery backups untouched).
- Cloud Sync **OFF**. No VPS/Sync flag change. No production EXE replace. No public Release.
- Isolated RC build is for **Owner GUI smoke only**.
- **18C.1 / 18C.2 CLOSED**. **18B.9 PAUSED, NOT CLOSED**. Staging **RESERVED**. Sync pilot **NO-GO**.

## 2. Last results

- PR [#27](https://github.com/nguyenthaibinh19/EnglishApp/pull/27) merged to `main`.
- Focused regressions were green at review (`test_account_add_word_save`, signed-in study data, vocab identity). Architect accepted that evidence; CI was not independently rerun.
- RC EXE (Owner smoke only): `dist-rc/langstudyguard-rc.exe` SHA-256 `a55099f56099f6d0edbe1eb889cec7b68c288bba61f5551b75df0cf223d94831`. Built from the code fix; the following docs commit does not change runtime.

## 3. Next

1. Owner RC GUI smoke: signed-in Add Word with a blank example, Add Word with an example, edit, and duplicate rejection.
2. No further VPS changes unless Owner/Architect authorize.
3. Do not enable `STUDY_SYNC_ENABLED` or resume 18B.9 from this handoff.
4. Do not rerun the 114-word import or reset the RC account DB.

## 4. STOP / boundaries

- STOP after this merge report — no new milestone.
