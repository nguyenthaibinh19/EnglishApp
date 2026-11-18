# Integration matrix

Separate **implemented** from **planned**. Do not claim Web, App, and AI are already technically integrated.

## Implemented (confirmed)

| From | To | Mechanism | Status | Notes |
|---|---|---|---|---|
| Desktop client | Account server | HTTPS `/api/*` on `langstudyguard.com` | Implemented | App-owned |
| Desktop updater | GitHub Releases API | Public Releases query | Implemented | App-owned |
| Website | App facts | Manual/curated metadata mirror | Conceptual only | No runtime import; Web private |

## Not implemented / blocked

| From | To | Status |
|---|---|---|
| Website production hosting | Apex domain static routes | **NOT AUTHORIZED** (W1) |
| Website | Live account registration UI | Not implemented |
| App | Google Drive off-box production backup | **NOT CONFIGURED**; Phase 18B.9 open; D5A2D2 FAIL |
| App | Vocabulary Cloud Sync | **OFF** |
| App | Local AI runtime (`langstudyguard-ai`) | AI repo **exists**; integration **not implemented**; `C-APP-AI-001` still PROPOSED |

## Planned (proposed only)

| From | To | Prerequisite |
|---|---|---|
| App | Local AI runtime | Accept C-APP-AI-001 (wire owner ratified: langstudyguard-ai); actual App consumer conformance tests; explicit Owner integration approval |
| Web | App API (future account/download flows) | Owner-approved routing topology; C-WEB-APP-001 |
| Web | Signed release portal | App release contract C-REL-001; verification gates |

## Compatibility validation rule

Before an integration may be marked **implemented** in this matrix:

1. Contract row exists in [CONTRACT_REGISTRY.md](CONTRACT_REGISTRY.md) with non-`proposed` path or explicit acceptance.
2. Evidence is recorded in the owner repo (tests, plan, or acceptance note).
3. Breaking consumer impact has Product Owner approval.
4. System Leader has reviewed cross-repo risk.

Agents must not update this matrix to “implemented” without that evidence.
