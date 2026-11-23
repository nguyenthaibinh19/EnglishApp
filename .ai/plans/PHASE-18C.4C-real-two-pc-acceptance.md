# Phase 18C.4C — Real two-PC acceptance

Status: **BLOCKED** (`APP_18C4C_BLOCKED`)  
Date: 2026-11-23  
Authorization: `APP_18C4C_OWNER_AUTHORIZED_REAL_TWO_PC_TEST`  
Source checked: `1ba2c622bb57ecb9864a35fbde318fd83f8522e7`  
Safety correction: PR #29, merge `e5763ff08097c6bb62901f6a858eda355b26f97c`

18C.4A and 18C.4B are Architect Accepted / CLOSED by the authorization for this phase. The six two-PC scenarios were not started. Production Cloud Sync stays OFF.

## 1. Machine A preflight

| Check | Result |
|-------|--------|
| Branch, HEAD, `origin/main` | `main` at `1ba2c622bb57ecb9864a35fbde318fd83f8522e7` |
| Worktree | Untracked `diff/` only |
| PR #29 ancestor | Present. `os.lstat` fail-closed check is in `staging_guard.py` |
| Lab directories | `package`, `sync`, `backup`, `verify`, `proof`, `client-a` are ordinary directories |
| Copied module hashes | 19 of 19 match the source tree |
| Module resolution | `account_store` and `sync_http` resolve inside `D:\lg-18c4a-lab\package` |
| Guard | **PASS** for `127.0.0.1:18765`, sync flag `1`, fake key, empty account token |
| Port `18765` | Not listening |
| `accounts.db` | Users `lab18c4_user_a` id 1 and `lab18c4_user_b` id 2, both active. One session row. No other user tables |
| `study_sync.db` | Zero vocabulary entities, vocabulary changes, learning attempts, progress rows, and progress changes |
| Client A settings | Username `lab18c4_user_a`, user id 1, environment `staging`. Token present and not copied here |

The lab databases were not reset. The server was not started.

## 2. Blocker

No working trusted SSH path is available from this session.

- The OpenSSH client is installed. No `ssh` process is running.
- `sshd` is not installed. This phase does not authorize installing or reconfiguring an SSH service, changing firewall rules, or bypassing host-key checks.
- There is no SSH config on this account.
- No second physical computer, `client-b` directory, or tunnel evidence was supplied.
- The plaintext password for `lab18c4_user_a` from 18C.4B was never stored. It is not available to this session. It was not reset, printed, or sent anywhere.

The connection gate therefore does not pass. Scenarios 1–6 are **BLOCKED**, not FAIL.

## 3. What the Owner needs before a rerun

1. A second physical Windows computer with a clean source checkout of the approved Account Sync implementation.
2. `client-b` outside that computer's production, RC, repository, and recovery paths.
3. An existing trusted LAN or private VPN path, and an SSH login the Owner already controls. The forward must be `B:127.0.0.1:18765` to `A:127.0.0.1:18765`.
4. The synthetic password entered by the Owner on B. If the Owner no longer has it, reset only `lab18c4_user_a` on A through the copied package command `python account_server.py password lab18c4_user_a`, at a private prompt. Do not paste the password into chat or GitHub.

## 4. Not done

- Lab server restart
- Client A relaunch
- SSH tunnel
- Computer B
- Scenarios 1–6
- Production, RC, VPS, or Google Drive changes
