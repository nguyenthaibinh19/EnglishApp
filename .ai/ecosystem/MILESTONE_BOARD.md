# Milestone board (ecosystem)

High-level only. Detailed App phase maps stay in App `plans/` and `roadmap.md`.

Preserve ACCEPTED ≠ COMMITTED ≠ MERGED ≠ DEPLOYED.

## Active workstream — App

| Milestone | Status | Notes |
|---|---|---|
| Phase 18B.8 monitoring | CLOSED — Leader Accepted | Cloud Sync still OFF |
| Phase 18B.9 off-box | **OPEN** | Production NOT READY |
| D5A2D0-P1 source import | CLOSED — accepted import-only | Branch `phase18b9/d5a2d0-p1-source-import` @ `98b590e`; **not merged** |
| D5A2D2 WSL isolation | **OVERALL FAIL** | Formal A/D/E not proven; do not reclassify |
| D5A2D3 helper journal evidence | **OVERALL FAIL** (E) | Original journals recovered; A/D predicates met; E still unproven under original predicate; D5A2D2 not rewritten PASS |
| D5A2D4 interrupted-transfer semantics | **CLOSED — Leader Accepted: REVISE TEST** | E1/E2 accepted; no ACK; historical D2/D3 FAIL preserved |
| D5A2D5 revised isolation evidence | **CLOSED — Leader Accepted** | Revised WSL isolation safety gate A/B/C/D/E1/E2/F/G/H; historical D2/D3 FAIL preserved; not production |
| D5A2D6 source integration readiness | **CLOSED — Leader Accepted** | READY_FOR_SOURCE_INTEGRATION_REVIEW; **not** merge approval; import unmerged; tests required before acceptance |
| D5A2D7 source integration candidate | **R2 CLOSED — Leader Accepted; P1 CLOSED — Leader Accepted** | `e2160e7` on `phase18b9/d5a2d7-source-candidate`; **NOT MERGED**; PR NOT CREATED; NOT DEPLOYED |
| GOV-0A governance planning | **Leader Accepted with corrections** | Planning milestone |
| GOV-0B1 ecosystem docs | **CLOSED — Leader Accepted** | Hosted under `.ai/ecosystem/` |
| GOV-0C | **NOT AUTHORIZED** | Not started automatically |
| GOV-0E GitHub Project Setup | **PROJECT CONFIGURED — DOCUMENTATION REGISTRATION IN PROGRESS** | Private Project `LangstudyGuard`; ops: [GITHUB_PROJECT_OPERATIONS.md](GITHUB_PROJECT_OPERATIONS.md); not CLOSED |

## Non-active — Web

| Milestone | Status (public-safe) |
|---|---|
| GOV-0B2 documentation standard | System Architect Accepted on review branch `gov0b2/web-documentation-standard` @ `c1296181`; **not merged** to `main` (`c17c218`) |
| W1.3 hybrid redesign | Owner Approved on feature branch @ `b0b5c8a1`; **not merged** to `main` |
| Website production deploy | **NOT AUTHORIZED** |

ChatGPT receives Web **milestone summaries** only, unless shared contracts/security escalate. Day-to-day: Product Owner → Antigravity Web.

## Non-active — AI

| Milestone | Status |
|---|---|
| Create `langstudyguard-ai` | **DONE** — private repo exists |
| AI-M0 bootstrap | System Architect Accepted; Owner closure may be separate / not yet recorded here |
| Workspace migration | Verified and documented in AI repo (private detail stays there) |
| App↔AI runtime contract `C-APP-AI-001` | **PROPOSED** — owner TBD (GOV-0C); not accepted |
| Model inference / training / App integration | **Not accepted** |

Day-to-day: Product Owner → Antigravity AI. Milestone reports to ChatGPT only.

## Failure durability

FAIL/BLOCKED results remain on GitHub in the owning repo even when not escalated day-to-day (example: App D5A2D2 FAIL).
