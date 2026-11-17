# Agent playbook

This folder is the collaboration and handoff playbook for StudyGuard. It tells the User, ChatGPT Leader, Cursor Developer, and Codex QA how to work in this repository and how to hand a chat to the next session.

## Authority

These files own collaboration workflow, engineering and diff discipline, and chat handoff rules.

They do not own product position or design:

| Subject | Authority |
|---|---|
| Position snapshot | [`../current_state.md`](../current_state.md) |
| Latest coordination checkpoint | [`ACTIVE_HANDOFF.md`](ACTIVE_HANDOFF.md) |
| Cross-repo governance | [`../ecosystem/README.md`](../ecosystem/README.md) |
| Rules that must hold | [`../invariants.md`](../invariants.md) |
| Subsystem boundaries | [`../architecture.md`](../architecture.md) |
| Why a decision was made | [`../decisions/`](../decisions/) |
| Direction | [`../roadmap.md`](../roadmap.md) |

[`ACTIVE_HANDOFF.md`](ACTIVE_HANDOFF.md) is the rolling coordination checkpoint: the latest Leader decision, assignments, pending review, and STOP line. It is not a second product state. Cursor records those Leader fields only from an explicit Leader or owner statement.

A dated file under [`handoffs/`](handoffs/) is an immutable snapshot of one chat. When a handoff and `current_state.md` disagree about a committed fact, `current_state.md` on the reviewed commit wins. A handoff may describe uncommitted work that is not yet in `current_state.md`. That description does not make the work merged. A new Leader reconciles `ACTIVE_HANDOFF.md` against GitHub, the worktree, tests, and evidence before proceeding.

Documentation checkpoints are standing owner authorization as of 2026-11-16. The rule is [AI_AGENT_WORKFLOW.md](AI_AGENT_WORKFLOW.md) section 11. It covers `.ai/` status, plans, decisions, and handoffs. It does not cover application source or production actions.

## Reading order

1. [`../current_state.md`](../current_state.md)
2. [`ACTIVE_HANDOFF.md`](ACTIVE_HANDOFF.md)
3. [`../invariants.md`](../invariants.md)
4. [`AI_AGENT_WORKFLOW.md`](AI_AGENT_WORKFLOW.md)
5. [`ENGINEERING_AND_DIFF_STANDARD.md`](ENGINEERING_AND_DIFF_STANDARD.md) before any implementation or diff
6. The ADR, architecture page, or procedure for the task
7. The code and tests named by the brief
8. [`CHAT_HANDOFF_PROTOCOL.md`](CHAT_HANDOFF_PROTOCOL.md) when a chat must be resumed elsewhere
9. One dated handoff only when the brief says to resume that snapshot

## Files

| File | Role |
|---|---|
| [AI_AGENT_WORKFLOW.md](AI_AGENT_WORKFLOW.md) | Canonical collaboration workflow |
| [ENGINEERING_AND_DIFF_STANDARD.md](ENGINEERING_AND_DIFF_STANDARD.md) | Briefs, tests, diffs, commit, and production boundaries |
| [CHAT_HANDOFF_PROTOCOL.md](CHAT_HANDOFF_PROTOCOL.md) | How to write and read a chat handoff |
| [ACTIVE_HANDOFF.md](ACTIVE_HANDOFF.md) | Rolling coordination checkpoint |
| [handoffs/](handoffs/) | Immutable dated snapshots |
