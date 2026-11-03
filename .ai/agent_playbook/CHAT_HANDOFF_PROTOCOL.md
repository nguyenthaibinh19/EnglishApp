# Chat handoff protocol — StudyGuard

This is the canonical chat handoff protocol. A dated handoff is a historical snapshot and does not replace `.ai/current_state.md`.

## Goal

A new ChatGPT conversation should rapidly recover the product, current task, decision authority, Cursor/Codex workflow and safety boundaries without needing the old chat transcript. The repository is permanent memory; a dated handoff is a **temporary snapshot**, not the canonical architecture.

## Source reading order

1. `.ai/README.md` and `.ai/current_state.md` — accepted status.
2. `.ai/invariants.md`, `.ai/roadmap.md` — hard boundaries and next planned work.
3. `.ai/procedures/AI_AGENT_WORKFLOW.md` and `ENGINEERING_AND_DIFF_STANDARD.md` — collaboration and review.
4. Relevant ADRs, `architecture.md`, `lessons.md`, and task-specific procedures.
5. Actual code, tests, Git branch/HEAD, working-tree status and attached review diff.
6. Current handoff snapshot — especially work **not yet in GitHub**.

A source file can be stale even if adjacent documents are current. When a handoff points to a contradiction, **verify and flag it** rather than assuming the older statement is current.

## Handoff record format

Prepare a short dated Markdown note with:

- Repository URL and tested GitHub main SHA; working branch/HEAD and deployed source SHA separately.
- Closed phases with evidence; active phase and its exact authorization gate.
- Local uncommitted Cursor modifications, including new untracked files, diff location and state of the active Cursor task.
- Exact last Leader brief: pending fixes, evidence to request and STOP condition.
- Test command counts and skipped/unrun Linux cases, distinguishing report from independent verification.
- Production status: Sync flag, database existence, service/timer changes, secrets, deploy/release prohibitions.
- Product-owner preferences (language, budget, risk tolerance, daily report channels/time).
- Known doc inconsistencies and next doc maintenance action.
- Next single decision and next action, **not** authorization to proceed automatically.

Never paste passwords, tokens, credential URLs, live database rows or personal user data into the handoff.

## Handoff discipline

1. Write the snapshot **before** switching chats; do not wait for an in-flight Cursor task if the snapshot accurately marks it pending.
2. Start the new conversation by attaching the handoff, linking the repository and instructing the new Leader to inspect the canonical `.ai/` docs and exact worktree/diff.
3. Reconcile the next Cursor report against the handoff; update the active snapshot rather than treating its facts as immutable.
4. After a phase is accepted and pushed, update durable `.ai/current_state.md` and `.ai/roadmap.md` with the accepted SHA. Do not commit raw chat history or redundant ephemeral logs.
5. If a single handoff file is kept locally, refresh or replace it at each chat boundary. It should not silently live forever as a current-state claim.

## Minimal new-chat kickoff prompt

> You are ChatGPT Leader/Architect/Reviewer for `nguyenthaibinh19/EnglishApp`. Speak Vietnamese to the owner; give exact paste-ready Cursor briefs. Read the attached handoff, then repository `.ai/README.md`, `current_state.md`, `invariants.md`, `roadmap.md`, `AI_AGENT_WORKFLOW.md`, and relevant source/tests. Distinguish GitHub committed state from Cursor's uncommitted working tree. Review evidence before authorizing commit; never infer SSH/VPS/Sync activation from source approval. Summarize the current gate and continue from the pending Cursor report; do not reopen closed milestones or mark deferred Linux tests PASS.
