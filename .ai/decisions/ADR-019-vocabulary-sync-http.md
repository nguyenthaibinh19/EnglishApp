# ADR-019 Authenticated Vocabulary Sync HTTP API

Status: Accepted (source HTTP architecture only — **not** production activation; sync stays default-off, not deployed, no desktop client)

## Context

Phase 18A ([ADR-018](ADR-018-account-cloud-sync.md), accepted commit `94f1bf7`) stores versioned vocabulary in `study_sync.db`. The desktop still has no sync client. Production must not gain a live sync surface by accident.

Phase 18B.1 exposes that store through the **existing** account server process (`app/account_server.py`). It does not add a second public service, a second authentication system, desktop upload, or a VPS deploy.

## Decision

### Same process, feature-gated

- Routes live on the account server already used for login and AI.
- Sync is **disabled unless** the server process environment variable `STUDY_SYNC_ENABLED` is exactly `1` (after trim). Unset, empty, `true`, `yes`, and `0` stay off.
- While disabled, sync paths return **404** `{"error": "Không có chức năng này."}` — the same body as an unknown POST route — and **must not** open, create, or modify `study_sync.db`.
- Production systemd / `server.env` must leave the flag unset until a later activation phase. Rollback is: unset the flag and restart; `study_sync.db` is left unused; login and AI routes keep working.
- `deploy/hetzner/setup.sh` copies the `account_server.py` import closure, including `sync_http.py`, `sync_store.py`, `vocab_identity.py`, and `vocabulary_model.py`, so the process can start while the flag is unset. Copying those files does not open `study_sync.db`.
- Login and AI routes keep calling `account_store.login()` and `account_store.user_for_token()` with no directory argument. There is no `ACCOUNT_DATA_DIR` override.
- Sync authentication calls the same `account_store.user_for_token(token)`, so it reads the same `accounts.db` as login.
- Optional `STUDY_SYNC_DIR` selects the directory for `study_sync.db` only. If unset, the sync module directory is used. The flag still has to be `1` before any connect.

### Authentication

- Sync routes require `Authorization: Bearer <session token>`.
- Body field `token` is **not** accepted for sync (existing AI routes may still accept it).
- `user_id` comes only from `account_store.user_for_token(token)` — the same call existing AI routes use. A JSON `user_id` is ignored and never selects the row owner.
- Missing, invalid, expired, or inactive-account tokens return **401** `{"error": "Authentication required."}`. `user_for_token` already requires `users.active = 1` and an unexpired session. These failures do not open `study_sync.db`.

### Endpoints (POST only)

All three are POST, matching the existing account server. No GET sync API. Paths match exactly, including existing `/api/login`, `/api/grade`, `/api/reading`, `/api/listening`, and `/api/enrich`. A query string does not select those routes or the sync routes.

| Path | Purpose |
|------|---------|
| `POST /api/sync/vocabulary/put` | Create or update one vocabulary entity |
| `POST /api/sync/vocabulary/delete` | Tombstone one entity |
| `POST /api/sync/vocabulary/changes` | Page this user’s changes after a cursor |

#### `POST /api/sync/vocabulary/put`

Request JSON object. Required keys:

| Field | Type | Rule |
|-------|------|------|
| `language_code` | string | Canonical study language |
| `vocab_id` | string | Stable vocabulary UUID |
| `payload` | object | Phase 18A allowlist; nested secrets rejected |
| `expected_revision` | integer | `0` to create; current revision to update. Bool and float rejected |
| `operation_id` | string | 1..128 chars; idempotency key per user |

`user_id` may be present and is discarded. Any other key → **400**.

Success **200**:

```json
{
  "language_code": "nl",
  "vocab_id": "<uuid>",
  "revision": 1,
  "deleted": false,
  "payload": {},
  "change_cursor": 1,
  "operation_id": "<id>",
  "expected_revision": 0
}
```

The wire object does **not** include `user_id`.

#### `POST /api/sync/vocabulary/delete`

Required keys: `language_code`, `vocab_id`, `expected_revision` (integer ≥ 1), `operation_id`. `user_id` discarded. No payload field.

Success **200** uses the same record shape with `"deleted": true`. The stored payload is the last live payload (tombstone does not wipe it).

#### `POST /api/sync/vocabulary/changes`

| Field | Type | Rule |
|-------|------|------|
| `after_cursor` | integer | Optional, default `0`. Exclusive lower bound |
| `limit` | integer | Optional, default `100`. Must be ≥ 1 and ≤ `500` (`sync_store.MAX_CHANGE_LIMIT`). Larger values are **400**, not silently truncated |
| `language_code` | string | Optional filter. Omit to include every study language for this user. Empty string is invalid |

`user_id` discarded. Other unknown keys → **400**.

Success **200**:

```json
{
  "changes": [
    {
      "cursor": 1,
      "language_code": "nl",
      "vocab_id": "<uuid>",
      "revision": 1,
      "deleted": false,
      "payload": {},
      "operation_id": "<id>",
      "expected_revision": 0
    }
  ],
  "next_cursor": 1,
  "has_more": false,
  "limit": 100
}
```

### Cursor semantics

- `cursor` is `vocabulary_changes.change_id` (database-wide autoincrement), not a per-user counter.
- A page contains only the authenticated user’s rows with `change_id > after_cursor`, ascending. Optional `language_code` narrows that set.
- Other users’ inserts can leave gaps. Clients resume with the returned `next_cursor`. They must not assume `cursor + 1`.
- `next_cursor` is the last change’s `cursor` in this page, or the request `after_cursor` when the page is empty.
- `has_more` is true only when another matching row exists after this page (probed with limit 1). It is not inferred from page length alone.
- History is never returned unbounded. One response holds at most 500 changes.

### Idempotency and conflicts

Store rules from ADR-018 apply unchanged:

- Same `operation_id` plus the same entity, delete intent, canonical payload, and `expected_revision` → **200** with the original record (no second change row).
- Same `operation_id` with any of those different → **409**, no mutation.
- Stale or impossible `expected_revision`, tombstone resurrection, delete of a missing/already-deleted entity → **409**, no mutation.

**409** body:

```json
{
  "error": "Sync conflict.",
  "current": {
    "language_code": "nl",
    "vocab_id": "<uuid>",
    "revision": 1,
    "deleted": false,
    "change_cursor": 1,
    "expected_revision": 0
  }
}
```

`current` is `null` when no entity row exists. `current` does not include payload, operation id, or `user_id`.

### Status codes

| Code | When | Body `error` |
|------|------|----------------|
| 200 | Accepted write or change page | (no error field) |
| 400 | Malformed JSON, non-object JSON, unexpected keys, store `SyncValidationError` | `Invalid sync request.` |
| 401 | Missing, invalid, expired, or disabled-account Bearer | `Authentication required.` |
| 404 | Sync flag not exactly `1` | `Không có chức năng này.` |
| 409 | `SyncConflictError` | `Sync conflict.` |
| 413 | `Content-Length` greater than 32768 bytes | `Sync request is too large.` |
| 500 | `SyncSchemaError`, SQLite errors, any other server failure | `Sync store unavailable.` |

The server reads a body only after the flag check, the size check, and a successful Bearer check. Oversized `Content-Length` is rejected **without** reading the body and **without** opening `study_sync.db`.

500 responses are fixed strings. They do not include exception text, stack traces, SQLite paths, passwords, tokens, or provider secrets. The process may log the exception **type name** to stderr.

Each sync attempt opens at most one `study_sync.db` connection and closes it before the response returns, including on failure after connect.

### Explicitly unchanged

- `/api/login`, `/api/grade`, `/api/reading`, `/api/listening`, `/api/enrich` keep their current auth (Bearer **or** body `token`) and error behavior.
- Non-sync oversized bodies stay **400**, not 413.
- No desktop sync client, no AppData migration, no Progress/SRS/AttemptHistory changes, no `accounts.db` schema change, no ScreenGuard or Windows Startup change.

## Why

A default-off flag on the process that already authenticates learners is the smallest way to test a real HTTP contract without turning production sync on. Keeping `user_id` server-side and refusing body tokens on these routes closes the two easiest ways to write another account’s vocabulary.

## Consequences

Easier: local integration tests on `127.0.0.1` with temporary databases; rollback does not require a schema downgrade. Harder: operators must treat `STUDY_SYNC_ENABLED=1` as a production change even though the code can ship dark. Desktop sync and conflict UI remain later work. A separate sync backup exists in source ([ADR-020](ADR-020-sync-database-backup.md)) but is not scheduled and does not by itself authorize activation.

## Do not

- Do not set `STUDY_SYNC_ENABLED=1` on the VPS in this phase.
- Do not accept a client `user_id` or a body `token` as sync authority.
- Do not return store or SQLite exception text to the client.
- Do not let a disabled flag create `study_sync.db`.
