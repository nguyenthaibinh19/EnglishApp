# Chat handoff protocol — StudyGuard

This is the canonical chat handoff protocol. `.ai/current_state.md` remains the accepted product state. [ACTIVE_HANDOFF.md](ACTIVE_HANDOFF.md) is the rolling coordination checkpoint. A dated file under `handoffs/` is an immutable snapshot. None of these replace ADRs, the roadmap, or source.

## Goal

A new ChatGPT conversation should rapidly recover the product, current task, decision authority, Cursor/Codex workflow and safety boundaries without needing the old chat transcript. The repository is permanent memory; a dated handoff is a **temporary snapshot**, not the canonical architecture.

## Source reading order

1. `.ai/README.md` and `.ai/current_state.md` — accepted product state.
2. `.ai/agent_playbook/ACTIVE_HANDOFF.md` — latest Leader decision, assignments, pending review, and STOP line. Reconcile it against GitHub, the worktree, tests, and evidence before acting.
3. `.ai/invariants.md`, `.ai/roadmap.md` — hard boundaries and next planned work.
4. `.ai/procedures/AI_AGENT_WORKFLOW.md` and `ENGINEERING_AND_DIFF_STANDARD.md` — collaboration and review.
5. Relevant ADRs, `architecture.md`, `lessons.md`, and task-specific procedures.
6. Actual code, tests, Git branch/HEAD, working-tree status and attached review diff.
7. A dated handoff only when the brief says to resume that snapshot. Do not rewrite it to match today's state.

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
4. Push a documentation checkpoint when status changes, including a failure or a pending review. Do not wait for acceptance. After a phase is accepted, update durable `.ai/current_state.md` and `.ai/roadmap.md` and push that checkpoint. Do not commit raw chat history or redundant ephemeral logs. A documentation push is not a source commit.
5. Refresh `ACTIVE_HANDOFF.md` after a material Leader decision, when a substantial Cursor task starts or finishes, when a task fails or blocks, when a review package is ready, when a milestone is accepted or rejected, and before a handoff. Publish that refresh under section 11 of `AI_AGENT_WORKFLOW.md`. Skip the commit when the checkpoint is unchanged. Cursor may fill Leader fields only from an explicit Leader or owner statement. A dated handoff stays immutable.

## Minimal new-chat kickoff prompt

> You are ChatGPT Leader/Architect/Reviewer for `nguyenthaibinh19/EnglishApp`. Speak Vietnamese to the owner; give exact paste-ready Cursor briefs. Read `.ai/current_state.md` and `.ai/agent_playbook/ACTIVE_HANDOFF.md`, then `invariants.md`, `roadmap.md`, `AI_AGENT_WORKFLOW.md`, and relevant source/tests. Reconcile the handoff against GitHub, the worktree, tests, and evidence before proceeding. `current_state.md` is the accepted product state. Cursor cannot manufacture a Leader decision. Distinguish IMPLEMENTED, TESTED, REPORTED, PENDING REVIEW, ACCEPTED, COMMITTED, PUSHED, and DEPLOYED. Documentation checkpoints under `.ai/` are standing authorization. Source commit, source push, and production actions are not. Never infer SSH/VPS/Sync activation from a documentation push. Summarize the current gate and continue from the pending Cursor report; do not reopen closed milestones or mark deferred Linux tests PASS.
