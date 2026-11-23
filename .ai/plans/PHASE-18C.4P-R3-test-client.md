# Phase 18C.4P-R3 — Production test client

Status: **READY FOR SYNC ACTIVATION REVIEW** (`APP_18C4P_R3_TEST_CLIENT_READY_FOR_SYNC_ACTIVATION`)  
Date: 2026-11-23  
Source: `ed4e49ea8b977468d10869adec8d2ec3b494fe91`

The production EXE was not rebuilt or launched. No account was created and Sync stays off.

## Machine A

Isolated copy: `D:\lg-18c4p-r3-client`  
Disposable data: `D:\lg-18c4p-r3-data`  
The copy has its own `build_manifest.json` (`channel=production`, version `1.4.0`, commit `ed4e49ea8b977468d10869adec8d2ec3b494fe91`). The repository manifest was not edited. There is no `.env` in the copy.

Child environment:

- `LG_APP_ENVIRONMENT=production`
- `ACCOUNT_SERVER_URL=https://langstudyguard.com`
- `LG_DATA_DIR=D:\lg-18c4p-r3-data`
- `OPENAI_API_KEY`, `EMERGENCY_PASSWORD`, and `ACCOUNT_TOKEN` empty
- `LG_RC_SMOKE` absent
- no `--lock`

Before launch, identity was runtime `production`, channel `production`, no identity error, RC false, not frozen, network writes allowed, host `langstudyguard.com`, data root `D:\lg-18c4p-r3-data`, token empty, emergency password empty, provider key empty.

The source window title was `Language Guard — PRODUCTION`. The process was then closed. No `settings.json` was written. The installed EXE hash, Startup shortcut, production AppData, RC `account_study.db`, recovery folder, and repository manifest were unchanged.

## Machine B

1. Install Python 3.13 with Tk and `python-dotenv`. Do not install `langstudyguard.exe`.
2. Clone `https://github.com/nguyenthaibinh19/EnglishApp` and check out `ed4e49ea8b977468d10869adec8d2ec3b494fe91` into a new folder. Do not copy a `.env` into it.
3. Create a data folder outside AppData, for example `D:\lg-18c4p-r3-data`.
4. In a new terminal, set only `LG_APP_ENVIRONMENT=production`, `ACCOUNT_SERVER_URL=https://langstudyguard.com`, and `LG_DATA_DIR` to that folder. Leave `LG_RC_SMOKE` unset. Set `OPENAI_API_KEY`, `EMERGENCY_PASSWORD`, and `ACCOUNT_TOKEN` to empty.
5. From the clone root, run `python app\main.py` with no `--lock`.
6. Confirm the title is `Language Guard — PRODUCTION`. Do not sign in until the activation gate below.

No result from computer B is claimed.

## Activation gate, not done

1. Create one synthetic production account. Do not use the real learner account.
2. Set `STUDY_SYNC_ENABLED=1` and restart only the account service. The flag is server-wide.
3. Sign the same synthetic account in on A and B and sync one vocabulary marker from A to B.
4. Run the existing `backup_sync.py` once, as `guard`, before 08:00 Europe/Amsterdam. Leave the sync backup timer disabled.
5. Rollback is removing `STUDY_SYNC_ENABLED` and restarting. Leave `study_sync.db` and accepted rows in place.
