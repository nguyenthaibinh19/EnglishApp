# System architecture (ecosystem view)

High-level only. Repo-local `architecture.md` files own subsystem detail.

## Confirmed components

```text
Windows desktop client (EnglishApp)
        |
        | HTTPS /api/*
        v
Account server on Hetzner VPS (EnglishApp deploy tree)
        |
        | domain langstudyguard.com (account/API traffic today)
        v
Learners / installed clients

Public website (langstudyguard-web) — separate repo, static site
        |
        | conceptual product metadata only (no runtime import from App)
        v
Future public download/marketing surface (deployment NOT authorized in W1)
```

## Ownership

| Concern | Owner repository |
|---|---|
| Desktop study lock, local DBs, updater client | App |
| Account server, VPS units, health monitoring, off-box backup design | App |
| Marketing site, download portal UX, static legal drafts | Web |
| Local AI runtime / eval / datasets | AI (**proposed**, not created) |
| Cross-repo governance docs | App `.ai/ecosystem/` |

## Explicit non-claims

- Web does **not** import App Python modules or production databases.
- AI repository does **not** exist yet; no App↔AI or Web↔AI technical integration is implemented.
- Website deployment to production DNS/Cloudflare/Caddy is **not** authorized by this document.
- Off-box Google Drive backup remains **NOT CONFIGURED**; Cloud Sync remains **OFF**.

## Integration discipline

Implemented vs planned edges are listed in [INTEGRATION_MATRIX.md](INTEGRATION_MATRIX.md).  
Shared contracts are listed in [CONTRACT_REGISTRY.md](CONTRACT_REGISTRY.md).

Any new cross-repo edge requires: contract entry, compatibility validation, System Leader review, and Product Owner approval for breaking changes.
