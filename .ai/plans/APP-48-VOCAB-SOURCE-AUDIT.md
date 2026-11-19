# APP 48 Vocabulary Source Audit (Read-Only)

Status: **COMPLETE — read-only** (`APP_48_VOCAB_SOURCE_AUDIT_READY`).  
**No vocabulary, SQLite, settings, or account data was modified.**

| Field | Value |
|-------|--------|
| Date | 2026-11-20 |
| Owner context | RC login OK; account id **1**; Dutch library empty in signed-in UI |
| Expected | ~48 words |
| Cloud Sync | Production server flag **OFF**; UI showed **Pending** |

## Task A — Discovery results

### Best user vocabulary source

| Item | Value |
|------|--------|
| **Path** | `%APPDATA%\langstudyguard\languages\nl\vocab.json` |
| Size | 17268 bytes |
| mtime (UTC) | 2026-11-05T12:51:16Z |
| SHA-256 | `ca387ab1bf13a95dd39dd033b0034dfc498fd4fc0e7450ea260161a75d805946` |
| Valid Dutch entries (project schema) | **114** |
| Unique ids / words | 114 / 114 |
| Overlap with bundled starter word set | 47 |
| Non-starter (likely Owner-added) words | **67** |
| Verdict | **Best historical user library** (not starter-only) |

The Owner’s “about 48” figure matches the **bundled starter pack** size, not this production guest library. The live production guest file is larger (**114** valid entries).

### Exact 48-word files (bundled starter / copies)

These match starter content (`valid_entries=48`, `non_starter_words=0`):

| Path | SHA-256 | Note |
|------|---------|------|
| `D:\EnglishApp\data\vocab.json` | `ee9b49ae…48501c` | Canonical starter reference used for comparison |
| `%APPDATA%\langstudyguard\vocab.json` | `586e1325…109912` | Legacy root copy; starter-only |
| `%APPDATA%\DutchGuard\vocab.json` | same as above | Legacy brand folder |
| `%APPDATA%\langstudyguard-rc\languages\nl\vocab.json` | `ee9b49ae…48501c` | **RC Guest** seed (starter); not used while signed in |
| `D:\EnglishApp\languages\nl\vocab.json` | `fb51fa43…bcb8d9` | Repo language file; 48 starter words |

### Other user-like candidates

| Path | Valid entries | Non-starter | Note |
|------|---------------|-------------|------|
| `%APPDATA%\DutchGuard\languages\nl\vocab.json` | 82 | 35 | Older user library |
| `D:\EnglishApp\qa-backup-20261027-150944\appdata\languages\nl\vocab.json` | 112 | 65 | QA backup snapshot |

### Account SQLite stores

| Path | Finding |
|------|---------|
| `%APPDATA%\langstudyguard\accounts\` | **Absent** — no production AppData account SQLite |
| `%APPDATA%\langstudyguard-rc\accounts\1\account_study.db` | Present; SHA-256 `c32d494bcaf2f3886213dbb1436108fd7cb5bcebe839016edc33397476ec5fd5`; size 94208; mtime 2026-11-19T23:05:04Z |
| RC `vocabulary_entities` (nl, deleted=0) | **0** |
| RC `vocabulary_entities` (all languages, deleted=0) | **0** |
| RC `legacy_import_consent` | **empty** |
| RC sync meta | `vocab_caught_up=0`, `progress_caught_up=0`, `offline=0`, cursors `0` |
| DB open mode for audit | SQLite URI `mode=ro` only |

**Conclusion:** The expected learning vocabulary lives in **production Guest JSON**, not in any account SQLite. RC account 1 currently has **zero** vocabulary entities. No historical account DB on this PC holds those entries.

## Task B — RC data separation and import plan (no execution)

### How selection works

1. **Guest:** `study_data.open_study_data()` → `languages/{code}/vocab.json` under the active data root (`langstudyguard` production / `langstudyguard-rc` for RC).
2. **Signed-in:** same gateway binds `AccountVocabStore` → `AccountLocalStore` / `accounts/{user_id}/account_study.db`. Guest JSON is **not** read or dual-written.
3. **Never auto-import on login** (`study_data` docstring; ADR-022 / 18C.2).
4. Explicit consent path already exists:
   - `AccountLocalStore.grant_legacy_consent(language_code, source_kind="guest")`
   - `AccountLocalStore.import_guest_vocabulary(language_code, entries, require_consent=True)` — normalizes entries, **skips existing ids**, does not rewrite guest files
   - GUI: `legacy_import_app` + FreeHome/StudyMaster “Import guest”

### Why RC UI is empty after login

- Signed-in UI reads **account id 1 SQLite** (0 rows).
- RC Guest folder still has **48 starter** words, which are invisible while signed in.
- Production Guest library (**114**) lives under `%APPDATA%\langstudyguard\…` and is **isolated** from RC by ADR-025 / RC smoke design.

### Can production Guest JSON be imported into RC account 1?

**Yes, with Owner consent**, using the existing APIs:

- Destination is empty → no overwrite of account vocabulary rows.
- Import skips duplicate ids.
- Must **not** point the GUI at RC Guest starter alone if the goal is the 114-word library; pass entries loaded from the **approved production Guest path** (or a verified copy). Default `preview_guest_vocabulary()` under RC `data_root` would only show the 48 starters.

### Proposed one-time import procedure (NOT RUN)

1. **Owner approval:** Explicitly approve source  
   `%APPDATA%\langstudyguard\languages\nl\vocab.json` (114) → RC account **id 1**.
2. **Backups (preserve originals):**  
   - Copy source JSON to a timestamped backup outside live paths.  
   - Copy `%APPDATA%\langstudyguard-rc\accounts\1\account_study.db` similarly.  
   - Record SHA-256 of both.
3. **Import (future authorized step only):**  
   - Open `AccountLocalStore(1, data_root=RC AppData)`.  
   - `grant_legacy_consent("nl", "guest", note=owner-approved-source-path)`.  
   - Load/normalize JSON entries; `import_guest_vocabulary("nl", entries)`.  
   - Do **not** migrate Progress / attempts / SRS (18B.9 remains PAUSED).
4. **Verify:** account `list_vocabulary("nl")` count ≈ 114 (minus any skipped invalids); spot-check ids; UI refresh.
5. **Rollback:** restore backed-up `account_study.db`; leave source JSON untouched throughout.

## Task C — False Cloud Sync “Pending”

### Why the engine starts

`account_sync_bootstrap.maybe_start_account_sync()` starts the worker whenever:

- signed-in token + `user_id` exist, and  
- environment identity allows network writes to `ACCOUNT_SERVER_URL`,  

**without** checking server `STUDY_SYNC_ENABLED`.

RC production-channel identity allows HTTPS account backend → worker starts.

### Why the label becomes Pending

1. Fresh store meta: `vocab_caught_up=0`, `progress_caught_up=0` (observed on account 1).
2. `AccountLocalStore.status()` treats missing catch-up as **Pending** (“Upload or download in progress”).
3. Sync HTTP against production with flag OFF returns **404**.
4. `AccountSyncEngine.sync_once()` maps `SyncClientError` with status **404** neither to offline nor to a disabled state (only 401/403 → conflict; ≥500/None → offline). Catch-up flags stay `0` → UI remains **Pending**.

So: **404 from disabled sync endpoints + engine still running + catch-up unset ⇒ misleading Pending**, even though Cloud Sync is OFF.

### Proposed focused client fix (proposal only)

1. Treat sync HTTP **404** (and/or explicit disabled body) as **server sync unavailable/disabled**.
2. Stop or idle the engine; surface **“Signed in / Server Sync disabled”** (existing label path when `engine_running` is false), never Pending/Synced.
3. Optionally gate `maybe_start_account_sync` on a cheap capability probe / known-disabled marker.
4. Regressions: synthetic localhost returning 404 → UI label disabled, not Pending; flag ON path unchanged; guest label unchanged.

**Do not** set `STUDY_SYNC_ENABLED=1` or change VPS config for this.

## Boundaries confirmation

- Read-only investigation only.  
- No imports, deletions, EXE rebuild, VPS work, sync activation, or account identity changes.  
- ADR-025 Accepted; 18C.1/18C.2 CLOSED; 18B.9 PAUSED; Staging RESERVED; Cloud Sync OFF; sync pilot NO-GO.

## STOP

Await Architect review before any import or Pending-status code change.
