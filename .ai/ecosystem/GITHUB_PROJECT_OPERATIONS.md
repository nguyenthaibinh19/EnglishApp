# GitHub Project operations — LangstudyGuard

Status: **GOV-0E CLOSED — LEADER ACCEPTED**

Closure covers Project setup and documentation registration only. It does **not** authorize new cross-repository integrations, merges, or deployments.

## 1. Purpose and scope

The private GitHub Project **LangstudyGuard** is the shared coordination board for App, Web, AI, Integration, and Governance workstreams.

It tracks milestones, issues, PRs, and dependencies across repositories. It does **not** replace:

- Canonical source in owning repositories
- ADRs and detailed evidence under each repo’s `.ai/`
- Formal Leader / Product Owner acceptance recorded in repository documentation

Project Status is tracking metadata only. It is **not** an execution permission and does not authorize commits, merges, deployments, VPS/SSH, OAuth, or production activation.

## 2. Project identification

| Field | Value |
|---|---|
| Name | `LangstudyGuard` |
| Owner | `nguyenthaibinh19` |
| Visibility | **PRIVATE** |
| Purpose | Cross-repository milestone and issue coordination |
| Project URL | https://github.com/users/nguyenthaibinh19/projects/1 |
| Created by | Product Owner (existing project; agents must **not** create another) |

Do not publish private issue bodies, credentials, or private-repo document contents into public EnglishApp documentation.

## 3. Views, fields, and workflows

### Views (Owner-confirmed)

1. Overview  
2. App  
3. Web  
4. AI  
5. Integration  
6. Governance  

Workstream-specific views (App / Web / AI / Integration / Governance) filter by the `Workstream` field.

### Fields

| Field | Kind | Notes |
|---|---|---|
| Repository | GitHub built-in | Owning repository of the linked issue/PR |
| Workstream | Project single-select | `App`, `Web`, `AI`, `Integration`, `Governance` |
| Status | GitHub project status | Target workflow below |
| Priority | Issue field | Tracking only |
| Approval Gate | Project single-select | `None`, `Architect Review`, `Owner Approval`, `Approved` |
| Assignees | Built-in | — |
| Linked pull requests | Built-in | — |
| Sub-issues progress | Built-in | — |

**Approval Gate** and related approval fields are **tracking metadata only**. They are **not** execution permissions. Source commits, merges, deployments, and production actions still require their applicable explicit authorizations in briefs and repository docs.

### Status workflow (target)

`Backlog` → `Ready` → `In Progress` → `In Review` → `Blocked` → `Done`

Owner confirmed:

- Workflow **Item added to project** is **ON** and sets new items to `Backlog`.
- Auto-add all repository issues is **NOT** enabled.

Agents must not mutate Project fields, workflows, or views unless a brief explicitly authorizes Project mutation (GOV-0E registration does **not**).

## 4. Issue creation and repository ownership

| Workstream | Day-to-day path | Issue home |
|---|---|---|
| App | Product Owner → ChatGPT → Cursor | `nguyenthaibinh19/EnglishApp` |
| Web | Product Owner → Antigravity Web | `nguyenthaibinh19/langstudyguard-web` (private) |
| AI | Product Owner → Antigravity AI | `nguyenthaibinh19/langstudyguard-ai` (private) |
| Integration | Shared contracts; escalate architecture | Owning repo for the contract/doc under review |
| Governance | Ecosystem docs in EnglishApp `.ai/ecosystem/` | Prefer App issues for GOV tracking; Project is the board |

Rules:

1. Create issues in the **owning** repository. Do not park Web/AI work as App issues by default.
2. Add items to the Project when coordination is needed; do not enable blanket auto-add.
3. Cross-repository contracts and architectural changes escalate to System Leader / Product Owner per [ECOSYSTEM_CHARTER.md](ECOSYSTEM_CHARTER.md) and [CONTRACT_REGISTRY.md](CONTRACT_REGISTRY.md).
4. `C-APP-AI-001` remains **PROPOSED / IN REVIEW**. Do not mark ACCEPTED from Project status alone. No App `LocalAIProvider` implementation is authorized by GOV-0E.
5. Preserve ACCEPTED ≠ COMMITTED ≠ MERGED ≠ DEPLOYED.

## 5. Agent reporting responsibilities

- **Cursor (App):** Detailed technical evidence to ChatGPT; when a brief names a Project item, reference issue number + workstream without pasting private bodies into public docs.
- **Antigravity Web / AI:** Milestone-level reports to ChatGPT unless shared contract/security escalation; day-to-day remains with Product Owner.
- **All agents:** Project Status is not a substitute for updating [MILESTONE_BOARD.md](MILESTONE_BOARD.md) and the owning repo’s `.ai/` when a formal acceptance occurs.
- See [AGENT_REPORTING_STANDARD.md](AGENT_REPORTING_STANDARD.md).

## 6. Approval and escalation

| Event | Required |
|---|---|
| Active-stream implementation acceptance | Active Workstream Lead; Owner may override |
| Breaking shared contract | System Leader review + Product Owner approval **before** consumer implementation |
| Source commit / push / PR / merge | Explicit brief for that action |
| Production / VPS / Google live ops | Explicit Product Owner brief |
| Project mutation (fields, views, automation) | Explicit Owner/Leader authorization |

Escalation: shared architecture, security boundaries, or contract changes → System Leader; final priority/activation → Product Owner.

## 7. Updating milestone status safely

1. Record formal acceptance in the owning repository documentation first (plan / milestone board / current_state as applicable).
2. Then align Project Status / Approval Gate as tracking metadata — only when authorized to touch the Project.
3. Never “close” a FAIL/BLOCKED historical result by moving a Project card alone.
4. Do not treat Project `Done` as merge, deploy, or production readiness.

## 8. Public / private information boundaries

EnglishApp is **public**. This file may name:

- Project name, owner, visibility, URL, view names, field names/values, and public issue titles/numbers

This file must **not** include:

- Private issue bodies, comments, or screenshots with secrets
- Private Web/AI document contents
- Credentials, tokens, age identities, learner data, OAuth material, production DB contents

See [SECURITY_BOUNDARIES.md](SECURITY_BOUNDARIES.md).

## 9. Initial issue inventory and known gaps

Owner-added tracking items (titles and numbers only; not acceptance proof):

| Repo | Issue | Title (public-safe) |
|---|---|---|
| EnglishApp | #1 | Coordination pilot: Windows installer lifecycle |
| EnglishApp | #2 | Slack ↔ Cursor Desktop ↔ ChatGPT bridge |
| EnglishApp | #3 | APP: D5A2D7 Source Integration Review |
| EnglishApp | #8 | APP: Phase 18B.9 Production Readiness |
| EnglishApp | #9 | GOV: GOV-0E Project Governance Setup |
| langstudyguard-ai | #1 | AI-M2 Local AI Service Acceptance |
| langstudyguard-ai | #2 | C-APP-AI-001 Contract Review |
| langstudyguard-web | #1 | W1.3 Redesign Merge Decision |

These items are **tracking only**. They do not prove the corresponding milestones are accepted.

### Issue field confirmation

Product Owner confirmed **EnglishApp #9** (`GOV: GOV-0E Project Governance Setup`) has **Workstream = `Governance`**. No Project mutation by agents.

## 10. How future sessions should use the Project

1. Read [ACTIVE_WORKSTREAM.md](ACTIVE_WORKSTREAM.md) and this file before coordinating cross-repo work.
2. Prefer repository docs + Git history as source of truth for acceptance and SHAs.
3. Use Project views filtered by Workstream for board hygiene.
4. Do **not** create a second GitHub Project.
5. Do **not** start GOV-0C, LocalAIProvider work, merges, or production actions from Project presence alone.
6. ChatGPT / Cursor / Antigravity sessions: update Project cards only when a brief authorizes Project mutation; otherwise document in `.ai/` and leave Project edits to the Owner or an authorized follow-up.

## Related App state (not authorized by GOV-0E)

- **D5A2D7-R2 CLOSED — Leader Accepted**
- **D5A2D7-P1 CLOSED — Leader Accepted** — source `e2160e77c4849606cad5e614dedfd2f79d8088dc` on `phase18b9/d5a2d7-source-candidate`
- **PR NOT CREATED. NOT MERGED. NOT DEPLOYED.**
- Phase 18B.9 OPEN; production NOT READY; Drive NOT CONFIGURED; Cloud Sync OFF; D5A2D2/D5A2D3 FAIL preserved
