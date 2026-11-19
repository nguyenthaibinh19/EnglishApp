# Production RC — Product Owner safe smoke path

Explicit **RC smoke mode** is independent of the production build channel:

- Uses the production HTTPS account/AI backend (login tests work).
- Uses **isolated** AppData: `%APPDATA%\langstudyguard-rc` (never production `%APPDATA%\langstudyguard`).
- Never auto-installs, never registers Startup `--lock`, never runs the production auto-updater.
- Window title / banner: **PRODUCTION BACKEND · RC TEST DATA** (not a fully activated production release).

Genuine `langstudyguard.exe` install / update / AppData behavior is unchanged when RC markers are absent.

## RC markers (any one)

1. EXE basename starts with `langstudyguard-rc` (default output of `build_production_rc.bat`)
2. CLI flag `--rc-smoke`
3. Environment `LG_RC_SMOKE=1`

Detection: `app_environment.is_release_candidate_smoke()` — resolved **before** settings and data paths initialize.

## Data isolation

| Path | Production | RC smoke |
|------|------------|----------|
| AppData | `%APPDATA%\langstudyguard` | `%APPDATA%\langstudyguard-rc` |
| Settings marker | `production` (or legacy unmarked) | `production-rc` only |
| Adopt production tokens | Yes (genuine prod only) | **Never** |
| Auto-import / migrate prod data | N/A | **Never** |
| `LG_DATA_DIR` → production AppData/install | Allowed for prod EXE | **Refused** |

## First-run behavior

| Machine state | Running | What happens |
|---------------|---------|--------------|
| Clean Windows PC | `dist-rc\langstudyguard-rc.exe` | Creates/uses `%APPDATA%\langstudyguard-rc` only. No LocalAppData install, no Startup. |
| PC with Language Guard installed | `langstudyguard-rc.exe` | Same isolated RC folder. Does **not** read, copy, or overwrite production settings, Guest data, account SQLite, installed EXE, Startup, or updater state. |
| Clean PC | genuine `langstudyguard.exe` | Unchanged first-install: copy + Startup `--lock` when no prior install; production AppData. |

## Safe Owner smoke checklist (second PC)

1. Copy only `dist-rc\langstudyguard-rc.exe` (or ZIP) — do **not** replace any installed production EXE.
2. Double-click the RC EXE (basename enables smoke mode). Optional: `LG_RC_SMOKE=1` or `--rc-smoke`.
3. No Python, Conda, or localhost backend required — account/login APIs use the production HTTPS backend from the production channel manifest.
4. Confirm chrome shows **PRODUCTION BACKEND · RC TEST DATA**.
5. Confirm data under `%APPDATA%\langstudyguard-rc` only; production `%APPDATA%\langstudyguard` unchanged if it already existed.
6. Confirm Cloud Sync stays **OFF** / not “Synced” (production `STUDY_SYNC_ENABLED` unset → pilot **NO-GO**).
7. Confirm no production updater prompt and no new Startup `langstudyguard.lnk`.
8. Log in / switch / log out — session is stored only in the RC settings file.

## Boundaries

- Do not enable production Cloud Sync.
- Do not publish a public GitHub Release from this RC.
- Rebuild RC only into `dist-rc/` — never overwrite Owner `dist\langstudyguard.exe` / ZIP / `.bak`.
