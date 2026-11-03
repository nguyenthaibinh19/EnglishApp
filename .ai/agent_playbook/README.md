# Agent playbook

This folder is the collaboration and handoff playbook for StudyGuard. It tells the User, ChatGPT Leader, Cursor Developer, and Codex QA how to work in this repository and how to hand a chat to the next session.

## Authority

These files own collaboration workflow, engineering and diff discipline, and chat handoff rules.

They do not own product position or design:

| Subject | Authority |
|---|---|
| Position snapshot | [`../current_state.md`](../current_state.md) |
| Rules that must hold | [`../invariants.md`](../invariants.md) |
| Subsystem boundaries | [`../architecture.md`](../architecture.md) |
| Why a decision was made | [`../decisions/`](../decisions/) |
| Direction | [`../roadmap.md`](../roadmap.md) |

A dated file under [`handoffs/`](handoffs/) is a historical snapshot of one chat. It is not a second current state. When a handoff and `current_state.md` disagree about a committed fact, `current_state.md` on the reviewed commit wins. A handoff may describe uncommitted work that is not yet in `current_state.md`. That description does not make the work merged.

## Reading order

1. [`../current_state.md`](../current_state.md)
2. [`../invariants.md`](../invariants.md)
3. [`AI_AGENT_WORKFLOW.md`](AI_AGENT_WORKFLOW.md)
4. [`ENGINEERING_AND_DIFF_STANDARD.md`](ENGINEERING_AND_DIFF_STANDARD.md) before any implementation or diff
5. The ADR, architecture page, or procedure for the task
6. The code and tests named by the brief
7. [`CHAT_HANDOFF_PROTOCOL.md`](CHAT_HANDOFF_PROTOCOL.md) when a chat must be resumed elsewhere
8. One dated handoff only when the brief says to resume that snapshot

## Files

| File | Role |
|---|---|
| [AI_AGENT_WORKFLOW.md](AI_AGENT_WORKFLOW.md) | Canonical collaboration workflow |
| [ENGINEERING_AND_DIFF_STANDARD.md](ENGINEERING_AND_DIFF_STANDARD.md) | Briefs, tests, diffs, commit, and production boundaries |
| [CHAT_HANDOFF_PROTOCOL.md](CHAT_HANDOFF_PROTOCOL.md) | How to write and read a chat handoff |
| [handoffs/](handoffs/) | Dated snapshots |
