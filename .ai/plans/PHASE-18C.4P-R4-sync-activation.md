# Phase 18C.4P-R4 — Production sync activation

Status: **BLOCKED** (`APP_18C4P_R4_BLOCKED`)  
Date: 2026-11-23  
Baseline: `17365b084d8f92fa13a446592f1c68c0a41302c6`

Cloud Sync stays **OFF**. No account was created. No client signed in.

## Preflight

The account service is active. Local and HTTPS health return 200. The four deployed modules match the approved LF hashes. `STUDY_SYNC_ENABLED` is unset. `study_sync.db` is absent. `accounts-20261123-154201.db` and `/var/backups/language-guard/pre-18c4p-code/` are present. `backup_sync.py` is present. Port 8765 is not public. The accounts backup timer stays enabled. The sync backup timer stays disabled. The verifier timer stays enabled.

## Blocker

`account_server.py add` reads the password twice with `getpass` from the controlling terminal. This session's shell records that terminal, so a password entered there would be stored in the command log and read back into the agent. No other private prompt is available. A generated or piped password was not used.

`syncpilot_18c4p` was not created. `STUDY_SYNC_ENABLED` was not set. Machine A and Machine B were not signed in. No sync backup was required because no sync database exists.

## Owner action

On a private terminal the agent cannot see, run the existing add command as the service user and type the password at the two prompts. Do not paste it into chat. After that, the activation can be repeated.
