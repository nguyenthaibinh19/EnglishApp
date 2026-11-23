# Active handoff

Rolling coordination checkpoint. See [current_state.md](../current_state.md) and [PHASE-18C.4-two-device-sync-acceptance.md](../plans/PHASE-18C.4-two-device-sync-acceptance.md).

## 1. Checkpoint metadata

- Written: 2026-11-23.
- Tag: `APP_18C4C_BLOCKED`.
- Source baseline: `1ba2c622bb57ecb9864a35fbde318fd83f8522e7`. PR #29 merge `e5763ff08097c6bb62901f6a858eda355b26f97c`.
- Active priority: **Phase 18C.4 — Real Two-Device Sync.** 18C.4A and 18C.4B are CLOSED. 18C.4C did not reach the connection gate.
- Application source baseline: `d6578c0f579d7ee9bd02aec855193339a7d8c124`.
- Remote main at start: `2ef0552d6cda58ff94dc02c680b2dd391b77aaef`.
- 18C.1, 18C.2, and 18C.3B remain CLOSED. The Sync Engine was not rebuilt.
- Phase 18B.10A: **AUDIT ACCEPTED, IMPLEMENTATION DEFERRED.** 18B.10B–E are **NOT AUTHORIZED.**
- Phase 18B.9: **PAUSED, NOT CLOSED.**
- Cloud Sync production: **OFF.**
- Staging deployment: **NOT STARTED.**
- Real two-PC acceptance: **NOT TESTED.**
- Sync pilot: **NO-GO.**
- RC account id 1, the 114 Dutch words, the 114 pending outbox rows, and recovery backups were not opened.

## 2. Evidence

- Lab root `D:\lg-18c4a-lab` holds `package`, `sync`, `backup`, `verify`, `proof`, and `client-a`.
- Nineteen copied modules matched their source SHA-256 before startup. The lab now keeps `package\accounts.db` and `sync\study_sync.db` for the next authorized phase.
- 18C.4C preflight: lab guard PASS, two synthetic users only, sync tables empty of vocabulary and attempts, port `18765` closed. No SSH session, SSH config, or `sshd` service. The synthetic password plaintext is not available here and was not reset. Details: [PHASE-18C.4C-real-two-pc-acceptance.md](../plans/PHASE-18C.4C-real-two-pc-acceptance.md).
- Original junction probe: **FAIL**. The corrected guard remains the one that validated this lab.
- `client-a` holds the synthetic staging session and bundled starter files. It is outside production, RC, recovery, and the repository.

## 3. Next

1. Owner supplies a second physical computer and an existing trusted SSH forward `B:127.0.0.1:18765` to `A:127.0.0.1:18765`.
2. Owner enters the synthetic password on B, or resets only `lab18c4_user_a` at a private prompt on A. Do not paste it into chat.

## 4. STOP

- Do not install or reconfigure SSH, and do not open a public tunnel.
- Do not start the lab server again until the SSH path and computer B are actually present.
- Do not run the two-computer scenarios.
- Do not enable production `STUDY_SYNC_ENABLED`, resume 18B.9, or implement 18B.10B–E.
