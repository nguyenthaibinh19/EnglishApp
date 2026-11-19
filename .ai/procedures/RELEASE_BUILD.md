# Release / EXE build notes

## Channels (ADR-025)

| Channel | Script | Output | AppData |
|---------|--------|--------|---------|
| production | `build_exe.bat` | `dist/langstudyguard.exe` | `%APPDATA%\langstudyguard` |
| production RC | `build_production_rc.bat` | `dist-rc/langstudyguard-rc.exe` | `%APPDATA%\langstudyguard` |
| staging | `build_staging_exe.bat` | `dist-staging/langstudyguard-staging.exe` | `%APPDATA%\langstudyguard-staging` |

Production RC must not overwrite an existing Owner `dist/langstudyguard.exe`. Do not publish a public GitHub Release until separate approval. Upgrade: replace installed EXE after Owner acceptance; rollback: restore `.bak` / previous ZIP. **RC smoke** uses isolated `%APPDATA%\langstudyguard-rc` (not production AppData), keeps the production HTTPS backend, blocks the production auto-updater, and shows **PRODUCTION BACKEND · RC TEST DATA** — see [RC_SMOKE_PRODUCT_OWNER.md](RC_SMOKE_PRODUCT_OWNER.md). Genuine `langstudyguard.exe` install/update/AppData semantics stay unchanged when RC markers are absent.

Each build writes `build_manifest.json` (`channel`, `version`, `commit_sha`) and embeds it in the EXE. Staging bundling **never** embeds a production `ACCOUNT_SERVER_URL` from `.env` — it forces `http://127.0.0.1:8765`.

## Rules

- Do not overwrite a Product Owner–prepared production EXE with a staging build.
- Staging EXE must not auto-install over `%LOCALAPPDATA%\langstudyguard\`.
- Unknown/mismatched identity fails closed for network writes.
- Production Cloud Sync remains separately gated (`STUDY_SYNC_ENABLED`).

See [STAGING_EXE_PRODUCT_OWNER_GUIDE.md](STAGING_EXE_PRODUCT_OWNER_GUIDE.md).
