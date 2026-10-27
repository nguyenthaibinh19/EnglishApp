# ADR-018 Account Cloud Sync Foundation

Status: Accepted (foundation architecture only — **not** production sync; no HTTP, desktop sync, VPS deploy, or production activation)

## Context

StudyGuard learning data is local-first (per-machine AppData: `vocab.json`, `progress.json`, `attempts.jsonl`, settings). Stable vocabulary UUIDs ([ADR-009](ADR-009-stable-vocabulary-identity.md)) make multi-device restore possible. The product goal is: reinstall or sign in on another Windows PC and restore vocabulary, Progress/SRS, AttemptHistory, and selected account-scoped settings.

Production must not silently overwrite learning state. Authentication already exists (`accounts.db` + session tokens). Phase 18A builds an **isolated sync persistence foundation** without HTTP, automatic sync, VPS deploy, or desktop upload.

## Decision

### Local-first synchronization

- The desktop remains the learner’s working store. Cloud sync is a restore/continuity layer, not a required online dependency for studying.
- Offline: local app continues to work; sync catches up later (future phases).
- No automatic background sync in 18A.

### Authentication and account isolation

- Sync records are keyed by **authenticated user id** (integer, as in `accounts.db` users).
- Trusted server code passes `user_id` after session validation. Sync store itself does not verify tokens.
- Different users never share rows. Same vocabulary UUID on two accounts is allowed and isolated.

### Canonical UUID identity

- Vocabulary entities sync by stable `vocab_id` ([ADR-009](ADR-009-stable-vocabulary-identity.md)).
- Existing valid UUIDs **never** change during sync writes.
- Canonical lexical payload uses vocabulary model v2 fields (`meaning`, not wire-legacy `vi` as primary).

### Revision-based optimistic concurrency

- Each entity has a server-generated integer `revision` (starts at 1 on create).
- Writers supply `expected_revision` (0 for create; current revision for update/delete).
- Mismatch → conflict, **no mutation**.

### Conflict detection — no silent overwrite

- Stale concurrent writes report conflict.
- No last-write-wins for vocabulary entities in this design.
- Future UI (not 18A) must present conflicts to the learner.

### Tombstones for deletions

- Deletes set a tombstone (`deleted=1`) and advance revision.
- Tombstoned entities must **not** be silently resurrected by a create/update that ignores the tombstone.
- 18A rejects put-on-tombstone; explicit undelete remains future work.

### Idempotent retries

- Every write carries a client `operation_id` unique per user.
- The stored operation identity includes: entity key (`user_id` + language + `vocab_id`), delete intent, canonical payload fingerprint, and the writer’s **`expected_revision`**.
- Replaying the **same** `operation_id` with that **exact** mutation returns the original result and does not append a duplicate change.
- Reusing an `operation_id` with a different payload, entity, delete intent, or `expected_revision` is a **conflict**.

### Vocabulary payload validation (sync store)

- Sync accepts an **explicit allowlist**: canonical fields, supported legacy aliases (`vi` / `alt` / `type` / `nl` / `en` / `example`), and valid enrichment (`examples`, `pronunciation.ipa`, controlled `forms`, `note`, `part_of_speech`).
- Unsupported fields are **rejected** before persistence. The store must not silently drop client data while acknowledging a successful write.
- Sensitive keys (tokens / API keys / passwords) are rejected **recursively**, including nested dicts and objects inside `examples[]`.
- Normalization to canonical form still runs after allowlist checks; local Vocabulary Model code is not modified for sync.

### Separate store from accounts.db

- Sync persistence lives in a **separate** SQLite file (`study_sync.db` by default), configurable by path.
- Do not mix sync tables into production `accounts.db` in 18A (keeps backup/rollback and blast radius clear).
- `deploy/hetzner/backup_accounts.py` remains accounts-only until a later ops phase adds sync DB backup.

### Schema versioning / migration (study_sync.db)

- Current code supports schema version **2** (`expected_revision` on changes and entities).
- `init_schema` is idempotent. Version metadata advances to 2 **only after** a successful migration.
- **v1 → v2:** add `expected_revision` if missing; backfill `expected_revision = revision - 1` for rows whose stored value does not already match (so already-correct v2 cells are not rewritten). Creates remain `expected_revision = 0`.
- **Future version:** if stored `schema_version` is **greater** than the code-supported version, opening/migrating must **fail clearly** without downgrading metadata or mutating user rows. Rejection uses a **read-only preflight** before any modifying DDL (no new tables, indexes, or metadata writes). Malformed `schema_version` metadata is also rejected conservatively (never treated as version 0 / license to migrate).
- Schema create/migrate/index/version-update runs inside one SQLite write transaction (`BEGIN IMMEDIATE`); failures roll back. `connect()` closes the connection if initialization fails.
- Failed migrations must not leave a falsely upgraded `schema_version`.

### Entity semantics (by domain)

| Domain | Sync approach (direction) | Phase 18A |
|--------|---------------------------|-----------|
| Vocabulary | Versioned entity + tombstone + revision | **Implemented** (store only) |
| Progress / SRS | Aggregate state; merge rules needed later | Deferred |
| AttemptHistory | Append-oriented events ([ADR-004](ADR-004-learning-attempt-history.md)); idempotent event ids | Deferred |
| Settings | Split account-scoped vs machine-local | Deferred |

### Account-scoped vs machine-local settings

- **Account-scoped (future sync candidates):** study languages, activity toggles, CEFR/reading level, native language preference.
- **Machine-local (do not sync):** paths, install dir, lock/ScreenGuard machine policy, Windows startup, local TTS capability cache, unsigned-update state.
- 18A does not sync settings.

### Initial migration / backup / restore

- Future: one-time upload of local vocab under auth; server assigns revisions; backup before migrate.
- Restore: pull by change cursor into empty or merging local store with conflict UI.
- **Not implemented in 18A.**

### Offline behavior

- Local study always works offline.
- Sync queue / retry / backoff are future client concerns.
- Server store must remain idempotent under retries.

### Rollback and staged production activation

- 18A: library + tests only — **no HTTP routes**, no desktop wiring, no VPS activation.
- Later phases: feature flag / server config before any production traffic.
- Rollback: disable flag; leave `study_sync.db` unused; desktop unaffected.

## Phase 18A vs future

**Implemented in 18A**

- ADR documentation.
- `app/sync_store.py`: SQLite schema + vocabulary put/delete/get/list-changes.
- Isolated pytest coverage with `tmp_path` only.

**Explicitly future (not 18A)**

- HTTP `/api/sync/*` endpoints.
- Client upload/download / automatic sync.
- Progress/SRS merge, AttemptHistory sync, settings sync.
- Production activation, VPS deploy, exe rebuild.
- Conflict resolution UI.
- Changing `backup_accounts.py` or `accounts.db` schema.

## Why

Stable UUIDs already enable sync. Separating a revisioned sync DB from auth keeps production account risk low while proving concurrency, isolation, tombstones, and idempotency before any network surface exists.

## Consequences

Easier: test sync rules without touching live routes; rollback is “don’t ship the flag.” Harder: Progress/Attempt merge remains the riskiest follow-on; operators must eventually back up `study_sync.db` separately.

## Do not

- Do not write sync data into production `accounts.db` in 18A.
- Do not activate production sync or ship HTTP sync routes in 18A.
- Do not regenerate vocabulary UUIDs.
- Do not silently overwrite on conflict or resurrect tombstones.
- Do not store auth tokens or API keys inside vocabulary payloads.
- Do not silently drop unsupported payload fields while acknowledging success.
- Do not treat Progress counters as a substitute for AttemptHistory events when those domains sync later.
