# Leadership handoff protocol

**Status:** **Leader Accepted** with GOV-0B1 CLOSED (2026-11-17). This is the operating handoff protocol for the ecosystem.  
**Supersedes as operating protocol:** [GOV-0A-LEADERSHIP_HANDOFF_PROTOCOL.md](../plans/GOV-0A-LEADERSHIP_HANDOFF_PROTOCOL.md) (kept as historical proposal).

## Principle

A change in product priority, or closing an implementation milestone, does **not** by itself:

- transfer Active Workstream Lead, or
- grant operational permissions (SSH, deploy, OAuth, merges, production flags, private-repo access).

Transfer requires **explicit Product Owner approval** and durable evidence below.

## When required

1. Product Owner changes the active workstream repository.
2. Product Owner changes who is Active Workstream Lead.
3. System Leader duties are reassigned (still needs Owner).
4. Contract ownership moves across repos after a release boundary.

Not required for: same-repo phase closure; non-active local milestones; chat compaction (use repo ACTIVE_HANDOFF).

## Gates (all required)

| Gate | Evidence |
|---|---|
| G1 Product Owner transfer decision | Written Owner statement recorded in durable docs |
| G2 Effective workstream + new Active Lead | Updated [ACTIVE_WORKSTREAM.md](ACTIVE_WORKSTREAM.md) |
| G3 Source baseline + deployment status | Commit SHAs; deploy state (**NOT READY** unless Owner says otherwise) |
| G4 Open FAIL/BLOCKED tasks | Listed with links (e.g. D5A2D2 FAIL) |
| G5 Pending architectural decisions | Listed or explicitly “none” |
| G6 Shared contracts + compatibility risks | Contract IDs frozen or change plan |
| G7 Permissions / ops needing fresh approval | Explicit “not carried over” list |
| G8 Outgoing Lead acknowledgement | Summary signed in handoff record |
| G9 Incoming Lead acknowledgement | Confirms reporting depth and agent mapping |
| G10 Final handoff acceptance | Owner or incoming Lead records acceptance UTC |

## Minimum record fields

```text
handoff_id:
effective_utc:
product_owner_decision_ref:
previous_active_workstream:
previous_active_lead:
new_active_workstream:
new_active_lead:
baseline_commits:
deployment_status:
open_fail_blocked:
pending_architecture:
shared_contracts_frozen:
permissions_requiring_fresh_approval:
outgoing_ack:
incoming_ack:
final_acceptance:
stop_conditions:
```

## After handoff

- Active stream: detailed reports to the new Active Lead ([AGENT_REPORTING_STANDARD.md](AGENT_REPORTING_STANDARD.md)).
- Non-active streams: Product Owner day-to-day; ChatGPT milestone summaries + contract/security escalations.
- System Leader/Architect role remains with ChatGPT unless Owner reassigns that role separately.

## Emergency stop

Any agent may STOP for production safety and notify the Product Owner. A stop is not a leadership transfer.
