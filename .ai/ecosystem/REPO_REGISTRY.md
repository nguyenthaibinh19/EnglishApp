# Repository registry

Facts and proposals only. Distinguish **confirmed** repository existence from product milestones (ACCEPTED / COMMITTED / MERGED / DEPLOYED).

## Confirmed

### APP — EnglishApp

| Field | Value |
|---|---|
| GitHub | `nguyenthaibinh19/EnglishApp` |
| Visibility | **Public** (confirmed) |
| Local path (this workstation) | `D:\EnglishApp` / worktrees under `D:\EnglishApp-worktrees\` |
| Role | Desktop client, account server, VPS ops memory, **canonical ecosystem governance host** |
| Local memory | `.ai/` |
| Current priority | **Yes** — active workstream |
| Day-to-day lead | ChatGPT (Active Workstream Lead) → Cursor |
| Reporting | Detailed implementation reports to ChatGPT |
| Access note | Public clone does not grant production SSH, secrets, or private-repo access |

### WEB — langstudyguard-web

| Field | Value |
|---|---|
| GitHub | `nguyenthaibinh19/langstudyguard-web` |
| Visibility | **Private** (confirmed) |
| Local path (this workstation) | `D:\langstudyguard-web` |
| Role | Public marketing/download portal (static Astro site) |
| Local memory | `.ai/` (Website-authoritative for Web implementation) |
| Current priority | No — non-active |
| Day-to-day lead | Product Owner → Antigravity Web |
| Reporting to ChatGPT | Milestone-level only (unless shared contract/security escalation) |
| Access note | Private. Agents that can read EnglishApp **must not assume** Web access. Requires appropriate GitHub permission. |

Public-safe remote observations (2026-11-17, D5A2D3 Stage 0; do not treat branch tips as merged/deployed):

| Ref | Observed tip | vs `origin/main` |
|---|---|---|
| `origin/main` | `c17c218` | — |
| `origin/gov0b2/web-documentation-standard` | `c1296181` | **not** ancestor of main (not merged) |
| `origin/feature/w1.3-hybrid-redesign` | `b0b5c8a1` | **not** ancestor of main (not merged) |

Website production deployment remains **NOT AUTHORIZED**. GOV-0B2 documentation was accepted by the System Architect on the review branch; that acceptance is not a merge or deploy.

### AI — langstudyguard-ai

| Field | Value |
|---|---|
| GitHub | `nguyenthaibinh19/langstudyguard-ai` |
| Visibility | **Private** (confirmed) |
| Status | **EXISTS** — AI-M0 accepted; AI-M2 implementation committed (acceptance pending) |
| Local path (this workstation) | `D:\langstudyguard-ai` (canonical). Inactive safety copy on C must not be modified. |
| Role | Local/runtime AI development, evaluation, datasets, model artifacts (planned) |
| Local memory | `.ai/` (private; do not copy private content into public App docs) |
| Current priority | No — non-active |
| Day-to-day lead | Product Owner → Antigravity AI |
| Reporting to ChatGPT | Milestone-level only (unless shared contract/security escalation) |
| Access note | Private. Reading EnglishApp does not grant AI access. |

Public-safe remote observations (2026-11-18):

| Ref | Observed tip |
|---|---|
| `origin/main` | `5cd4dd26a01779322a9d1f638ef20bc9131fda31` |

AI-M0: **System Architect Accepted**. AI-M2 Local AI Service **implementation committed** at the tip above; **architectural acceptance pending**. `C-APP-AI-001` remains **PROPOSED / IN REVIEW**. App `LocalAIProvider` integration is **NOT AUTHORIZED**. Do not treat AI commits as App integration acceptance.

## Shared coordination (not a source repository)

| Item | Status |
|---|---|
| Shared GitHub Project `LangstudyGuard` | **EXISTS** (Owner-created, private). GOV-0E **CLOSED — Leader Accepted**. Ops: [GITHUB_PROJECT_OPERATIONS.md](GITHUB_PROJECT_OPERATIONS.md). Do **not** create another Project. |
| GOV-0C | Not automatically authorized |

## Governance hosting rule

Canonical ecosystem documents live only under:

`EnglishApp/.ai/ecosystem/`

Web and AI repos should link to these files (or to the public GitHub paths). They must not keep independently editable forks of the global governance set.

## Permission reminder

Repository visibility and agent capability are different. Private Web/AI content, VPS credentials, OAuth material, and learner data remain out of scope for public ecosystem text — see [SECURITY_BOUNDARIES.md](SECURITY_BOUNDARIES.md).
