# GOV-0A — Cross-repository governance blueprint

Status: **Leader Accepted with corrections, 2026-11-17** (planning milestone). Corrections applied in GOV-0B1: canonical governance lives under `EnglishApp/.ai/ecosystem/` only; no fourth governance repo; no independently editable mirrors in Web/AI; no separate global Technical Lead. Documentation only at acceptance time.

Written: 2026-11-17. EnglishApp baseline `origin/main` at documentation time: `4b32180e045cd2bcd6d05969a1314146464fd9cd`.

This amendment **supersedes** any earlier GOV-0A draft leadership/delegation wording. All existing documentation-only and production safety boundaries remain in force.

**Phase 18B.9D5A2D2 remains FAIL** ([PHASE-18B.9D5A2D2-wsl-isolation.md](PHASE-18B.9D5A2D2-wsl-isolation.md)). This blueprint does not reopen or reclassify that result.

## 1. Purpose

Define how ChatGPT, the Product Owner, and technical agents (Cursor, Antigravity/Web, future AI agents) share leadership across:

- `EnglishApp` (desktop + account server + VPS ops memory)
- `langstudyguard-web` (public website)
- a future AI repository (not created in GOV-0A)

## 2. Correct leadership model

ChatGPT has **two distinct responsibilities**:

| Role | Scope |
|---|---|
| **System Leader / Architect** | Cross-repository architecture, roadmap consistency, integration contracts, major milestone reviews |
| **Active Workstream Lead** | Directly manages the currently prioritized workstream: detailed briefs, implementation review, bug analysis, technical reports |

**Current priority: EnglishApp.**

Therefore, until the Product Owner changes it:

1. ChatGPT **directly leads Cursor** on EnglishApp (detailed technical reporting and the existing implementation / review / acceptance workflow remain in force).
2. The **Product Owner directly leads** the Web and AI agents for routine implementation.
3. ChatGPT receives **milestone-level** reports from Web and AI — not routine implementation reports or internal bug churn.
4. The **Product Owner retains final decision authority**.
5. Technical agents **do not independently change** shared integration contracts.

A change of Active Workstream Lead requires an **explicit Product Owner decision** and a documented leadership handoff. Completing an implementation milestone does **not** automatically transfer leadership.

See the proposed protocol: [GOV-0A-LEADERSHIP_HANDOFF_PROTOCOL.md](GOV-0A-LEADERSHIP_HANDOFF_PROTOCOL.md).

### 2.1 Reporting matrix

| Workstream | Who manages day-to-day | What ChatGPT receives | Durable record |
|---|---|---|---|
| **App (active)** | ChatGPT as Active Workstream Lead → Cursor | Full technical reports, diffs, acceptance | EnglishApp `.ai/` + GitHub |
| **Web (non-active)** | Product Owner → Web agent | Milestone summaries, shared-contract proposals, integration risks | Website `.ai/` + GitHub |
| **AI (future, non-active)** | Product Owner → AI agent | Milestone summaries, shared-contract proposals, evaluation/privacy risks | Future AI `.ai/` + GitHub |

Internal bugs and routine iterations on non-active workstreams do **not** require ChatGPT review.

All repositories must keep durable GitHub documentation, including **failures and unresolved tasks** (D5A2D2 FAIL is the current App example).

### 2.2 Shared integration contracts

Examples (illustrative, not an exhaustive contract list):

- Public product metadata mirrored on the website (`version`, languages, honesty about Cloud Sync / downloads)
- Account-server API surface and domain routing (`langstudyguard.com` `/api/*` protection)
- Release / updater channels
- Off-box backup and monitoring status language (App-owned; website must not invent SUCCESS)

Contract changes require System Leader review plus Product Owner approval before any agent implements them across repos.

## 3. Documentation architecture

### 3.1 Canonical structural reference: EnglishApp `.ai/`

EnglishApp’s existing tree is the **canonical structural reference** for repository-local agent documentation:

```text
.ai/
  README.md                 # memory purpose + reading order
  current_state.md          # product/position snapshot
  architecture.md           # subsystem boundaries
  invariants.md             # must-not-break rules
  roadmap.md                # direction
  lessons.md                # durable lessons
  decisions/                # ADRs
  plans/                    # phase/plan records (including failures)
  procedures/               # how-to checklists
  agent_playbook/           # workflow, diff standard, ACTIVE_HANDOFF, handoffs/
```

Authority split inside a repo remains: tests/code for behavior; ADRs for why; `current_state.md` for position; `ACTIVE_HANDOFF.md` for rolling coordination (not a second product state).

### 3.2 Proposed global `.ai/ecosystem/` (preserved proposal)

Not created in GOV-0A. Proposed later (GOV-0B+), living either in a small dedicated governance repo or as a mirrored docs package:

```text
.ai/ecosystem/
  README.md
  LEADERSHIP.md                      # System Leader vs Active Workstream Lead
  LEADERSHIP_HANDOFF_PROTOCOL.md     # adopted form of the GOV-0A proposal
  ACTIVE_WORKSTREAM.md               # which repo is currently active
  INTEGRATION_CONTRACTS.md           # shared contracts index
  REPOSITORIES.md                    # App / Web / AI ownership map
  MILESTONE_REPORTING.md             # what non-active streams must send
  RISK_REGISTER.md                   # cross-repo risks (optional)
```

Each product repo keeps its own full `.ai/` tree. Ecosystem docs do **not** replace repo-local `current_state.md`.

### 3.3 Future AI repository documentation frame

When the AI repo is initialized (not in GOV-0A), use the same skeleton, adapted for:

| EnglishApp analogue | AI-repo adaptation |
|---|---|
| `architecture.md` | Training/serving boundaries, eval harness ownership |
| `decisions/` | Model/data/privacy ADRs |
| `procedures/` | Dataset ingest, eval runs, artifact promotion |
| `invariants.md` | No PII in public artifacts; no silent contract changes |
| `plans/` | Experiment plans + failed eval records |
| `agent_playbook/` | AI-agent workflow + ACTIVE_HANDOFF |

Plus AI-specific folders (proposed): `datasets/`, `evaluations/`, `model_artifacts/` **indexes** (not raw secrets), and privacy procedures.

## 4. Website documentation gap assessment (read-only)

Audited path: `D:\langstudyguard-web\.ai\` (not modified).

### 4.1 Existing equivalents

| EnglishApp structure | Website status |
|---|---|
| `current_state.md` | Present |
| `architecture.md` | Present |
| `invariants.md` | Present (strong zero-deletion / boundary rules) |
| `roadmap.md` | Present |
| `decisions/` | Present (ADR-001 website boundaries) |
| `procedures/` | Partial (`RELEASE_DISTRIBUTION.md`) |
| Handoff | Present as `AGENT_HANDOFF.md` (combined orientation + handoff) |
| Design evidence | Present under `docs/design/` (outside `.ai/`, appropriate for W1 visuals) |

### 4.2 Missing relative to EnglishApp canonical structure

| Gap | Risk | GOV-0B suggestion |
|---|---|---|
| No `.ai/README.md` reading-order index | New agents may miss authority hierarchy | Add Website `.ai/README.md` mirroring App pattern |
| No `agent_playbook/` split (`AI_AGENT_WORKFLOW`, diff standard, `ACTIVE_HANDOFF`, dated `handoffs/`) | Coordination relies on one fat `AGENT_HANDOFF.md`; no rolling STOP checkpoint separate from orientation | Introduce playbook files; keep Website-specific verify commands |
| No `lessons.md` | Recurring Web pitfalls may stay in chat only | Add after next closed Web milestone |
| Thin `plans/` | Failures/unresolved Web tasks may not be durable | Add `plans/` for W-phase records including FAIL/BLOCKED |
| No explicit documentation-checkpoint policy pointer | Unclear what Web agents may push without source | Port App section-11 idea, adapted to Astro/Web |
| `current_state.md` cites older EnglishApp baselines | Integration drift vs App HEAD | Milestone sync of reference SHAs when App releases |

### 4.3 Outdated / inconsistent records (do not silently rewrite in GOV-0A)

- Website `current_state.md` snapshot date **2026-11-11**; App off-box state has advanced through D5A2D2 (2026-11-16) — expected workstream lag, but product-copy references may drift.
- Website ADR-001 / handoff still describe ChatGPT Leader authorization for cross-repo edits in a single “Leader” sense; under this amendment, cross-repo contract changes need **System Leader review + Product Owner final authority**, while Web day-to-day is Product Owner–led.
- Website still correctly forbids touching EnglishApp without approval — **keep that boundary**.

### 4.4 Website-specific rules that must remain unchanged

1. Zero-deletion / no destructive cleanup of `dist/` without owner action (`invariants.md`).
2. Repository isolation from EnglishApp (ADR-001).
3. No DNS / Cloudflare / Caddy / VPS changes in W1.
4. Honest download gating (no false “stable website binary” claims).
5. Legal pages remain DRAFT until owner/legal review.
6. Non-destructive verify path preferred over `astro build` while `dist/` exists.

### 4.5 Recommended improvements for GOV-0B (not authorized now)

1. Add Website `.ai/README.md` + slim `agent_playbook/` without weakening Website invariants.
2. Split rolling `ACTIVE_HANDOFF.md` from orientation handoff.
3. Add `plans/` for W1.3+ outcomes including unresolved items.
4. Align leadership wording with this amendment after Product Owner acceptance.
5. Define milestone-report template Web → ChatGPT (System Leader).

## 5. EnglishApp local obligations under this model

While App is the active workstream:

- Cursor continues detailed reporting to ChatGPT.
- Docs-only checkpoints under standing App policy remain valid.
- Failures stay on GitHub (D5A2D2 FAIL preserved).
- Web/AI routine work does not interrupt App briefs unless a shared contract or Product Owner priority change says so.

## 6. Explicit non-goals of GOV-0A

- No Website documentation edits
- No new AI repository
- No source edits in EnglishApp application tree
- No merge of `phase18b9/d5a2d0-p1-source-import`
- No VPS / Google / production activation
- No reclassification of D5A2D2

## 7. Proposed acceptance criteria for GOV-0A

Leader / Product Owner may accept GOV-0A when they agree that:

1. The dual ChatGPT role model and current App priority are correct.
2. The reporting matrix for active vs non-active workstreams is correct.
3. The EnglishApp `.ai/` structure is the canonical template.
4. The Website gap assessment is accurate enough to schedule GOV-0B.
5. The leadership handoff protocol is the right draft to adopt later into `.ai/ecosystem/`.

## 8. STOP

GOV-0A is planning only. Await Product Owner / Leader review before GOV-0B or any cross-repo documentation implementation.
