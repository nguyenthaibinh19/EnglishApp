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
| owner_repository | **PROPOSED** joint; AI repo not created |
| canonical_document_path | **UNKNOWN** |
| version | **PROPOSED** |
| status | proposed |
| consumer_repositories | App; AI (proposed) |
| compatibility_policy | No implementation claim until AI repo exists and contract is accepted |
| last_accepted_decision | none |
| change_approval_required | Yes |

### C-WEB-APP-001 — Web ↔ App backend

| Field | Value |
|---|---|
| contract_id | C-WEB-APP-001 |
| owner_repository | App (API/domain); Web (static consumers) |
| canonical_document_path | Website ADR-001 routing options; App Caddy/API ownership |
| version | **PROPOSED** for future website deployment topology |
| status | proposed (production website deploy not authorized) |
| consumer_repositories | Web |
| compatibility_policy | Must preserve `/api/*` to account server until Owner-approved topology |
| last_accepted_decision | Website ADR-001 (no W1 DNS/VPS change) |
| change_approval_required | Yes |

## Non-entries

Off-box Drive backup monitoring phrases are App-owned operational status, not a cross-repo publish contract until activation. Google Drive remains **NOT CONFIGURED**.
