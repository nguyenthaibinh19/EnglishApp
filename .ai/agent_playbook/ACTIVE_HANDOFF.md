# Active handoff

Rolling coordination checkpoint. It does not replace [current_state.md](../current_state.md), [ADR-024](../decisions/ADR-024-offbox-age-drive.md), [roadmap.md](../roadmap.md), or source. Leader fields are copied from the owner brief. Technical fields are what this worktree showed. This file does not name the commit that adds it.

## 1. Checkpoint metadata

- Written: 2026-11-16T17:41:29Z.
- Observed `origin/main`: `a5e64ac0d51a0ced585388c841fd9d1a3b05c600`.
- Documentation worktree: `phase18b9/local-recovery-poc` at that same SHA.
- Verified here: P1 script hash, Desktop client fingerprint, credential and evidence directory metadata, and local private setup config existence. No Google API call. The live script was not executed. `LG_LIVE_APPROVAL` was not set. Secrets and the folder id were not written into GitHub.

## 2. Last Leader decision

Phase 18B.9D5A2C1 remains **CLOSED — Leader Accepted, 2026-11-16**.

Phase 18B.9D5A2C2-P1 remains **ACCEPTED, 2026-11-16**.

OAuth consent completed successfully on 2026-11-16. A refresh-token file exists on WSL ext4.

Leader assigned D5A2C2 final live-test setup as a local configuration check only. The live synthetic Google Drive test stays **NOT AUTHORIZED**.

Phase 18B.9 stays **OPEN**. Google Drive production stays **NOT CONFIGURED**. Cloud Sync stays **OFF**.

## 3. Active work

- ChatGPT Leader: review the redacted live-setup plan and decide whether to ask the owner for one explicit synthetic live-test approval.
- Cursor: local live-setup checks completed. Ready for Leader review. No live execution.
- Antigravity, Website W1: separate workspace. Live execution state: **UNKNOWN**.
- Codex: no assignment observed.

## 4. Working tree and evidence

- P1 `live_synthetic_once.py` SHA-256 `90f987c78c21c9a212eb14ed16ac3944ed4d5eac4b1550ea378ce8cd76cbf78a` matched.
- Desktop client fingerprint `76459cc5d090` matched. Client secret key is present in the Desktop JSON; the P1 script still does not load that JSON and expects optional `LG_OAUTH_CLIENT_SECRET` in the environment.
- Credential directory `/home/nguyenthaibinh19/language-guard/oauth-d5a2c2-credentials` remains mode `0700` on ext4. `oauth-refresh` exists, mode `0600`, nonempty. Contents were not read.
- Evidence root `/home/nguyenthaibinh19/language-guard/d5a2c2-live-evidence` is mode `0700` on ext4. `results-live-once` is absent.
- Owner supplied a Drive folder id for `LanguageGuard-Synthetic-Backup-Test`. Format validated. The value is stored only in the local private file `/home/nguyenthaibinh19/language-guard/d5a2c2-live-setup.json` mode `0600`, with `live_test_authorized=false`. It is not in GitHub.
- Public recipient path is present (`age1pq1`, length 1959). Synthetic identity path exists and is not a symlink; it was not opened. WSL age binary is executable. WSL Python is 3.14.4.

## 5. Pending review

D5A2C2 live-setup plan: **PENDING LEADER REVIEW**.

Live synthetic Drive test: **NOT AUTHORIZED**. Still requires a later explicit owner approval phrase and Leader brief.

## 6. Current risks

- Folder accessibility under `drive.file` is still **UNKNOWN** until a later authorized live test. Failure must fail closed. Do not broaden scope.
- External Testing refresh tokens are expected to expire about seven days after the 2026-11-16 consent.
- The approval phrase must not be placed in shell history, logs, or GitHub.
- Google Drive production stays **NOT CONFIGURED**. Cloud Sync stays **OFF**.

## 7. Next action

Leader reviews the redacted invocation plan. If accepted, a separate brief must authorize exactly one synthetic live test.

That recommendation is not permission to run it.

## 8. Authorization / STOP

Permitted: documentation-only checkpoints under `.ai/`, using [AI_AGENT_WORKFLOW.md](AI_AGENT_WORKFLOW.md) section 11, fast-forward only.

Prohibited: Google Drive API calls, setting `LG_LIVE_APPROVAL`, executing the live script, VPS changes, source commit or push, credential changes, production database operations, Cloud Sync activation, and publishing the folder id to GitHub.

STOP after publishing this checkpoint.
