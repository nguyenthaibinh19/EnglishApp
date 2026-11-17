# Repository registry

Facts and proposals only. Do not treat proposals as created repositories.

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
| Day-to-day lead | Product Owner → Web agent |
| Access note | Private. Agents that can read EnglishApp **must not assume** Web access. Requires appropriate GitHub permission. |

## Proposed

### AI — langstudyguard-ai

| Field | Value |
|---|---|
| Intended GitHub name | `langstudyguard-ai` |
| Visibility | **Expected private** (proposal) |
| Status | **PROPOSED — not created** |
| Role | Local/runtime AI development, evaluation, datasets, model artifacts (planned) |
| Local memory | Future `.ai/` per [REPOSITORY_DOC_STANDARD.md](REPOSITORY_DOC_STANDARD.md) |
| Day-to-day lead (when created) | Product Owner → AI agent (unless Owner changes Active Lead) |
| Access note | Not available. Do not invent commits, branches, or integrations. |

## Governance hosting rule

Canonical ecosystem documents live only under:

`EnglishApp/.ai/ecosystem/`

Web and AI repos should link to these files (or to the public GitHub paths). They must not keep independently editable forks of the global governance set.

## Permission reminder

Repository visibility and agent capability are different. Private Web/AI content, VPS credentials, OAuth material, and learner data remain out of scope for public ecosystem text — see [SECURITY_BOUNDARIES.md](SECURITY_BOUNDARIES.md).
