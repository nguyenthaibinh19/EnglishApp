# Phase 18C.4 — Two-device sync acceptance

Status: **Ready for Architect review** (`APP_18C4_READY_FOR_ARCHITECT_REVIEW`)  
Owner priority: working Account Sync between two real Windows computers, before production backup work or unrelated features.  
Date: 2026-11-23  
Cloud Sync production: **OFF** · 18B.9: **PAUSED, NOT CLOSED** · Staging on the VPS: **RESERVED** · Sync pilot: **NO-GO**

This document is the readiness and test plan. It does not start a server, build an EXE, change application source, or run the two-computer test.

## 1. Baseline

| Check | Result |
|-------|--------|
| Named application baseline | `d6578c0f579d7ee9bd02aec855193339a7d8c124` |
| `main` at inspection | `46e84f869aae1501f16a5b05116fbb81112939bf` |
| Difference | The later commit is the 18B.10A documentation audit only. Account Sync source is the named baseline. |
| Closed product slices | 18C.1, 18C.2, and 18C.3B. Do not rebuild them. |
| 18B.10A | Recorded audit. Not the active priority. Its rate-limit and quota work is not a prerequisite for this acceptance. |

No sync suite was rerun. No Owner data was opened.

## 2. What already supports the scenario

The in-process two-device tests are not this acceptance. They do show that the same components are the ones a real pair of computers would use.

| Behavior | Where it already lives |
|----------|------------------------|
| Signed-in vocabulary, attempts, Progress, and SRS push and pull | `account_sync_engine.sync_once`: vocabulary pull, vocabulary push, progress push, progress pull, preferences |
| Worker starts on launch, login, and account switch | `main.py`, `account_session.commit_session`, `account_sync_bootstrap.maybe_start_account_sync` |
| Local mutation wakes the worker; otherwise it polls every 60 seconds | `notify_local_change`, `poll_seconds=60` |
| Offline, then retry | Network and HTTP 500 set offline and use backoff, capped at 60 seconds. The outbox stays pending. |
| Same account, two stores | `tests/test_account_ux_two_device.py` scenarios A and B, in one process |
| Quiz attempt and SRS cross a simulated second store | `test_scenario_b_learning_attempts_progress_srs_mistake_book` |
| Vocabulary conflict is explicit Keep local / Keep server | `sync_conflict_app.py`. Status text points at Sync conflicts. No silent last-write-wins. |
| Restart keeps the account database | Logout keeps the local SQLite file. The session token is in that environment's `settings.json`. Launch calls `maybe_start_account_sync`. |
| Other account is isolated | Separate per-user SQLite files. Scenario A covers this in one process. |
| Guest files are not uploaded on login | `maybe_start_account_sync` returns immediately when there is no token. |
| Production host refusal | A development or staging identity cannot send an authenticated call to `langstudyguard.com` or any subdomain. |
| Server flag | Sync routes exist only when that server process has `STUDY_SYNC_ENABLED` exactly `1`. Otherwise they return 404 and the client shows Sync unavailable. |

The 60-second poll is the receiving computer's wait. Saving on one computer wakes only that computer's worker.

## 3. How both computers reach one backend

The production VPS is not the backend for this test. `deploy/hetzner/staging_guard.py` allows `ACCOUNT_BIND=127.0.0.1` only and refuses port `8765`. A development or staging client may call loopback without extra host trust. Any other host requires `LG_TRUSTED_STAGING_HOSTS`, which is a separate trust decision.

Safe shape that uses those rules and does not publish a service:

1. One lab process on computer A, bound to `127.0.0.1` and port `18765`.
2. Computer A's app uses `http://127.0.0.1:18765`.
3. Computer B reaches that process through an SSH local forward to B's own loopback, then uses `http://127.0.0.1:18765` as well.

The Bearer token then stays inside localhost on A and inside the SSH tunnel on B. No public port, no VPS unit, and no change to `LG_TRUSTED_STAGING_HOSTS`. Creating that tunnel, and turning the lab flag on, waits for a separate authorization. This plan does not open either one.

Unplugging computer A's Ethernet does not make A's own client offline, because A talks to localhost. The offline scenario belongs to computer B, by closing the tunnel. Stopping the lab process makes both clients offline and is the reconnect check for A.

`langstudyguard.exe` and `langstudyguard-rc.exe` are the wrong clients. The RC smoke identity keeps the production channel and the production account host, with data under `%APPDATA%\langstudyguard-rc`. This test uses a source tree on both computers, commit `d6578c0f579d7ee9bd02aec855193339a7d8c124` or a later commit that does not change Account Sync source.

## 4. Minimum missing work

No application change is required for the first live test if the lab below is authorized.

| Gap | Why it blocks a real pair | Who closes it |
|-----|---------------------------|---------------|
| No isolated server is running | Both apps currently target `http://127.0.0.1:8765` or whatever the developer `.env` already has. Production sync is off, so a client that hits production gets 404. | Later authorized lab on computer A only |
| Second computer has no path to that server | Loopback on B is not A's loopback | Owner, SSH forward, after authorization |
| Second computer needs this source tree and the same Python launch | A production or RC EXE must not be used | Owner copies the source checkout. No new EXE in this phase |
| Lab directories do not exist yet | A source run without `LG_DATA_DIR` writes the development data into the repository tree | Created only when the test is authorized, outside AppData and outside the repo |
| Evidence sheet | Pass/fail has to be written without tokens or Owner data | Filled during the authorized test |

18B.10A quotas are not in this list. A few synthetic rows will not decide that audit.

## 5. Lab configuration

Do not perform this section until authorization. Do not point it at the VPS.

Computer A holds three new directories, all outside the repository, `%APPDATA%\langstudyguard`, `%APPDATA%\langstudyguard-rc`, `%APPDATA%\langstudyguard-staging`, and `%LOCALAPPDATA%\LanguageGuard-Recovery`:

- `lab\server` — `accounts.db`, `study_sync.db`, and the lab `.env`
- `lab\client-a` — `LG_DATA_DIR` for the first app
- The second computer uses its own `lab\client-b`

Server process on A, and nowhere else:

- `ACCOUNT_BIND=127.0.0.1`
- `ACCOUNT_PORT=18765`
- `STUDY_SYNC_ENABLED=1`
- `STUDY_SYNC_DIR` = the new `lab\server` directory
- `OPENAI_API_KEY=staging-fake-not-a-provider-key`
- `OPENAI_BASE_URL=http://127.0.0.1:9`
- Account database path overridden to `lab\server\accounts.db` for that process only

Set those in the server shell before launch. `load_dotenv()` does not override variables already present, so a developer `.env` must not be able to replace them. Run `staging_guard.validate` against that layout first. The guard must accept it: loopback bind, port not `8765`, fake key, and paths that are not `/opt/language-guard` or `/var/backups/language-guard`. The guard does not start the server.

Create one synthetic user with the lab `account_server.py add` command. The username must not be an existing Owner account. The password stays in the Owner's password manager for the test and is not written into the plan, the repo, or a log.

Both apps, from this source tree:

- `LG_APP_ENVIRONMENT=staging`
- `LG_DATA_DIR` = that computer's new client directory
- `ACCOUNT_SERVER_URL=http://127.0.0.1:18765`
- Do not set `LG_RC_SMOKE`
- Do not set `STUDY_SYNC_ENABLED` in the client shell

On B, the SSH forward is `127.0.0.1:18765` to A's `127.0.0.1:18765`. B's app still uses the localhost URL, which staging is allowed to call.

Before the first login, confirm all of the following. Any failure stops the test.

- The lab process listens on `127.0.0.1` only.
- Production `STUDY_SYNC_ENABLED` is still unset and public sync routes still return 404.
- Neither client directory is the RC or production data folder.
- The lab account database file size starts at a new file, not a copy of the RC database.
- The 114 Dutch words and 114 pending outbox rows are not imported.

## 6. Who does what

Cursor, on the development machine, after a later authorization and still without the second computer:

- Create the three lab directories and run the guard preflight.
- Start the lab server and create the synthetic user.
- Launch client A from source and sign in.
- Stop there. Cursor cannot observe computer B.

Owner, on the second computer:

- Open the SSH forward.
- Launch client B from the same source commit with `lab\client-b`.
- Sign in as the same synthetic user.
- Perform the B half of each scenario below.
- Close the tunnel for the offline scenario, then open it again.

Cursor does not log in to the Owner RC account and does not copy either lab database into the repository.

## 7. Acceptance scenarios

Use one invented vocabulary item, `syncprobe`, meaning `lab-marker`. Do not use the recovered Dutch list. Wait up to 90 seconds after a change for the other computer's poll. A local save wakes only the computer that saved.

Record pass or fail, the status label, and the time. Do not record the token, the password, answer text, or any real vocabulary.

| # | Steps | Pass | Fail |
|---|-------|------|------|
| 1. Vocabulary A to B | A adds `syncprobe` / `lab-marker` and waits. | B's signed-in list shows that item. Both status labels reach Synced. | B never shows it, or the status becomes Sync unavailable (the lab flag is off or B reached the wrong host). |
| 2. Quiz B to A | B studies `syncprobe` once and submits an answer. | A shows one attempt for that item and the same Progress/SRS streak and due state after the next poll. Repeating the wait does not add a second attempt. | A stays at no attempt, or a second identical submit on B creates a second server event. |
| 3. Offline then once | B closes the SSH forward, studies one new synthetic item, then opens the forward. | B shows Offline or Pending while the tunnel is closed. After it returns, both computers show the new item and exactly one attempt. | The item never sends, or reopening the tunnel duplicates it. |
| 4. Conflict | While both are caught up, A and B each change the meaning of `syncprobe` to different synthetic meanings before either polls. | Both end in Conflict. Sync conflicts offers Keep local and Keep server. The chosen meaning is the one both sides show after they catch up. The other meaning is not silently dropped. | One meaning disappears with no conflict, or the status returns to Synced with the two meanings still different. |
| 5. Restart | Quit both apps. Start them again with the same environment variables. | Both are still the synthetic user, `syncprobe` is present, attempt count is unchanged, and the status returns to Synced without a new attempt. | A guest vocabulary list appears, the RC data folder changes, or a duplicate attempt is uploaded. |
| 6. Account isolation | On B, sign out and sign in as a second synthetic user created on the same lab server. | B does not list `syncprobe`. A, still the first user, still lists it. Signing B back into the first user shows `syncprobe` again. | The second user sees the first user's word, or A's list changes because B switched accounts. |

Scenario 3 is B, not A. A's localhost client does not go offline when the house network does.

## 8. Isolation and rollback

- Production `.env`, systemd, and the public host stay untouched. `STUDY_SYNC_ENABLED` on production stays unset.
- The lab flag lives only in the one server shell on computer A.
- Rollback of the lab: stop that process, close the SSH forward, and delete the new `lab` directories. Do not delete `%APPDATA%\langstudyguard`, `%APPDATA%\langstudyguard-rc`, or the recovery folder.
- A failed test does not authorize a VPS staging host, a public port, or a production flag change.
- Phase 18B.9 stays paused. Phase 18B.10A stays a reviewed audit, not this priority.

## 9. STOP

`APP_18C4_READY_FOR_ARCHITECT_REVIEW`

The next step is Architect review of this plan. The lab server, the SSH forward, and the second computer are not authorized by this document.
