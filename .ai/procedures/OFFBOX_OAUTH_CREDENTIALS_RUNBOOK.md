# Off-box production credentials / OAuth runbook

Status: **RUNBOOK ONLY — not executed.** Creates no credentials, clients, tokens, or Drive folders.
Does not authorize live Google API calls.

See the consolidated staged package: [OFFBOX_PRODUCTION_DEPLOYMENT_RUNBOOK.md](OFFBOX_PRODUCTION_DEPLOYMENT_RUNBOOK.md).

## Credential delivery contract (source-designed in R1; hardened in R2)

`APP_18B9_PRODUCTION_UPLOAD_ENTRYPOINT_R2` defines a **worker-only, least-privilege** input contract. This is the **delivery design**, not provisioning.

| LoadCredential name | Required for upload mode | Purpose |
|---|---|---|
| `oauth-refresh` | yes | Refresh token (existing unit directive) |
| `upload-activation` | yes (`authorized`) | Deliberate activation marker |
| `drive-folder-id` | yes | Production Drive folder id |
| `oauth-client-id` | yes | OAuth Desktop client id |
| `oauth-client-secret` | optional | Client secret when the Desktop client requires it |

Rules:

- Prefer systemd `LoadCredential=` / root-owned files under `/etc/language-guard/` (or equivalent).
- **Never** pass raw secrets via environment values, command-line arguments, unit text that embeds secret values, git, issues, or logs.
- Forbidden env knobs remain fail-closed: `LG_DRIVE_FOLDER`, `LG_UPLOAD_ENABLED`, `LG_OAUTH_*`, `LG_CLIENT_*`, `LG_REFRESH_TOKEN`.
- Default shipped worker unit still declares **only** `LoadCredential=oauth-refresh:…`. Extra activation credentials require an Owner-authorized drop-in after Architect merge + VPS install.
- Incomplete or invalid activation configuration fails **before** socket handoff, encryption, or network activity.
- Activation-related credential entries that are symlinks (including dangling), directories, or other non-regular types fail closed — never silent inactive fallback.
- Documented `LG_RESUME` values only: absent/empty or exact `1` (reject `0`/`true`/other).
- Lab External Testing refresh tokens are **not** production-durable.

Distinctions:

- **Contract designed** ≠ credentials installed on VPS.
- **Installed** ≠ enabled ≠ operational upload.

## Goals

- Dedicated production Google Cloud project (not External Testing lab client).
- OAuth scope exactly `https://www.googleapis.com/auth/drive.file`.
- Desktop client; refresh token root-owned at `/etc/language-guard/oauth-refresh` mode `0400`.
- Worker receives secrets only through systemd `LoadCredential=…`.
- Helper never sees tokens (`InaccessiblePaths` includes `/etc/language-guard` and `/run/credentials`).
- Age identity stays offline; VPS holds public `age1pq1` recipient only.

## Owner steps (manual, outside agents)

1. Create a production GCP project reserved for Language Guard off-box backup.
2. Configure OAuth consent for unattended production use (not 7-day External Testing).
3. Create a Desktop OAuth client; download client JSON to an owner-controlled offline store.
4. Perform consent once on an owner machine; store only the refresh token for VPS install.
5. Create or designate a Drive folder owned by the production identity; record folder id offline.
6. On a later authorized VPS write session: install recipient file, oauth-refresh, and (after R1 merge) client-id / optional client-secret / folder-id / upload-activation files with root ownership; do not place age identity on the VPS.
7. Do not enable the timer or mark Drive configured until the activation gate is accepted. Env toggles alone never authorize upload.

## Fail-closed expectations

- Missing `oauth-refresh` → worker unit must fail on start when LoadCredential is required, or fail closed inside the worker.
- Frozen `backup_worker.main()` with `LG_DRIVE_FOLDER` / `LG_UPLOAD_ENABLED` → exits `live-transport-disabled` (behavior preserved).
- Production wrapper without `upload-activation=authorized` (+ folder/client/refresh) → inactive encrypt-only path or ConfigError; no network transport.
- Inactive encrypt-only may leave attempt state `ENCRYPTED` but process exit is `3` (`INACTIVE_NOT_OFFBOX_EXIT`) — not off-box success.
- HTTP upload success alone cannot become `VERIFIED`; independent ciphertext download match is required.
- Fake or localhost `VERIFIED` must never flip the daily Drive line away from **NOT CONFIGURED**.

## Explicit non-goals

- No agent-created secrets in git.
- No token paste into issues, PR bodies, or chat logs.
- No DELETE/PATCH against Drive objects from this runbook.
- No claim that the R1 contract equals provisioned production credentials.
