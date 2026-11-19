# Production RC — Product Owner safe smoke path

Explicit **RC smoke mode** avoids production auto-install and Startup registration.
Genuine `langstudyguard.exe` install semantics are unchanged when RC markers are absent.

## RC markers (any one)

1. EXE basename starts with `langstudyguard-rc` (default output of `build_production_rc.bat`)
2. CLI flag `--rc-smoke`
3. Environment `LG_RC_SMOKE=1`

Detection: `install.is_release_candidate_smoke()` → `prepare()` seeds vocab and returns True **in place** (no copy into `%LOCALAPPDATA%\langstudyguard\`, no Startup `--lock` shortcut).

## First-run behavior (documented)

| Machine state | Running | What happens |
|---------------|---------|--------------|
| Clean Windows PC, no Language Guard | `dist-rc\langstudyguard-rc.exe` | Runs from the RC path; creates/uses production AppData folder `%APPDATA%\langstudyguard` (ADR-025 production channel). **Does not** install to LocalAppData or register Startup. |
| PC with Language Guard already installed | `langstudyguard-rc.exe` | Same in-place run. **Does not** overwrite the installed EXE or rewrite Startup. Existing production install remains intact. |
| Clean PC | genuine `langstudyguard.exe` (future approved release) | Unchanged first-install: copy + Startup `--lock` when no prior install. |

## Safe Owner smoke checklist (second PC)

1. Copy only `dist-rc\langstudyguard-rc.exe` (or the ZIP) — do **not** replace any installed production EXE.
2. Double-click the RC EXE (basename already enables smoke mode). Optional: set `LG_RC_SMOKE=1` or pass `--rc-smoke`.
3. No Python, Conda, or localhost backend required — account/login APIs use the production HTTPS backend from the production channel manifest.
4. Confirm window chrome shows production environment identity (ADR-025) and data stays under `%APPDATA%\langstudyguard`.
5. Confirm Cloud Sync stays **OFF** / not “Synced” (production `STUDY_SYNC_ENABLED` unset → pilot **NO-GO**).
6. Confirm no new `langstudyguard.lnk` with `--lock` appeared under Startup during the smoke.
7. Log in / switch / log out with ordinary test accounts only.

## Boundaries

- Do not enable production Cloud Sync.
- Do not publish a public GitHub Release from this RC.
- Rebuild RC only into `dist-rc/` — never overwrite Owner `dist\langstudyguard.exe` / ZIP / `.bak`.
