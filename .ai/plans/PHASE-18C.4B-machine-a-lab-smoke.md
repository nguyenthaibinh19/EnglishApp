# Phase 18C.4B — Machine A lab smoke

Status: **Machine A ready for Architect review** (`APP_18C4B_MACHINE_A_READY_FOR_ARCHITECT_REVIEW`)  
Date: 2026-11-23  
Authorization: `APP_18C4B_OWNER_AUTHORIZED_MACHINE_A_ONLY`  
Source: `24089334db501bacc5e87bfc1615e0dc5b5254a7`  
Safety correction: PR #29, merge `e5763ff08097c6bb62901f6a858eda355b26f97c`

Computer B was not contacted. No SSH tunnel was opened. Production Cloud Sync stayed OFF. The lab server was stopped after the smoke.

## 1. Baseline

- Branch `main`. HEAD and `origin/main` were `24089334db501bacc5e87bfc1615e0dc5b5254a7`.
- The merged `os.lstat` junction check is present in `deploy/hetzner/staging_guard.py`.
- Working tree before this checkpoint: only the untracked `diff/` directory.
- The original 18C.4A junction result remains a **FAIL**. This smoke used the corrected guard.
- Port `18765` was closed before startup.
- `D:\lg-18c4a-lab\package`, `sync`, `backup`, `verify`, `proof`, and `client-a` were ordinary directories.
- All 19 copied module hashes matched the source tree. No database file existed under the lab.

## 2. Guard and server

`staging_guard.validate(layout, require_env_file=True)` returned **PASS** before the process started. The process was `deploy/hetzner/staging_server.py` with `PYTHONPATH` set to the lab package only.

Proof `D:\lg-18c4a-lab\proof\effective-d0ad7fdfdb9c4d16a038f3979bd030e2.json`:

- bind `127.0.0.1`
- port `18765`
- base URL `http://127.0.0.1:9`
- staging fake key accepted
- `sync_enabled` true

Verbose import lines showed `account_server.py`, `account_store.py`, `config.py`, `sync_http.py`, and `sync_store.py` loading from `D:\lg-18c4a-lab\package`. `staging_guard.py` loaded from the merged source tree. No application module loaded from `app\`.

The listener was one socket: `127.0.0.1:18765`, process `37836`. No `0.0.0.0` listener was present.

## 3. Client isolation

The source tree `.env` contains a real provider key, an emergency password, and an account URL. A clean child environment set every one of those names before import. `load_dotenv()` did not replace them.

Effective client result:

- `config.py` from the source tree
- runtime `staging`
- build channel `production`, because `build_manifest.json` says production
- `LG_RC_SMOKE` absent
- data directory `D:\lg-18c4a-lab\client-a`
- account URL `http://127.0.0.1:18765`
- provider base URL `http://127.0.0.1:9`
- effective provider key was the staging fake key and differed from the file
- emergency password empty while the file value was non-empty
- account token empty
- `STUDY_SYNC_ENABLED` absent from the client
- `https://langstudyguard.com` refused
- `http://127.0.0.1:18765` allowed

No source change was required for that isolation.

## 4. Synthetic accounts

The copied `account_server.py add` command created the accounts in `D:\lg-18c4a-lab\package\accounts.db`. Passwords were generated in memory and were not written to the report.

| id | username | active |
|----|----------|--------|
| 1 | `lab18c4_user_a` | yes |
| 2 | `lab18c4_user_b` | yes |

Tables: `users`, `sessions`. No other account database was copied.

## 5. Loopback API

All calls used `http://127.0.0.1:18765`.

| Check | Result |
|-------|--------|
| `GET /` | 200, `ok` true |
| `POST /api/login` for user A | 200, username `lab18c4_user_a`, user id 1, token issued |
| `POST /api/session` | 200, same username and user id |
| `POST /api/sync/preferences/get` without a token | 401, `Authentication required.` |
| authenticated preferences get | 200, revision present, zero values |
| authenticated vocabulary changes | 200, zero changes |

`study_sync.db` was created only at `D:\lg-18c4a-lab\sync\study_sync.db`. No other lab database appeared.

## 6. Client A

The source `app\main.py` was launched without `--lock`. The sign-in dialog title was `Language Guard — STAGING`. Login through that dialog succeeded.

The home window then showed:

- `Language Guard — STAGING`
- signed in as `lab18c4_user_a` (id 1)
- environment `staging`, backend `127.0.0.1`
- Cloud Sync: Synced, server and client caught up
- the signed-in Dutch deck shown as empty

`settings.json` recorded username `lab18c4_user_a`, user id 1, environment `staging`, and a token. The token is not copied here. Account storage was created at `client-a\accounts\1\account_study.db`.

The client also wrote bundled starter files under `client-a\languages`. Dutch has 48 entries and is byte-identical to the source tree `data\vocab.json`. The other starters have 8 entries each. None match the recovered 114-word guest hash. No `attempts.jsonl` file was created. The home screen did not show those starter entries as the signed-in deck.

## 7. Shutdown and isolation

The client window was closed. The lab server process was stopped. Port `18765` was no longer listening.

Preserved: `accounts.db`, `study_sync.db`, and the proof file.

Unchanged metadata:

- `%APPDATA%\langstudyguard`
- `%APPDATA%\langstudyguard-rc`
- `%APPDATA%\langstudyguard-rc\accounts\1\account_study.db`
- `%LOCALAPPDATA%\LanguageGuard-Recovery`

## 8. Not tested

- Computer B
- SSH
- the six two-device scenarios
- production Cloud Sync, which remains OFF

## 9. Before computer B

- A separate authorization.
- Computer B on a trusted path, with its own `client-b` outside production, RC, and recovery data.
- An Owner-held SSH login to computer A and a local forward from `127.0.0.1:18765` on B to `127.0.0.1:18765` on A.
- Confirmation that the forward ends with the SSH session and that no public HTTP port is opened.
