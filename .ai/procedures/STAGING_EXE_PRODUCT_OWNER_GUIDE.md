# Product Owner — Staging EXE launch guide

Short checklist for Language Guard **staging** without touching production data.

**Owner decision (2026-11-19):** Staging is reserved for future use. The staging EXE may be built and stored, but **no staging backend or user trial is activated now**. Near-term local testing should use an isolated **development / localhost** configuration instead.

## What to open (when staging trial is later authorized)

Use the staging binary only:

`D:\EnglishApp-worktrees\env-isolation\dist-staging\langstudyguard-staging.exe`

Do **not** replace or delete:

- `D:\EnglishApp\dist\langstudyguard.exe`
- `D:\EnglishApp\dist\langstudyguard.zip`
- `D:\EnglishApp\dist\langstudyguard.exe.bak-*`

## What you should see immediately

- Window title: **Language Guard — STAGING**
- Banner: **STAGING — test data only**
- **Environment…** dialog shows: build channel `staging`, git SHA, backend host (localhost), data directory under `langstudyguard-staging`, Cloud Sync status that is **not** a guessed “Synced”

## Isolation guarantees

| Concern | Staging behavior |
|---------|------------------|
| Learner data | `%APPDATA%\langstudyguard-staging\` |
| Install copy | Does **not** auto-install over production `%LOCALAPPDATA%\langstudyguard\` |
| Startup | Does **not** create/change `langstudyguard.lnk` |
| Production token | Not loaded from `%APPDATA%\langstudyguard\settings.json` |
| Production host | Authenticated calls to `langstudyguard.com` are refused |
| Guest import | Only guest files inside the staging data folder (empty until you create them) |

## Backend limitation

If no staging account server is running, use a **localhost** test server (`http://127.0.0.1:8765`). This guide does not authorize contacting the live production backend.

Cloud Sync production remains **OFF**. A staging EXE that cannot verify the server feature flag should show Disabled / Unavailable / Unknown — not Synced.

## Smoke steps

1. Launch `langstudyguard-staging.exe` (SmartScreen may warn — unsigned).
2. Open **Environment…** and confirm channel, SHA, backend host, data directory.
3. Confirm `%APPDATA%\langstudyguard\` files are unchanged (timestamps / hashes).
4. Sign in only with **synthetic** staging credentials on localhost.
5. Confirm Guest / ScreenGuard still work in staging.
6. Stop. Do not merge or deploy without Architect review.

## Status preserved

- 18C.1 CLOSED
- 18C.2 CLOSED
- 18B.9 PAUSED, NOT CLOSED
- Production Cloud Sync OFF
