# Off-box production credentials / OAuth runbook

Status: **RUNBOOK ONLY — not executed.** Creates no credentials, clients, tokens, or Drive folders.
Does not authorize live Google API calls.

See the consolidated staged package: [OFFBOX_PRODUCTION_DEPLOYMENT_RUNBOOK.md](OFFBOX_PRODUCTION_DEPLOYMENT_RUNBOOK.md). Lab External Testing refresh tokens are **not** production-durable. In addition to `oauth-refresh`, production exchange needs a client ID and may need a client secret; least-privilege delivery of those parameters is **not designed** yet (no raw secrets in environment, unit text, git, or issues).

## Goals

- Dedicated production Google Cloud project (not External Testing lab client).
- OAuth scope exactly `https://www.googleapis.com/auth/drive.file`.
- Desktop client; refresh token root-owned at `/etc/language-guard/oauth-refresh` mode `0400`.
- Worker receives the token only through systemd `LoadCredential=oauth-refresh:...`.
- Helper never sees the token (`InaccessiblePaths` includes `/etc/language-guard` and `/run/credentials`).
- Age identity stays offline; VPS holds public `age1pq1` recipient only.

## Owner steps (manual, outside agents)

1. Create a production GCP project reserved for Language Guard off-box backup.
2. Configure OAuth consent for unattended production use (not 7-day External Testing).
3. Create a Desktop OAuth client; download client JSON to an owner-controlled offline store.
4. Perform consent once on an owner machine; store only the refresh token for VPS install.
5. Create or designate a Drive folder owned by the production identity; record folder id offline.
6. On a later authorized VPS write session: install recipient file and oauth-refresh with root ownership; do not place age identity on the VPS.
7. Do not set `LG_DRIVE_FOLDER` or `LG_UPLOAD_ENABLED` until the activation gate is accepted.

## Fail-closed expectations

- Missing `oauth-refresh` → worker unit must fail on start (LoadCredential required).
- Worker with `LG_DRIVE_FOLDER` / `LG_UPLOAD_ENABLED` set while live transport is still gated → process exits failed (`live-transport-disabled`).
- Fake or localhost `VERIFIED` must never flip the daily Drive line away from **NOT CONFIGURED**.

## Explicit non-goals

- No agent-created secrets in git.
- No token paste into issues, PR bodies, or chat logs.
- No DELETE/PATCH against Drive objects from this runbook.
