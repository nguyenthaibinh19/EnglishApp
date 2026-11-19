# ADR-025 — Environment Identity and Isolation

Status: **Proposed for Architect merge review** (PR #22; R1 safety fixes applied).

## Context

Phase 18C.1 and 18C.2 are CLOSED — Architect Accepted. An executable built from `main` is not automatically production. An executable pointed at localhost is not automatically staging-safe unless configuration and data storage are isolated.

Production Cloud Sync remains **OFF**. Phase 18B.9 remains **PAUSED, NOT CLOSED**.

**Product Owner decision (2026-11-19):** Staging is reserved for future use. Its EXE may be built and stored, but **no staging backend or user trial is activated now**. Near-term local testing uses isolated development / localhost configuration.

## Decision

Language Guard maintains **independent** facts:

1. **Build channel** — `development` | `staging` | `production` (from `build_manifest.json`)
2. **Runtime environment** — same vocabulary; frozen builds pin runtime to build channel
3. **Backend host** — validated separately against the identity
4. **Active account identity** — non-sensitive username / user id only in UI
5. **Data directory** — environment-specific AppData folder for frozen builds
6. **Cloud Sync status** — from the live sync engine only
7. **Version / commit SHA** — from the build manifest

### Permanent rules

- A Git branch does **not** determine deployment environment.
- An EXE filename alone does **not** determine environment.
- Build identity and runtime backend must be **independently verified**.
- Development and staging **cannot** silently connect to known production hosts.
- Staging data and credentials must be **isolated** (`%APPDATA%\langstudyguard-staging\`, `%LOCALAPPDATA%\langstudyguard-staging\`).
- Production data **cannot** be mutated by staging or development tests.
- `LG_DATA_DIR` overrides for non-production builds are validated: production AppData and production install directories (including overlaps) are **rejected**; isolated synthetic directories remain allowed for tests. Fail closed before writes/imports when validation fails.
- Account and sync HTTP clients **never follow redirects** with credentials, Bearer tokens, or learning payloads. A redirect `Location` aimed at a production or otherwise forbidden host is refused without contacting that host.
- Environment identity must be **visible before login** (setup/login window) and on StudyMaster (title + banner + Environment details).
- Unknown or mismatched identity **fails closed** for network writes.
- Cloud Sync must not be labeled `Synced` unless the engine confirmed catch-up.
- Future Cursor/Antigravity agents must follow these rules.

### Isolation map (frozen)

| Environment | Data | Install | EXE basename |
|-------------|------|---------|--------------|
| production | `%APPDATA%\langstudyguard` | `%LOCALAPPDATA%\langstudyguard` | `langstudyguard.exe` |
| staging | `%APPDATA%\langstudyguard-staging` | `%LOCALAPPDATA%\langstudyguard-staging` | `langstudyguard-staging.exe` |
| development | `%APPDATA%\langstudyguard-dev` | `%LOCALAPPDATA%\langstudyguard-dev` | `langstudyguard-dev.exe` |

Source `development` continues to use the repository root as `data_dir()` unless a validated `LG_DATA_DIR` is set.

Staging/development frozen builds **do not** auto-install into production LOCALAPPDATA and **do not** create `langstudyguard.lnk` Startup shortcuts.

Remote staging hosts require explicit `LG_TRUSTED_STAGING_HOSTS`.

## Consequences

- Staging EXE is built via `build_staging_exe.bat` into `dist-staging/` and must never overwrite `dist/langstudyguard.exe`.
- Account / sync HTTP clients call `assert_network_writes_allowed` before network I/O and use redirect-refusing openers.
- Stored sessions without a matching `environment` marker are adopted only by production.
- Production Cloud Sync flag and server configuration are unchanged by this ADR.
- Staging remains **inactive** for Product Owner trial until separately authorized.

## Related

- [ADR-018](ADR-018-account-cloud-sync.md), [ADR-022](ADR-022-event-first-automatic-account-sync.md), [ADR-023](ADR-023-windows-installation-safety.md)
- Product Owner guide: [../procedures/STAGING_EXE_PRODUCT_OWNER_GUIDE.md](../procedures/STAGING_EXE_PRODUCT_OWNER_GUIDE.md)
