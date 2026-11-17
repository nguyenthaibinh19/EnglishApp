# Agent reporting standard

## Active workstream (currently App)

Depth: **detailed**.

Send to Active Workstream Lead (ChatGPT while App is active):

- Baseline SHA and branch
- Exact scope completed / not completed
- Diff or file allowlist
- Test/evidence counts (pass/fail/skip/blocked)
- FAIL/BLOCKED with durable plan or evidence paths
- Secrets scan result without printing secrets
- STOP confirmation and forbidden actions avoided

Significant implementation, isolation, packaging, and acceptance work uses the existing App review/acceptance workflow (`agent_playbook/`).

## Non-active workstreams (Web, AI)

Depth: **milestone-level** to ChatGPT (System Leader).

Product Owner manages routine implementation and local bugs.

Milestone summary to ChatGPT should include:

1. Milestone name and result (`PASS` / `FAIL` / `BLOCKED` / `READY_FOR_REVIEW`)
2. Source commit or PR reference
3. Shared-contract changes requested or made (IDs from [CONTRACT_REGISTRY.md](CONTRACT_REGISTRY.md))
4. Validation evidence (commands/results at summary level)
5. Risks and blockers
6. Explicit **requested Leader decision** (if any)

Escalate outside the milestone cadence when:

- a shared contract may break
- security/privacy boundaries are involved
- an agreed milestone gate needs System Leader review

## Local failure durability

Every repo must record FAIL/BLOCKED outcomes in its own `.ai/` (or linked evidence) on GitHub even if ChatGPT is not asked for a deep review that day.

## What not to send ChatGPT from non-active streams

- Routine UI polish iterations
- Ordinary local bug fix play-by-plays
- Private logs containing secrets or learner data
