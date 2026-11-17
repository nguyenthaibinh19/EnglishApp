# Security boundaries

## Repository isolation

- App, Web, and AI are separate repositories and workspaces.
- Agents must not modify another repository without an explicit brief naming that repo.
- Website zero-deletion and EnglishApp zero-deletion / off-box non-deletion rules remain in force in their home repos.

## Secrets and private material

Never place in public ecosystem docs (or public App commits):

- OAuth client secrets, refresh/access tokens, authorization codes
- age private identities / `AGE-SECRET` material
- Telegram/Brevo/heartbeat credentials
- Emergency Exit password
- Production `.env` contents
- Learner/account database contents
- Private Web operational runbooks beyond public facts
- Private AI datasets or model weights indexes that expose PII

If a governance fact needs a private detail, record a **safe reference** and mark the restricted location as private-authoritative (do not paste the secret).

## Public vs private repos

| Repo | Visibility | Ecosystem implication |
|---|---|---|
| EnglishApp | Public | Hosts `.ai/ecosystem/`; content must be public-safe |
| langstudyguard-web | Private | Link from ecosystem; do not copy private code/docs here |
| langstudyguard-ai | Private (exists) | Link from ecosystem; do not copy private AI datasets, weights indexes, or ops detail here |

Access to private repositories requires GitHub permission. Reading EnglishApp does not grant Web/AI access.

## Production and operations

Still forbidden without a separate Owner/Leader brief:

- VPS/SSH, unit install/enable, production DB access
- Google API / OAuth changes / Drive live ops
- Cloud Sync activation (`STUDY_SYNC_ENABLED`)
- Merge of offbox source-import branch without explicit decision
- Claiming Google Drive configured or production off-box ready

Current preserved gates: Phase 18B.9 **OPEN**; production **NOT READY**; Drive **NOT CONFIGURED**; Cloud Sync **OFF**; D5A2D2 **FAIL**.

## Domain / API protection

Installed clients depend on `langstudyguard.com` account/API routing. Website work must not break `/api/*` without an Owner-approved topology (Website ADR-001). Details of private Web deploy plans stay in the Web repo.
