# Ecosystem charter

## Purpose

Define who decides what across App, Web, and the future AI repository.

## Roles

| Role | Actor | Authority |
|---|---|---|
| Product Owner | Human owner | Final authority on priority, leadership transfer, production activation, and breaking contract approval |
| System Leader / Architect | ChatGPT | Cross-repo architecture, roadmap consistency, integration contracts, major milestone reviews |
| Active Workstream Lead | ChatGPT while App is active (unless Owner reassigns) | Detailed briefs, implementation review, bug analysis, and technical reports for the **active** workstream |
| Technical agents | Cursor (App), Web agent, future AI agent | Implement only inside the assigned repository and brief |

There is **no** separate global Technical Lead who may override this model.

## Dual ChatGPT responsibilities

1. **System Leader / Architect** — always ecosystem-wide.
2. **Active Workstream Lead** — only for the currently prioritized workstream.

These are distinct. Holding System Leader does not imply day-to-day control of non-active streams.

## Current default (until Owner changes it)

- Active workstream: **App** (`EnglishApp`)
- ChatGPT directly leads Cursor on App and receives detailed technical reports.
- Product Owner directly leads Web and AI agents.
- ChatGPT receives **milestone-level** reports from Web/AI, plus escalations that touch shared architecture or contracts.
- Product Owner retains final authority.

## Hard rules

1. Completing a milestone does **not** transfer Active Workstream Lead.
2. Changing product priority does **not** by itself grant operational permissions (SSH, deploy, OAuth, merges, production flags).
3. A leadership transfer requires explicit Product Owner approval and durable handoff evidence — see [LEADERSHIP_HANDOFF_PROTOCOL.md](LEADERSHIP_HANDOFF_PROTOCOL.md).
4. Technical agents must not independently approve or implement breaking shared-contract changes — see [CONTRACT_REGISTRY.md](CONTRACT_REGISTRY.md).
5. Local repo invariants (including Website zero-deletion and isolation) are not weakened by this charter.

## Decision classes

| Decision | Approver |
|---|---|
| Active workstream / Active Lead change | Product Owner (+ handoff record) |
| Breaking shared contract | Product Owner after System Leader review |
| Non-breaking contract clarification | System Leader; Owner may override |
| Active-stream implementation acceptance | Active Workstream Lead; Owner may override |
| Non-active routine bugs | Product Owner (no ChatGPT deep review required) |
| Production activation / VPS / Google live ops | Product Owner with explicit brief |
