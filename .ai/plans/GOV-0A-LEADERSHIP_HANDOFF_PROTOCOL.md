# GOV-0A proposal — Leadership handoff protocol

Status: **Historical proposal.** The adopted operating protocol is [../ecosystem/LEADERSHIP_HANDOFF_PROTOCOL.md](../ecosystem/LEADERSHIP_HANDOFF_PROTOCOL.md) (GOV-0B1). Keep this file for provenance.

Related: [GOV-0A-governance-blueprint.md](GOV-0A-governance-blueprint.md) (Leader Accepted with corrections).

## 1. Roles

| Role | Who | Authority |
|---|---|---|
| Product Owner | Human owner | Final decisions; may change Active Workstream Lead |
| System Leader / Architect | ChatGPT | Cross-repo architecture, contracts, major milestone review |
| Active Workstream Lead | ChatGPT **or** Product Owner (explicit) | Day-to-day briefs and technical review for the active repo |
| Technical agent | Cursor / Web agent / AI agent | Implements only inside the assigned repo and brief |

Completing a milestone does **not** transfer Active Workstream Lead.

## 2. When a handoff is required

A leadership handoff is required when **any** of the following is true:

1. Product Owner changes which repository is the **current priority**.
2. Product Owner changes who is Active Workstream Lead for that priority.
3. System Leader duties are paused or reassigned (rare; still needs Product Owner).
4. A shared integration contract will be owned by a different workstream after a release boundary.

A handoff is **not** required merely because:

- a phase inside the same active repo closed;
- a non-active workstream finished a local milestone;
- an agent chat was compacted or restarted (use repo `ACTIVE_HANDOFF` / Website handoff instead).

## 3. Required artifacts

Before the new Active Workstream Lead issues implementation briefs:

1. **Product Owner decision** recorded in the active repo’s durable memory (and later in `.ai/ecosystem/ACTIVE_WORKSTREAM.md`).
2. **Outgoing Lead summary**: current baseline SHA, open FAIL/BLOCKED items, forbidden actions still in force.
3. **Incoming Lead acknowledgement**: confirms priority repo, agent mapping, and reporting depth (detailed vs milestone-only).
4. **Contract freeze note**: list shared contracts that must not change without System Leader + Product Owner.

Minimum fields:

```text
handoff_id:
effective_utc:
product_owner:
previous_active_workstream:
previous_active_lead:
new_active_workstream:
new_active_lead:
baseline_commits:
open_failures:
shared_contracts_frozen:
stop_conditions:
```

## 4. Reporting after handoff

| Stream | Reporting |
|---|---|
| New active workstream | Detailed technical reports to the Active Workstream Lead |
| Other workstreams | Product Owner manages details; ChatGPT gets milestone summaries + contract/integration risks only |

## 5. Emergency exception

If production safety requires an immediate cross-repo stop, any agent may STOP and notify the Product Owner. That stop is not a leadership transfer. Resume only with an explicit Owner decision.

## 6. Adoption path

1. Accept GOV-0A blueprint.
2. In GOV-0B, copy this protocol into `.ai/ecosystem/` (or a governance docs repo) and link it from each product `.ai/README.md`.
3. Do not weaken Website-specific invariants when linking.
