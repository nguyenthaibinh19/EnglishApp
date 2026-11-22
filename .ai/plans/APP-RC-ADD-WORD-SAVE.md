# APP — RC signed-in Add Word save fix

Status: **CLOSED — Owner GUI smoke accepted** (`APP_RC_ADD_WORD_SAVE_FIX_CLOSED_OWNER_ACCEPTED`)  
Baseline: `main` `c1ce12eb6df0da1550702e4fd05226753972ec3e`  
PR: [#27](https://github.com/nguyenthaibinh19/EnglishApp/pull/27) **MERGED** (approved HEAD `26f9c90b465de2b265e79e0daf0832d6c58ab591`)  
Merge commit: `6cfade645dbdd4fbddec9fb83d4d295e632b1e1b`  
`main` at acceptance docs: `623847c9549832b5821566028055739d86094a29`  
Cloud Sync: **OFF**  
18B.9: **PAUSED, NOT CLOSED** · Staging: **RESERVED** · Sync pilot: **NO-GO**  
Next: **none** — no new milestone from this closure.

## Root cause

`VocabularyLibraryApp._edit_dialog.save` always passes `example`, including `""`.

`AccountVocabStore._optional_from_extra()` calls `VocabStore._optional_from_extra(self, ...)`, which invoked `self._merge_legacy_example_edit`. That method exists only on `VocabStore`, so signed-in Add/Edit raised:

`AttributeError: 'AccountVocabStore' object has no attribute '_merge_legacy_example_edit'`

The failed call returned before `upsert_vocabulary`, so the account SQLite transaction stayed unchanged.

## Fix

- Call `VocabStore._merge_legacy_example_edit` so Guest and Account stores share the same example merge.
- `commit_vocab_edit()` surfaces duplicate and persistence failures and leaves the dialog open.
- Successful library save reloads the list and refreshes FreeHome via `on_saved`.

## RC smoke build

| Item | Value |
|------|--------|
| Path | `D:\EnglishApp-worktrees\env-isolation\dist-rc\langstudyguard-rc.exe` |
| SHA-256 | `a55099f56099f6d0edbe1eb889cec7b68c288bba61f5551b75df0cf223d94831` |
| Owner RC Dutch / pending | **114 / 114** (unchanged) |
| Recovery backup | Intact |
| Production `dist/langstudyguard.exe` | Not present / not modified |

## Owner RC GUI smoke

Owner confirmed on 2026-11-22 that all RC GUI smoke checks for PR #27 **PASSED**.

Signed-in Add Word with a blank example, Add Word with an example, edit, and duplicate rejection are accepted. Original RC account data and recovery backups were not modified for this closure.

## Boundaries

No VPS, no `STUDY_SYNC_ENABLED`, no re-import, no RC DB reset, no production EXE, no public Release.
