# Active handoff

Rolling coordination checkpoint. It does not replace [current_state.md](../current_state.md), [ADR-024](../decisions/ADR-024-offbox-age-drive.md), [roadmap.md](../roadmap.md), or source. Leader fields are copied from the owner brief. Technical fields are what this worktree showed. This file does not name the commit that adds it.

## 1. Checkpoint metadata

- Written: 2026-11-16T17:20:00Z.
- Observed `origin/main`: `e8ab4bba31d51986f690dcb18f9afc068f26b109`.
- Documentation worktree: `phase18b9/local-recovery-poc` at that same SHA.
- Verified here: `git rev-parse HEAD`, `git fetch origin main`, and `git status` in that worktree. One Desktop OAuth client JSON on `D:` was validated by structure only. Secrets were not printed. No consent, token refresh, Google call, live script, or VPS access occurred.

## 2. Last Leader decision

Phase 18B.9D5A2C1 remains **CLOSED — Leader Accepted, 2026-11-16**.

Phase 18B.9D5A2C2-P1 remains **ACCEPTED, 2026-11-16**, for the local WSL gate and private ext4 evidence root.

Owner assigned local OAuth client preparation only. The live Google Drive test stays **NOT AUTHORIZED**. Phase 18B.9 stays **OPEN**. Google Drive production stays **NOT CONFIGURED**. Cloud Sync stays **OFF**.

Detail: [PHASE-18B.9-offbox-status.md](../plans/PHASE-18B.9-offbox-status.md).

## 3. Active work

- ChatGPT Leader: review the proposed Desktop-client import procedure before any credential import or consent.
- Cursor: OAuth client preparation completed to the safe-metadata stage. Private empty credential directory created on WSL ext4. No import yet.
- Antigravity, Website W1: separate workspace. Live execution state: **UNKNOWN**.
- Codex: no assignment observed.

## 4. Working tree and evidence

- This worktree matches observed `origin/main`. Untracked `diff/` remains local and is not part of GitHub.
- One Google OAuth Desktop client JSON was found under `D:\Secret\`. Filename pattern `client_secret_*.apps.googleusercontent.com.json`. Structure validation: `installed` section, expected Google auth/token/cert URIs, `client_id` and `client_secret` keys present. Values were not printed. Client-id fingerprint `sha256_12=76459cc5d090`.
- Private credential directory prepared: `/home/nguyenthaibinh19/language-guard/oauth-d5a2c2-credentials`. Filesystem ext4, owner uid 1000, mode `0700`, empty, not a symlink. No `oauth-refresh` file is present.
- D5A2C2-P1 script still reads a separate `oauth-refresh` from the credential directory argument and an optional `LG_OAUTH_CLIENT_SECRET` environment value. It does not load the Desktop client JSON.
- Accepted P1 script SHA-256 remains `90f987c78c21c9a212eb14ed16ac3944ed4d5eac4b1550ea378ce8cd76cbf78a`.

## 5. Pending review

D5A2C2-P1: accepted.

OAuth client preparation: **PENDING LEADER REVIEW** of the proposed import procedure. No consent and no import are authorized.

Live synthetic Drive test: **NOT AUTHORIZED**.

## 6. Current risks

- No `oauth-refresh` exists for the one-shot. Desktop client JSON is not a refresh token.
- Folder id and token validity remain **UNKNOWN**. C2D did not leave a durable `oauth-refresh`.
- `drive.file` access to an existing folder remains **UNKNOWN**.
- Do not copy the Desktop JSON into the credential directory or into GitHub.
- The live script has not been executed. The approval phrase was not set.
- Google Drive production stays **NOT CONFIGURED**. Cloud Sync stays **OFF**.

## 7. Next action

Leader reviews the proposed safe import procedure for the Desktop client metadata and a future separately obtained `oauth-refresh`.

That is not permission to import, consent, refresh, or run the live test.

## 8. Authorization / STOP

Permitted: documentation-only checkpoints under `.ai/`, using [AI_AGENT_WORKFLOW.md](AI_AGENT_WORKFLOW.md) section 11, fast-forward only.

Prohibited: copying credentials, OAuth consent, token refresh, Google API calls, executing the live script, setting the approval phrase, VPS changes, service or timer activation, application source commit or push, production database operations, Cloud Sync activation, and remote deletion.

STOP after publishing this checkpoint.
