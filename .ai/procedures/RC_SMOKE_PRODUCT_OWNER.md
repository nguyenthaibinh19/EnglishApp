# Production RC — Product Owner safe smoke path

Explicit **RC smoke mode** is independent of the production build channel:

- Uses the production HTTPS account/AI backend (login tests work).
- Requires an explicit isolated data root in `LG_DATA_DIR`. It does not use `%APPDATA%\langstudyguard-rc`.
- Never auto-installs, never registers Startup `--lock`, never runs the production auto-updater.
- Window title / banner: **PRODUCTION BACKEND · RC TEST DATA** (not a fully activated production release).

Genuine `langstudyguard.exe` install / update / AppData behavior is unchanged when RC markers are absent.

## RC markers (any one)

1. EXE basename starts with `langstudyguard-rc` (default output of `build_production_rc.bat`)
2. CLI flag `--rc-smoke`
3. Environment `LG_RC_SMOKE=1`

Detection: `app_environment.is_release_candidate_smoke()` — resolved **before** settings and data paths initialize.

## Data isolation

RC smoke validates `LG_DATA_DIR` before settings are loaded and before Sync Engine starts. A missing or invalid root stops the process. It does not open a stored session, a database, or network synchronization.

Refused for ordinary RC smoke, including a path that overlaps or redirects to them:

- `%APPDATA%\langstudyguard-rc`
- `%APPDATA%\langstudyguard`
- `%LOCALAPPDATA%\langstudyguard`
- `%LOCALAPPDATA%\LanguageGuard-Recovery`

A genuine `langstudyguard.exe` without RC markers still uses its production AppData directory and does not require `LG_DATA_DIR`.

The already-built v1.5.0 candidate does not contain this check. Start that binary only through `D:\EnglishApp\.local\labs\18d1\launch_rc_smoke.py`. The launcher applies the same refusals and also requires the data root to be a directory under `D:\EnglishApp\.local\data`. It refuses the 18D.1 incident root `.local\data\18d1-v1.5.0-rc`.

| Path | Production | RC smoke |
|------|------------|----------|
| Data root | `%APPDATA%\langstudyguard` | Explicit `LG_DATA_DIR` only |
| Default RC AppData | Not used | **Refused** |
| Settings marker | `production` (or legacy unmarked) | `production-rc` only |
| Adopt production tokens | Yes (genuine prod only) | **Never** |
| Auto-import / migrate prod data | N/A | **Never** |
| `LG_DATA_DIR` → production AppData, install, or recovery | Allowed for prod EXE when it is that EXE's own root | **Refused** |

## First-run behavior

| Machine state | Running | What happens |
|---------------|---------|--------------|
| Any PC | RC smoke without an approved `LG_DATA_DIR` | Stops before settings, databases, install, or sync. |
| PC with Language Guard installed | RC smoke with an approved isolated root | Uses only that root. Does **not** read, copy, or overwrite production settings, Guest data, account SQLite, the protected RC account, installed EXE, Startup, or updater state. |
| Clean PC | genuine `langstudyguard.exe` | Copies into the production install directory and does not create Startup `--lock` until the local emergency code is acknowledged. An existing shortcut is left unchanged. `--lock` does not engage until that acknowledgement. |

## Safe Owner smoke checklist (second PC)

1. Copy only `dist-rc\langstudyguard-rc.exe` (or ZIP) — do **not** replace any installed production EXE.
2. Start it with an explicit isolated `LG_DATA_DIR` that is not a protected directory above. For the already-built v1.5.0 candidate, use the guarded launcher and do not double-click the EXE.
3. No Python, Conda, or localhost backend required — account/login APIs use the production HTTPS backend from the production channel manifest.
4. Confirm chrome shows **PRODUCTION BACKEND · RC TEST DATA**.
5. Confirm data is only under the approved `LG_DATA_DIR`. Production `%APPDATA%\langstudyguard` and `%APPDATA%\langstudyguard-rc` stay unchanged.
6. Confirm Cloud Sync stays **OFF** / not “Synced” unless a separate decision authorizes it.
7. Confirm no production updater prompt and no new Startup `langstudyguard.lnk`.
8. Log in / switch / log out — session is stored only in the approved RC settings file.

## Boundaries

- Do not enable production Cloud Sync.
- Do not publish a public GitHub Release from this RC.
- Rebuild RC only into `dist-rc/` — never overwrite Owner `dist\langstudyguard.exe` / ZIP / `.bak`.
