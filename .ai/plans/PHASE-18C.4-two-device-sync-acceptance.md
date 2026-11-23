# Phase 18C.4 — Two-device sync acceptance

Status: **18C.4A-R1 final PR ready for Architect review** (`APP_18C4A_R1_FINAL_PR_READY_FOR_ARCHITECT_REVIEW`)  
Owner priority: working Account Sync between two real Windows computers, before production hardening and Google Drive backup.  
Date: 2026-11-23  
Cloud Sync production: **OFF** · 18B.9: **PAUSED, NOT CLOSED** · Staging: **RESERVED, not deployed** · Sync pilot: **NO-GO** until explicitly authorized  
18B.10A: **AUDIT ACCEPTED, IMPLEMENTATION DEFERRED.** Do not implement 18B.10B, 18B.10C, 18B.10D, or 18B.10E.

This document is the readiness and test plan. It does not start a server, build an EXE, change application source, or run the two-computer test.

## 1. Baseline

| Check | Result |
|-------|--------|
| Architect named `main` | `46e84f869aae1501f16a5b05116fbb81112939bf` |
| This worktree before the correction | `d27c8d95b9c6d9ca1da63cda23aeab6a195a6d77`, which contains that commit plus the first 18C.4 plan |
| Application source | Unchanged since `d6578c0f579d7ee9bd02aec855193339a7d8c124` |
| Closed product slices | 18C.1, 18C.2, and 18C.3B. Reuse them. Do not rebuild the Sync Engine. |
| 18B.10A | Audit accepted as documentation. Implementation deferred. Its limits are not a prerequisite for this test. |

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

## 4. Readiness

| Requirement | Class | Evidence |
|-------------|-------|----------|
| Two Windows apps, same synthetic account, vocabulary, attempts, Progress, and SRS | **Already implemented** | `account_sync_engine.sync_once` and the signed-in UI. In-process coverage is `tests/test_account_ux_two_device.py`. |
| Offline retry without a second event | **Already implemented** | Outbox stays pending. HTTP 500 and network errors back off. Idempotent `event_id` and `operation_id` retries are tested. |
| Simultaneous vocabulary edits | **Already implemented** | `sync_conflict_app.py` offers Keep local and Keep server. No silent last-write-wins. |
| Account switch | **Already implemented** | `account_session.switch_account` stops the previous worker and starts the next. Local SQLite for the previous user stays on disk. |
| Restart without loss or duplication | **Already implemented** | The account SQLite and `settings.json` live under `LG_DATA_DIR`. Launch calls `maybe_start_account_sync`. |
| Production host refused by a staging or development client | **Already implemented** | `validate_backend_for_identity` rejects `langstudyguard.com` and every subdomain. |
| Sync engine rebuild, rate limits, quotas | **Missing functionality: none for this test** | 18C.1, 18C.2, and 18C.3B stay as they are. 18B.10B–E stay deferred. |
| Isolated server whose `accounts.db` is not the repository file | **Missing deployment/configuration** | `account_store.db_path()` is the directory of the imported `account_store.py`. `STUDY_SYNC_DIR` moves only `study_sync.db`. `deploy/hetzner/staging_server.py` already refuses to start unless the effective account file is `STAGING_PACKAGE_DIR\accounts.db`. |
| Loopback path from the second computer | **Missing deployment/configuration** | The guard allows bind `127.0.0.1` only. An SSH local forward is the path that keeps both clients on localhost. |
| Client data outside the repo, production AppData, and RC AppData | **Missing deployment/configuration** | A source run without `LG_DATA_DIR` writes development data into the repository tree. |
| Any pass/fail from two physical computers | **Missing real-device evidence** | Every existing two-device test is one process. |
| Second computer, SSH session, and the synthetic password | **Requires Owner action** | Cursor cannot see or operate that computer. The password is not written into the repo. |
| Decision to start the lab process | **Requires Owner action** | 18C.4A prepared the files only. Starting the process, the tunnel, and accounts still needs 18C.4B. |

## 5. Minimum execution steps

18C.4A completed the offline part of steps 1–3 at `D:\lg-18c4a-lab` and validated the guard without starting a process. Steps 4–8 stay unauthorized. Do not point them at the VPS. Do not fall back to `python account_server.py` from the live source tree.

1. On computer A, create five sibling directories outside the repository, `%APPDATA%\langstudyguard`, `%APPDATA%\langstudyguard-rc`, `%APPDATA%\langstudyguard-staging`, and `%LOCALAPPDATA%\LanguageGuard-Recovery`: `lab\package`, `lab\sync`, `lab\backup`, `lab\verify`, and `lab\proof`. None may contain another. Add `lab\client-a` on A and `lab\client-b` on B.
2. Copy the server modules into `lab\package`. Do not copy an existing `accounts.db`, `study_sync.db`, `.env`, or anything from the RC folder.
3. Write `lab\package\.env` with only these six lines: `OPENAI_API_KEY=staging-fake-not-a-provider-key`, `OPENAI_BASE_URL=http://127.0.0.1:9`, `ACCOUNT_BIND=127.0.0.1`, `ACCOUNT_PORT=18765`, `STUDY_SYNC_DIR` set to `lab\sync`, and `STUDY_SYNC_ENABLED=1`.
4. Start `deploy/hetzner/staging_server.py` with `PYTHONPATH=lab\package` and the matching `STAGING_PACKAGE_DIR`, `STAGING_ENV_FILE`, `STAGING_PROOF_DIR`, `STUDY_SYNC_BACKUP_DIR`, and `STUDY_SYNC_VERIFY_DIR`. The guard must accept loopback, port `18765`, the fake key, and those separated paths.
5. With the same `PYTHONPATH`, create two synthetic users through the copied `account_server.py add`. The names must not be an Owner account. Keep the passwords out of the repo and out of logs.
6. On each computer, launch this source tree with `LG_APP_ENVIRONMENT=staging`, `LG_DATA_DIR` set to that computer's client directory, and `ACCOUNT_SERVER_URL=http://127.0.0.1:18765`. Do not set `LG_RC_SMOKE`. Do not set `STUDY_SYNC_ENABLED` in the client shell. Do not use `langstudyguard.exe` or `langstudyguard-rc.exe`.
7. On B, open an SSH local forward from B's `127.0.0.1:18765` to A's `127.0.0.1:18765`. Then sign both apps into the first synthetic user.
8. Run the six scenarios in section 7. Wait up to 90 seconds for the other computer's 60-second poll.

Before step 7, confirm the listener is `127.0.0.1` only, public sync routes still return 404, both client directories are the new lab folders, and `lab\package\accounts.db` is a new file. The 114 Dutch words and 114 pending outbox rows are not imported.

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

- Create the sibling lab directories, copy the server package, and start it only through `staging_server.py`.
- Create the two synthetic users in that copied package.
- Launch client A from the source tree with `LG_DATA_DIR` and sign in.
- Stop there. Cursor cannot observe computer B.
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
| 2a. Same event replay | After scenario 2b has one accepted attempt, retransmit that same `event_id` and body. | The server returns the original result. Attempt count stays 1. Progress counters do not increment again. | A second row appears for that `event_id`. |
| 2b. Second quiz submission | B submits one new answer for `syncprobe`. The app allocates a new `event_id`. | A shows that one new attempt and the updated Progress/SRS after the next poll. | The new answer never arrives, or it reuses the previous `event_id`. |
| 3. Offline recovery on B | B closes only its SSH forward, completes one synthetic study action, then opens the forward. | While closed, B is Offline or Pending and the event remains local. After reconnect, both computers show that event once. Nothing already accepted is lost. | The pending event disappears, never uploads, or appears twice. |
| 4. Deterministic conflict | Follow the eight steps below. Do not depend on both people editing at the same moment. | B shows Conflict after reconnect. Keep local or Keep server is an explicit choice. Both computers then show the chosen meaning, and the unchosen meaning is not deleted without that choice. | The meanings converge with no conflict screen, or the chosen value never reaches the other computer. |
| 5. Restart | Quit both apps. Start them again with the same environment variables. | Both are still the synthetic user, `syncprobe` is present, attempt count is unchanged, and the status returns to Synced without a new attempt. | A guest vocabulary list appears, the RC data folder changes, or a duplicate attempt is uploaded. |
| 6. Account isolation | On B, sign out and sign in as a second synthetic user created on the same lab server. | B does not list `syncprobe`. A, still the first user, still lists it. Signing B back into the first user shows `syncprobe` again. | The second user sees the first user's word, or A's list changes because B switched accounts. |

Scenario 2 records the replay and the new submission as separate results. A second genuine quiz answer is supposed to create one new attempt. Only a repeated `event_id` must stay at one row.

Scenario 3 uses B's tunnel. Unplugging computer A does not make A's localhost client offline, so that is not the offline test.

Scenario 4 sequence, not executed in 18C.4A:

1. Both computers sync the same synthetic item.
2. Close B's SSH tunnel before B receives later changes.
3. Change the item on A and let that change reach the lab server.
4. Change B's stale copy while B is still offline.
5. Reopen B's tunnel.
6. The affected client shows a conflict.
7. Resolve it with the existing Keep local or Keep server control.
8. Both computers show the chosen value. The other value is not discarded silently.

Failure evidence is a missing conflict, a silent overwrite, a lost pending event, or a duplicate `event_id`. Do not record tokens, passwords, or real learner data.

## 8. Isolation and rollback

- Production `.env`, systemd, and the public host stay untouched. `STUDY_SYNC_ENABLED` on production stays unset.
- The lab flag lives only in the one server shell on computer A.
- Rollback of the lab: stop that process, close the SSH forward, and delete the new `lab` directories. Do not delete `%APPDATA%\langstudyguard`, `%APPDATA%\langstudyguard-rc`, or the recovery folder.
- A failed test does not authorize a VPS staging host, a public port, or a production flag change.
- Phase 18B.9 stays paused. Phase 18B.10A stays accepted documentation. Do not implement 18B.10B, 18B.10C, 18B.10D, or 18B.10E.

## 9. 18C.4A offline preflight

Performed on computer A only. The lab server was not started. No account was created. No SSH session was opened. `staging_server.py` was not run.

Lab root: `D:\lg-18c4a-lab`. It is outside the repository, both worktrees, `%APPDATA%\langstudyguard`, `%APPDATA%\langstudyguard-rc`, `%APPDATA%\langstudyguard-staging`, and `%LOCALAPPDATA%\LanguageGuard-Recovery`.

| Directory | Role |
|-----------|------|
| `D:\lg-18c4a-lab\package` | Copied server modules and the lab `.env`. Future `accounts.db` is not present. |
| `D:\lg-18c4a-lab\sync` | Future `study_sync.db`. Empty. |
| `D:\lg-18c4a-lab\backup` | Guard backup root. Empty. |
| `D:\lg-18c4a-lab\verify` | Guard verify root. Empty. |
| `D:\lg-18c4a-lab\proof` | Guard proof root. Empty. |
| `D:\lg-18c4a-lab\client-a` | Future client A `LG_DATA_DIR`. Empty. |
| Computer B `client-b` | Not created. Owner creates it on computer B after a later authorization. |

Copied allowlist, each SHA-256 matched the source file:

| Module | SHA-256 |
|--------|---------|
| `account_server.py` | `4101e111abee9400217334b468901c5e033c6be1fa79be7ba189c72f749685b9` |
| `account_store.py` | `187345f6b8d8eae46ae9cdf290dbc33f556e7d29518046ed5891b4e9da73a331` |
| `sync_http.py` | `a3970550cc0cfb58124804135ed49ea0004e14b8a8de51c5d027b200bb3a5222` |
| `sync_store.py` | `3fc2292cc2a6d78dedd5e8e1f4e7edbb26e722278f34f3b0bfb35999d43e2985` |
| `config.py` | `d1baad348dcbf6726af97a182c584da2a51e5553d57738b6e094a8d01faee393` |
| `app_environment.py` | `aaf7b3aad24f3602929ffc68c6179b712eadbe310202de45938bbc3e370bc458` |
| `languages.py` | `e579fc91a8a625bdce36fde80b73c61b08b00420a264be951db107cf127ff178` |
| `vocab_identity.py` | `d1c7cbfa0d5007c1f391f8d88621f65f290d70d0c1a0f64c5e5998cc8f05bc3e` |
| `vocabulary_model.py` | `fe1f814c24d3627cfc62fc70b2c2afb2d7bafd6ca950f47c0d17865e6c99dbc1` |
| `text_utils.py` | `de95e48b23ef74eb8b06b9b9c186ea5b94e66ce1b0ff9f5e740baea176846880` |
| `ai_teacher.py` | `91ea4549a232c80bdb7bce1b371f385117edeb3ef337074f7ac73822cb4fdf3f` |
| `listening.py` | `a7764d849e8086237909dc74f64ddd7b9b3bf083f9ff3c1562d28fab9f589d67` |
| `listening_content.py` | `8e8e8cf35aaff6ddd1e9f21a4eb4a40f79099c6103d5422d60347e7982e79fb9` |
| `reading_schema.py` | `5322899c542acd390ba87a4fc6233bc3244065dfa89baa4810578470869c8258` |
| `srs.py` | `eca45912b04de8747339c3b3e552ab728d8bc53fa5d5beaba2487e36592eb867` |
| `ai/__init__.py` | `b38551951f24d9919702ecec340691f5cdce12fda581351876038ec7f38c08b4` |
| `ai/base.py` | `1757801d424661c0dc912ec1ba4b08244d9c62d55d12cfa51071ec0c2e401bb1` |
| `ai/service.py` | `b3081aedb98676282f03e34101d29a8b0759e6e0ba00b3ba42c0e53e2cafaff2` |
| `ai/openai_provider.py` | `9655f1b3cb5a33345052af18395fbfb6e707b4cb55f0b90f8700fcea791fceeb` |

`srs.py` is included because progress accept imports it when an attempt is uploaded. It is not imported during this preflight. No SQLite file, cache, or backup was copied. The lab `.env` has only the six guard keys and the documented fake provider values.

Path check, with `sys.path` pointing at the copy and the repository removed from the path:

- `account_store.__file__` = `D:\lg-18c4a-lab\package\account_store.py`
- `account_store.db_path()` = `D:\lg-18c4a-lab\package\accounts.db`
- `sync_http.sync_db_path()` = `D:\lg-18c4a-lab\sync\study_sync.db`
- Neither file existed before or after the check.

Guard command: `python -I D:\lg-18c4a-lab\check_guard.py`, which calls `staging_guard.validate(layout, require_env_file=True)` and does not import `staging_server`. Result: **PASS**. Bind `127.0.0.1`, port `18765`, fake key accepted, account token empty, account and sync paths separated. Port check used a non-binding connect probe. Proof directory stayed empty. Both databases stayed absent.

`client-a` is empty and does not overlap production AppData, RC AppData, recovery, or either EnglishApp tree. A staging identity accepts that path.

Reparse safety, original 18C.4A result: **FAIL**. `os.path.islink` did not see a directory junction, and the guard accepted that path. The probe was removed. The real lab directories were ordinary directories.

Reparse safety, 18C.4A-R1: the guard rejects a junction, including when it is only an ancestor. A probe of `D:\lg-18c4a-lab\junction-probe` returned `symlink`. `os.path.islink` on that junction was still false. The probe was removed again. The six lab directories remain ordinary directories.

18C.4A-R1 required correction: `os.path.lexists()` treats an `lstat` access error as a missing path. The walk now uses `os.lstat`. Only `FileNotFoundError` is a genuinely missing component. Permission errors and other `lstat` failures reject the path. A focused test simulates `PermissionError` on an existing package directory and expects code `symlink` with no database and no proof file.

Focused suite after that correction: `tests/test_sync_staging_isolation.py`, **22 passed, 3 skipped**. The skips remain **UNVERIFIED** file or directory symlink creation (Windows error 1314), not passes. The lab guard was run again with this module and returned **PASS**. Both database files are still absent. Port `18765` was not listening. The 19 copied module hashes are unchanged. The server was not started.

## 10. SSH prerequisites

Not started.

Computer A will bind only `127.0.0.1:18765`. Computer B will use an SSH local forward over a path the Owner already trusts, then open `http://127.0.0.1:18765` on B. Both apps use a staging identity and their own `LG_DATA_DIR`.

Still required from the Owner, after 18C.4B authorization:

- Computer B on the same trusted LAN or VPN path.
- An SSH login to computer A. The credential stays with the Owner and is not written here.
- The forward `127.0.0.1:18765` on B to `127.0.0.1:18765` on A.
- Confirmation that the forward dies when the SSH session ends, and that no public HTTP port was opened.
- `client-b` created on computer B, outside production, RC, and recovery data.

## 11. STOP

`APP_18C4A_R1_FINAL_PR_READY_FOR_ARCHITECT_REVIEW`

18C.4B is a separate authorization. It is required before the lab server starts, before any synthetic account is created, and before the SSH tunnel or the two-computer test.
