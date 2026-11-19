# APP — RC FreeHome Cloud Sync stale label correction

Status: **Ready for Architect review** (`APP_RC_FREEHOME_SYNC_LABEL_FIX_READY`)  
Baseline: `main` `a2660f0e4bdd649efe37e5731e721de35ecf1e77` (PR #25 merged)  
PR: [#26](https://github.com/nguyenthaibinh19/EnglishApp/pull/26)  
Cloud Sync: **OFF**

## Task A — Read-only diagnosis

| Check | Result |
|-------|--------|
| Running processes | `langstudyguard-rc.exe` ×2 |
| Running EXE path | `D:\EnglishApp-worktrees\account-ux-rc\dist-rc\langstudyguard-rc.exe` |
| Running EXE SHA-256 | `352fbda878557a33f66c71447ff701966d832972fc157c13b06aa217dc9eb701` |
| Approved RC SHA-256 | `01fa9a587f5040a025c65081bfe5ee5e7550b42dbd8d6568be86f16cd751fe6e` |
| Match approved? | **No — outdated EXE** |
| RC DB | `%APPDATA%\langstudyguard-rc\accounts\1\account_study.db` |
| `server_sync_unavailable` | **absent / unset** |
| Pending outbox | **114** |
| Live Dutch vocab | **114** |

### Root cause (Owner symptom)

The Owner screenshot was taken with an **outdated** RC EXE (pre–PR #25 Sync 404 handling). That binary never recorded `server_sync_unavailable`, so FreeHome correctly showed **Pending** for 114 pending outbox rows.

### Latent UI gap (still fixed)

Even with the approved PR #25 EXE, FreeHome only refreshed AccountPanel on login/logout/switch — not after the background worker’s first Sync 404. StudyMaster already polls every 5s. FreeHome lacked that loop.

## Task B — Fix

| Path | Change |
|------|--------|
| `app/account_panel.py` | `AccountSyncStatusPoller` — Tk `after` loop; UI-only `AccountPanel.refresh()` |
| `app/home_app.py` | Start poller on FreeHome; stop on destroy / leave to StudyMaster; no second loop on account switch |
| `tests/test_freehome_sync_label_refresh.py` | Pending→unavailable after synthetic 404; no duplicate loops; destroy/stop; StudyMaster loop unchanged; no Sync HTTP on UI refresh |

## Task D — RC rebuild (Owner smoke only)

| Item | Value |
|------|--------|
| Path | `D:\EnglishApp-worktrees\env-isolation\dist-rc\langstudyguard-rc.exe` |
| SHA-256 | `26df6fafd7be7e4bcd808765faf07a06cf309c58dc34663df4c81150926bbbc6` |
| Data root | `%APPDATA%\langstudyguard-rc` |
| Dutch vocab / pending outbox | **114 / 114** (unchanged) |
| Recovery backups | Intact under `%LOCALAPPDATA%\LanguageGuard-Recovery\vocab-114-20261119-232144\` |
| Production `dist/langstudyguard.exe` | Not modified |

**Owner action:** close the outdated `account-ux-rc` RC processes, then run this new `dist-rc` EXE for smoke.

## Boundaries

No re-import, Guest edits, RC DB reset, VPS, Sync ON, production EXE, public Release, Progress/SRS migration.
