# Shared contract registry

## Approval model

1. **Owner repository** maintains the canonical document for a contract.
2. **Consumers** must not fork a second source of truth.
3. Non-breaking clarifications: System Leader may accept; Product Owner may override.
4. **Breaking changes:** System Leader review **and** Product Owner approval **before** implementation in any consumer.
5. No technical agent may independently approve a breaking shared-contract change.
6. Compatibility validation is required before cross-repo integration is claimed — see [INTEGRATION_MATRIX.md](INTEGRATION_MATRIX.md).

## Registry fields

Each entry uses:

`contract_id`, `owner_repository`, `canonical_document_path`, `version`, `status`, `consumer_repositories`, `compatibility_policy`, `last_accepted_decision`, `change_approval_required`

`status` values: `active` | `draft` | `proposed` | `unknown` | `retired`

## Entries

### C-APP-API-001 — Account server HTTP API surface

| Field | Value |
|---|---|
| contract_id | C-APP-API-001 |
| owner_repository | App (`EnglishApp`) |
| canonical_document_path | App code + App ADRs/procedures for `/api/*` (exact OpenAPI **UNKNOWN** / not published here) |
| version | **UNKNOWN** (no ecosystem version tag yet) |
| status | active (implemented server routes exist in App) |
| consumer_repositories | Desktop client (App); future Web account UI **proposed** |
| compatibility_policy | Breaking route/auth changes need Owner approval; installed clients may lag |
| last_accepted_decision | Historical App deploys; no ecosystem versioned acceptance yet |
| change_approval_required | Yes for breaking changes |

### C-WEB-META-001 — Public product metadata honesty

| Field | Value |
|---|---|
| contract_id | C-WEB-META-001 |
| owner_repository | App (product facts); Web mirrors for display |
| canonical_document_path | App `current_state` / release facts; Web `src/data/product.ts` is a **consumer mirror** (private Web path — do not paste private contents here) |
| version | **PROPOSED** ecosystem versioning |
| status | draft |
| consumer_repositories | Web |
| compatibility_policy | Web must not claim Sync ON, Drive configured, or stable website binaries without App-accepted facts |
| last_accepted_decision | Website ADR-001 boundaries (Web repo) |
| change_approval_required | Yes when changing user-visible capability claims |

### C-REL-001 — Download / update distribution

| Field | Value |
|---|---|
| contract_id | C-REL-001 |
| owner_repository | App (GitHub Releases + updater client) |
| canonical_document_path | App updater + release process; Web release procedure is consumer/docs |
| version | **UNKNOWN** |
| status | active for GitHub Releases channel; website-hosted stable artifact **not** authorized |
| consumer_repositories | Installed clients; Web download page |
| compatibility_policy | Do not retire public Releases without client migration plan |
| last_accepted_decision | Website W1 honest gating / App updater behavior |
| change_approval_required | Yes for channel changes |

### C-AUTH-PRIV-001 — Authentication and privacy boundaries

| Field | Value |
|---|---|
| contract_id | C-AUTH-PRIV-001 |
| owner_repository | App |
| canonical_document_path | App invariants/ADRs; Web legal pages remain DRAFT until Owner/legal review |
| version | **UNKNOWN** |
| status | active constraints; legal text draft on Web |
| consumer_repositories | Web (copy only); AI (**proposed**) |
| compatibility_policy | No learner data or secrets in public ecosystem docs or Web static claims beyond accepted facts |
| last_accepted_decision | **UNKNOWN** for final legal acceptance |
| change_approval_required | Yes |

### C-APP-AI-001 — App ↔ local AI runtime

| Field | Value |
|---|---|
| contract_id | C-APP-AI-001 |
| owner_repository | **AI** (`langstudyguard-ai`) — canonical wire/API specification and server schema; **App** (`EnglishApp`) owns the separate `AIProvider` domain interface and consumer mappings |
| canonical_document_path | Private `langstudyguard-ai/.ai/proposals/C-APP-AI-001-PROPOSAL.md` — **single wire-contract source of truth**, not copied into public App docs |
| version | `0.2.0` (System Architect accepted wire contract 2026-11-18) |
| status | active — accepted **wire specification only**; App integration **not implemented** |
| consumer_repositories | App (consumer); AI (producer) |
| compatibility_policy | Account-server remains the default App route; no hidden cloud fallback in explicit local mode; App validates all responses; breaking wire changes need Architect review and Product Owner approval |
| last_accepted_decision | **2026-11-18:** Product Owner ratified AI wire/App domain ownership; System Architect accepted wire contract v0.2.0 after App-side synthetic conformance review (`57ad1bd`); **no** `LocalAIProvider` implementation, integration, deployment or production acceptance authorized |
| change_approval_required | Yes |

### C-WEB-APP-001 — Web ↔ App backend

| Field | Value |
|---|---|
| contract_id | C-WEB-APP-001 |
| owner_repository | **App** — canonical API/domain contract owner. Web is a **consumer** and retains ownership of its own implementation and Website ADR-001. |
| canonical_document_path | App API/domain docs and Caddy/API ownership; Web ADR-001 remains Web-owned implementation/routing policy |
| version | **PROPOSED** for future website deployment topology |
| status | proposed (production website deploy not authorized) |
| consumer_repositories | Web |
| compatibility_policy | Must preserve `/api/*` to account server until Owner-approved topology |
| last_accepted_decision | Website ADR-001 (no W1 DNS/VPS change) |
| change_approval_required | Yes |

## Non-entries

Off-box Drive backup monitoring phrases are App-owned operational status, not a cross-repo publish contract until activation. Google Drive remains **NOT CONFIGURED**.
