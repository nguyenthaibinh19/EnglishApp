# ADR-022 Event-first Progress Sync and Automatic Account Sync

Status: **Accepted — architecture only; not implemented.**

This document does not authorize schema changes, HTTP routes, a Windows client, timer installation, deployment, or `STUDY_SYNC_ENABLED=1`. Nothing in this ADR is implemented behavior.

Baseline: `d2777913e7d175fea0ad26c629c5cf7f2c0feca8` (Phase 18B.4). Vocabulary sync remains the Accepted contracts in [ADR-018](ADR-018-account-cloud-sync.md), [ADR-019](ADR-019-vocabulary-sync-http.md), [ADR-020](ADR-020-sync-database-backup.md), and [ADR-021](ADR-021-sync-backup-alerts.md). Production gates remain [PHASE-18B.3-production-readiness.md](../plans/PHASE-18B.3-production-readiness.md). Phase 18B.5 stays the next repo-only milestone and is not started here.

## Product decision (approved)

- Study stays local-first. A learner can answer with no network.
- While the Windows app is running and the session is valid, account sync runs automatically.
- Ordinary updates do not need a reinstall, a restart, a Restore button, or a Sync button.
- Offline study catches up when the network returns.
- Several Windows devices may use one account.
- One account must not read or write another account's events or progress.
- A separate always-running Windows service is out of scope. Sync lives in the running app.

## What the code does today

Implemented today, and unchanged by this ADR:

- `accounts.db` holds users and sessions. Sync already takes `user_id` only from `account_store.user_for_token()` on `Authorization: Bearer`. A body `user_id` is not authority ([ADR-019](ADR-019-vocabulary-sync-http.md)).
- `study_sync.db` is schema version **2**. It stores `vocabulary_entities` and `vocabulary_changes` only. `change_id` is the vocabulary cursor. `UNIQUE (user_id, operation_id)` makes a vocabulary retry idempotent. A future schema is rejected before DDL. Vocabulary change pages use `after_cursor`, return `next_cursor` and `has_more`, and cap a page at 500 ([ADR-019](ADR-019-vocabulary-sync-http.md)).
- `LearningAttempt` ([ADR-004](ADR-004-learning-attempt-history.md)) is one finalized answer: timestamp, language, word snapshot, `user_answer`, `expected_answer`, `correct`, verdict (`exact` / `near` / `wrong`), `hint_used`, prompt, and optional `vocab_id`. There is **no `event_id`**. `AttemptHistory` appends JSONL and skips a failed append without failing the session.
- `Progress.record` increments `seen` / `correct` / `wrong` / `streak`, then `apply_review_to_stats`. Mastery (`correct`) means an exact answer with no hint. SRS v2 ([ADR-006](ADR-006-srs-v2.md)) writes `interval_days` and `due_at` from the streak ladder `1, 3, 7, 14, 30` days. A non-mastered review sets interval 0 and due at the review time. Session requeue is not SRS.
- Progress, attempts, and `vocab.json` live under `languages/{code}/` in the machine data directory. They are **not namespaced by account**. `progress.json` `days` is the device's local calendar, not UTC.
- Vocabulary identity is the immutable UUID from [ADR-009](ADR-009-stable-vocabulary-identity.md). Legacy attempts may have an empty `vocab_id`.

## Server data model (not implemented)

`accounts.db` stays users and sessions. No progress tables there.

A future schema **v3** of `study_sync.db` adds the tables below. v3 is additive. Vocabulary tables and their revision, tombstone, and `operation_id` rules stay as they are. Opening a database newer than the code still fails before any DDL. The version advances to 3 only after the new tables and indexes commit. A failed migration leaves the stored version at 2.

### `learning_attempts`

Immutable accepted events. One row is the full Mistake Book record for that answer, not a counter increment.

| Column | Rule |
|---|---|
| `user_id` | Integer from the Bearer session. Not taken from JSON. |
| `event_id` | Client UUID, generated once, 1..128 chars, stable across retries. |
| `device_id` | Client UUID for the install. Not a credential and not an authorization key. |
| `language_code` | Canonical study language. |
| `vocab_id` | Stable vocabulary UUID. Required. |
| `verdict` | `exact`, `near`, or `wrong`. |
| `mastered` | Integer 0 or 1. Must be 1 only when verdict is `exact` and `hint_used` is 0. |
| `hint_used` | Integer 0 or 1. |
| `occurred_at` | Client UTC timestamp. Evidence of when the device thought the answer happened. Not the SRS clock. |
| `received_at` | Server UTC timestamp, assigned on first accept. |
| `server_seq` | Monotonic id assigned on first accept. |
| `algorithm_id` | The ladder the server applied. This design accepts only `ladder-v2`. |
| `word_snapshot` | Spelling at answer time. Display only. Not identity. |
| `user_answer` | The learner's answer. Required string. May be empty. |
| `expected_answer` | The expected answer. Required string. May be empty only for a legacy imported line that has no expected text. New quiz events must be non-empty. |
| `prompt` | Meaning prompt shown for the question. Required string. May be empty. |

Primary key: `(user_id, event_id)`.

Indexes: `(user_id, server_seq)`, `(user_id, language_code, vocab_id, server_seq)`.

Text bounds, counted in Unicode code points, not bytes: `word_snapshot`, `user_answer`, `expected_answer`, and `prompt` are each at most **500**. Over-long text is rejected. The server does not truncate, because truncation would change the stored attempt and the idempotency comparison. A rejected event inserts nothing and does not consume a history-quota slot.

The ingest allowlist is exactly the client fields above except `user_id`, `received_at`, and `server_seq`, which the server assigns. `user_id` in JSON is an unexpected field and is rejected. Unknown fields are rejected. Bool is not an integer. Nested objects are rejected. The same forbidden credential keys already rejected by vocabulary sync are rejected here, including inside any future nested value. Answer text is account-isolated: every read and write filters on the session `user_id`.

Logs, alerts, and HTTP error bodies must not contain `user_answer`, `expected_answer`, `prompt`, `word_snapshot`, other vocabulary content, tokens, or secrets. A safe log may include `event_id`, HTTP status, and integer sizes.

Quota, enforced later by the Phase 18B.10 gate and not by this ADR: each newly accepted event counts once toward the account history quota, and the stored text counts toward the account storage quota. A duplicate `event_id` does not count again. Validation failures and conflicts do not insert a row. Silent trimming of old attempts is not part of this proposal.

### `user_progress`

Derived state. Not a client-uploaded `progress.json`.

| Column | Rule |
|---|---|
| `user_id`, `language_code`, `vocab_id` | Primary key. |
| `seen`, `correct`, `wrong`, `streak` | Fold of accepted events. |
| `interval_days`, `due_at` | Result of `ladder-v2` after the latest accepted event. |
| `last_event_id`, `last_server_seq` | Last event applied to this row. |
| `algorithm_id` | `ladder-v2`. |
| `state_version` | Increments by one when this row's fold changes. Starts at 1 for the first event. |
| `updated_at` | Server time of that fold. |

### `progress_changes`

Incremental journal for devices. Separate from `vocabulary_changes` so a vocabulary cursor is never a progress cursor.

The journal row stores the progress snapshot **after** this event was folded. Later events must not rewrite an older snapshot. The changes API reads this snapshot; it does not recompute history from the current `user_progress` row.

| Column | Rule |
|---|---|
| `change_id` | Integer primary key, autoincrement. This is the download cursor. |
| `user_id`, `event_id` | The accepted event. Unique together. |
| `server_seq` | Same accept order as `change_id` for that insert. |
| `seen`, `correct`, `wrong`, `streak` | Snapshot after this event. |
| `interval_days`, `due_at` | Snapshot after this event. |
| `state_version` | `user_progress.state_version` after this event. |
| `algorithm_id` | `ladder-v2`. |
| `created_at` | Server time. |

Unique: `(user_id, event_id)`. Index: `(user_id, change_id)`.

Attempt text stays on `learning_attempts` and is joined when a page is built. It is not copied into the journal.

### Accept transaction

One `BEGIN IMMEDIATE` transaction:

1. Look up `(user_id, event_id)`.
2. If the stored event matches this delivery, including `user_answer`, `expected_answer`, `prompt`, and `word_snapshot`, stop and return the original result. Do not insert another journal row and do not change counters.
3. If the same `event_id` arrives with a different vocab, language, device, verdict, mastered flag, hint flag, `occurred_at`, algorithm, word snapshot, user answer, expected answer, or prompt, conflict and make no change.
4. Otherwise insert the attempt, fold it into `user_progress`, and insert one `progress_changes` row that holds the post-fold snapshot.
5. Commit. The HTTP success is after the commit. The success body includes `change_id`, `server_seq`, and `progress_after` for that insert. The client uses that body to update its confirmed projection. It does not move the download cursor from this response.

A conflict or a failed commit leaves the previous attempt and progress rows in place.

### Identity and retention

The server discards a JSON `user_id`. The session user is the only owner.

Accepted events are not deleted to satisfy the 14-file backup rotation. That rotation copies the whole `study_sync.db`, so v3 rows are inside the existing backup once they exist. Row retention is a quota problem for the Phase 18B.10 gate: a new event that would pass the account quota is rejected, and older events stay. Silent trimming is not part of this proposal.

A vocabulary tombstone does not delete attempts or the progress row. The client must not recreate the vocabulary entity from a progress row.

## Download and restore (not implemented)

A new device restores by paging this account's `progress_changes` from cursor `0`. That page stream is both the full accepted attempt history and the authoritative Progress/SRS. The device does not upload or add `progress.json` to reconstruct either one.

Proposed route, default-off with the existing flag: `POST /api/sync/progress/changes`.

Request allowlist: `after_cursor`, `limit`. No `user_id`. Optional `language_code` filters one language and does not change cursor meaning: the cursor remains the global per-account `change_id`, and a language filter must not skip another language's ids into the stored cursor. The normal restore and the normal poll omit `language_code`.

Response, session user only:

```text
{
  "changes": [ { "change_id", "server_seq", "event", "progress_after" } ],
  "next_cursor",
  "has_more",
  "limit"
}
```

`event` is the attempt row, including the bounded answer, expected answer, and prompt. `progress_after` is the journal snapshot for that `change_id` (`seen`, `correct`, `wrong`, `streak`, `interval_days`, `due_at`, `state_version`, `algorithm_id`). Rows are ordered by ascending `change_id` and are exactly the rows with `change_id` greater than `after_cursor`. Page size default is 100 and maximum is 100, which is below the vocabulary cap of 500. An empty page returns `next_cursor` equal to `after_cursor` and `has_more` false.

Server ordering is `change_id` / `server_seq` only. `occurred_at` is inside `event` and is not a sort key.

The account database keeps two projections per vocabulary. They are not one row.

| Projection | Written from | Used for |
|---|---|---|
| Confirmed | A server `progress_after` snapshot, from a download page or from an upload success body. | The account's server fold. Compared by `state_version`. |
| Provisional | Confirmed, plus local attempts that are not yet covered by that confirmed snapshot. | Offline study and the Pending display. Never compared as if it were `state_version`. |

An older snapshot must not be rejected just because the provisional streak is ahead, or because an upload success already stored a newer confirmed version. The page is validated as a whole before any write. Validation failure writes nothing and leaves the cursor.

A local attempt is covered when its outbox row is acknowledged and the confirmed `state_version` for that vocabulary is greater than or equal to the `state_version` on that acknowledgement. Provisional folds only uncovered attempts, in local commit order, on top of confirmed. Folding a covered attempt again would double-count it.

Validation, in `change_id` order:

1. An empty page commits nothing. The cursor stays.
2. Each `change_id` is strictly greater than the previous id in the page and strictly greater than the durable cursor. Any other order fails validation.
3. A new `event_id` will be inserted once. The same id with the same body is an idempotent skip. The same id with a different body is an integrity conflict.
4. Compare `progress_after.state_version` with the **confirmed** version only.
   - No confirmed row, or the snapshot version is greater: the snapshot will replace confirmed.
   - The snapshot version is lower: skip that snapshot. Do not change confirmed. Still persist a new attempt from step 3.
   - The snapshot version is equal: the counters, streak, interval, `due_at`, and `last_event_id` must match the confirmed row. A match skips the snapshot. A difference is an integrity conflict.
5. Any integrity conflict fails the page. Pending outbox rows are left in place.

If validation succeeds, one transaction:

1. Insert each new attempt. Do not insert a second row for an event already stored.
2. Replace confirmed only for snapshots that validation marked newer.
3. Rebuild provisional for each touched vocabulary from the confirmed row plus local attempts not yet covered by it. A pending or unacknowledged outbox row is not deleted.
4. Set the progress cursor to the last `change_id` in the page.
5. Commit. A failed commit leaves attempts, both projections, and the cursor as they were.

The cursor advances only inside that commit, and only after the whole page validated. The client does not store the HTTP `next_cursor` before the commit. A replay of an already applied page is a no-op because those `change_id`s are not greater than the cursor.

### Upload acknowledgement ahead of the cursor

An upload success can arrive before this device has downloaded every earlier `change_id`. Other devices may own those earlier ids. The client, in one local transaction, marks that outbox row acknowledged, stores the attempt if it is not already stored, and applies `progress_after` to confirmed using the same version rules as a page: newer replaces, older does not regress, equal must match. It does **not** set the download cursor to that `change_id`. Moving the cursor there would skip events this device has not applied.

A later page still contains the acknowledged event and any gap before it. The event is already stored, so it is not inserted again. Older snapshots in the gap are skipped when confirmed is already newer. Newer snapshots apply. Attempts from the other devices are inserted. The cursor moves to the end of that page only when the page transaction commits. Until the cursor is caught up, the indicator stays Pending even though this device's own upload was acknowledged.

Caught up means the last successful poll returned `has_more` false and the committed cursor equals that response's `next_cursor`. Until then the UI stays Pending even if individual HTTP calls returned 200. A full restore is that same loop from cursor 0. It is subject to the same rate limits as a normal poll. Restore does not bypass quotas.

Vocabulary pull stays on its own cursor and its own route. A progress page must not be applied as a vocabulary revision.

## Event-first merge (locked for this proposal)

**Fold in server accept order. Anchor SRS `due_at` to server `received_at`. Use `ladder-v2` only.**

- The device creates `event_id` once, in the same local transaction as the outbox row, and reuses it on every retry.
- The server applies events in `change_id` / `server_seq` order. `occurred_at` is stored and can be shown. It does not reorder the fold and it does not set `due_at`.
- For a mastered answer, `due_at` is `received_at` plus the ladder interval `1, 3, 7, 14, 30` days for the streak after that event. For any other answer, `interval_days` is 0 and `due_at` is `received_at`. A device clock set in the future or the past cannot move the schedule by itself.
- Counters come from distinct accepted `event_id`s. Replaying one id does not increment `seen` twice.
- Two offline devices may each create an event for the same `vocab_id`. Both count. The later one to be **accepted** updates streak and `due_at`.
- Local `progress.json` files are never added together.
- A mismatch on a reused `event_id` is a conflict. The stored event remains. Nothing is deleted to make the new body fit.
- An unknown or newer `algorithm_id` than `ladder-v2` is rejected. The server does not grade it with a guessed ladder. A future ladder needs a new accepted decision and a new id.
- Historical events are not reinterpreted when the ladder changes. An explicit rebuild would be a separate migration that writes a new `state_version` and does not delete the events.

### Locked trade-off

A wrong answer that was made earlier on a device, but uploaded after another device's correct answer has already been accepted, is applied **last** and resets the streak. `due_at` then becomes that late event's `received_at`. This is accepted. Ordering or scheduling from `occurred_at` is rejected, because a skewed or edited clock could rewrite SRS.

### How the UI reconciles

The study screen shows provisional while this device still has local attempts for that word that are not covered by confirmed. Otherwise it shows confirmed. Provisional uses `ladder-v2` and the device clock only as a stand-in for those uncovered attempts. It is Pending, not the account's confirmed schedule.

When a newer confirmed snapshot commits, provisional is rebuilt from that snapshot plus only the still-uncovered local attempts. A late wrong answer that resets the server streak replaces the confirmed streak. Pending local attempts stay in the outbox and remain on top of the new confirmed row. The screen does not keep a provisional streak that ignored the snapshot, and it does not drop the pending attempts. `occurred_at` may still be shown as the device's claimed time. The schedule the learner reviews against is the projection on screen; the confirmed `due_at` is the server schedule.

A long offline batch uploads in local outbox order, and the server folds it in accept order. After reconnect, each device applies the other device's snapshots with the version rules above. The indicator stays Pending until the outbox has no `pending` row and the download cursor is caught up. An acknowledged upload with an older cursor is still Pending.

## Legacy history (not implemented)

Machine-global `languages/{code}/attempts.jsonl` is **not rewritten**. Import does not open it for write, does not insert `event_id` into it, and does not delete lines.

New synced study does not append that file. Guest study may still append it, as the app does today. Those writes are outside the account database.

Moving old lines into an account requires an explicit consent record stored in that account's local database. Login does not create that record. Consent names the account. A second account on the same PC does not inherit it and does not receive the imported events unless that account consents separately.

Identical JSONL lines at different offsets are different attempts. The ledger primary key is not the line hash.

`legacy_import_source` binds one machine path to one OS file identity:

| Column | Rule |
|---|---|
| `language_code` plus the canonical `attempts.jsonl` path | The only file a pass may read for that language. |
| `file_identity` | Windows volume serial and file index, read when the pass opens the file. Stable across appends. A replaced file has a new identity. |
| `high_water` | Byte offset just after the last complete line committed for this identity. |

If the file identity cannot be read, the pass imports nothing and the UI shows Conflict / Action required. It does not fall back to a hash-only key.

`legacy_import_ledger` rows:

| Column | Rule |
|---|---|
| `file_identity`, `offset` | Primary key. `offset` is the byte offset where the line starts. |
| `line_sha256` | Hash of the raw line bytes, including its terminating newline. Verification only. Two identical lines at two offsets are two rows. |
| `disposition` | `imported`, `skipped_no_vocab_id`, `unreadable`, or `source_conflict`. |
| `event_id` | Set only for `imported`. Allocated once, in this row, and reused on every retry. |
| `created_at` | Local time the ledger row committed. |

One local transaction inserts the ledger row, sets `high_water` to the first byte after that line, and, for `imported`, inserts the account attempt plus its outbox row under that `event_id`. A crash before commit leaves no partial ledger row and does not move `high_water`.

The pass opens the file read-only and captures its size. It considers only newline-terminated lines that end at or before that size. Before reading new lines it checks that `file_identity` still matches the binding and, when `high_water` is greater than 0, that the byte before `high_water` is a newline and the line ending there still hashes to the ledger row for its offset. If the identity does not match, the pass imports nothing. If the hash at an existing offset does not match, one transaction marks that row `source_conflict`, leaves its `event_id` in place, does not move `high_water`, and stops. No second event is created.

- Concurrent append past the captured size is left for a later pass. Earlier offsets are not read again as new attempts.
- A final line with no newline inside the captured size is not imported and gets no ledger row. The next pass can import it after a newline is present. It is not marked `unreadable`.
- A complete line that is not JSON is `unreadable`. It stays in the file.
- A line with no valid `vocab_id` is `skipped_no_vocab_id`. It stays in the file, is not uploaded, and is not matched by word text.
- The same `(file_identity, offset)` with the same hash is a no-op and reuses `event_id`.
- The same offset with a different hash is `source_conflict`. The pass does not allocate a second `event_id` and does not delete the event already imported from that offset.
- Truncation is the same file identity with a size below an offset already in the ledger. Imported events and ledger rows stay. The pass does not re-import the shortened prefix as new events. The UI shows Conflict / Action required. Nothing is removed to match the shorter file.
- Replacement is a new file identity at the same path. The old ledger and its events stay. The new file is not imported until this account consents again, and that consent names the new file identity. Consent does not by itself enqueue the new file. It is not a resume of the old identity.

### Replacement overlap

A replaced file may repeat attempts already imported from the old file. Before any outbox row is created for the new file identity, a preflight compares each complete line's `line_sha256` with every `line_sha256` already in this account's ledger, from any file identity.

- A line whose hash matches an existing ledger row is an overlap. It is not uploaded. The accepted event from the old identity stays.
- A line with no hash match is unambiguous. After the replacement consent, that line may be imported once under the new file identity and its own offset.
- Overlaps are reconciled explicitly. Skip records a ledger row at the new offset with disposition `skipped_overlap`, no `event_id`, and no upload. Import-as-distinct records a normal `imported` row and a new `event_id` only after that explicit choice. The default is skip. A later pass does not treat an unreconciled overlap as permission to upload.
- Neither choice deletes an existing accepted event, and skip does not create a second one.

A later pass runs only while consent for this account and this file identity remains. Revoking consent stops further imports and does not delete events already in the account store. The source file is never opened for write.

Imported events are still only local until the server accepts them. Authoritative counters and SRS then come from the server fold of those events, not from a copy of `progress.json`. If that fold disagrees with the machine-global `progress.json`, the account store follows the fold after download. `progress.json` itself is left unchanged.

## Local durability (not implemented)

The authoritative local store for synced study is one SQLite database per account. It holds the account's attempts, the confirmed projection, the provisional projection, device-local daily activity, the outbox, the progress cursor, the vocabulary cursor, the consent record, and the import ledger.

That database is the only durability boundary for those rows. This design does **not** claim an atomic write across that database and `progress.json`, `attempts.jsonl`, or `vocab.json`. Those files stay the machine-global guest and legacy store. A failure to update them must not roll back a committed account transaction, and a failure of the account transaction must not be repaired by reading them.

### New answer, signed in

One transaction, before the UI treats the answer as saved for sync:

1. Allocate `event_id` once.
2. Insert the local attempt, including answer, expected answer, and prompt.
3. Rebuild the provisional projection for that `vocab_id` from confirmed plus this uncovered attempt. Do not change confirmed.
4. Insert the outbox row for that same `event_id` with state `pending`.
5. Update this account's device-local day bucket for the device calendar date.
6. Commit.

If the process dies before commit, the answer is not in the account store and must not be recovered from a JSONL line. If it dies after commit, startup uploads that `event_id` again. The outbox stays `pending` until a later transaction records the server's success for that id. A crash after the server commit but before that local ack leaves `pending`, and the retry is idempotent.

The worker does not delete an unacknowledged outbox row on shutdown, logout, or crash.

### Download cursor

The cursor update and the page's attempt and progress writes are the one transaction in Download and restore. Crash before that commit retries the same cursor. Crash after it does not apply those `change_id`s again.

### What is not inside the transaction

Signed-in study does not write `progress.json`. Guest study still uses that file, as the app does today. Those guest writes are outside the account database and are not how sync recovers.

## Daily activity

Signed-in daily activity is a table in that account's SQLite file, keyed by the device's local calendar date and language. It records which vocabulary ids were asked, correct, or wrong on this PC, and a local reading-done flag if the learner marks reading done while signed in. It is written in the same transaction as a signed-in answer. It is not uploaded, not part of `user_progress`, and not a server column.

Each account has its own file, so two accounts on one PC do not share a day bucket. Logout closes one file and opens the other. Login does not copy `progress.json` `days` into the account, and the attempt import does not copy them either.

Machine-global `progress.json` `days` is guest and legacy only. Guest study keeps writing it. Signed-in study does not.

Account-wide daily activity across devices is a separate projection. It is not designed here and must not be described as synchronized by ADR-022. Reading-done and listening results are not events in this proposal.

## Windows background sync engine (not implemented)

A future component runs beside Tkinter, not inside widget callbacks.

- The per-account database described under Local durability holds the outbox and both cursors.
- The worker starts on login, on a local mutation, on reconnect, on application resume, and on a timer. The initial polling candidate is 60 seconds, configurable, and must slow down when the server reports a rate limit. A full restore uses the same limit.
- Connection failure uses exponential backoff with jitter. Offline study does not wait for the worker.
- The worker does not call Tkinter. The UI reads a snapshot posted to the main thread.
- Shutdown finishes the current local commit, leaves the outbox and cursors on disk, and stops the worker. Resume opens the same account database.
- Logout, account switch, or an invalid session stops the worker and closes that account database. The next cycle does not open another account's file.
- Existing machine-global progress and attempts are not uploaded because someone logged in. Attempts move only through the consent import above, including the replacement overlap preflight.
- Vocabulary push and pull keep `expected_revision`, tombstones, and `operation_id` behavior. Progress sync does not overwrite a vocabulary entity.

### Account vocabulary isolation (future client, not implemented)

Today `vocab.json` is machine-global under `languages/{code}/`. The future signed-in client stores that account's working vocabulary in the per-account database, not in that shared file.

- Login does not copy machine-global `vocab.json` into the account store and does not push it.
- Account A's vocabulary is not listed in account B and is not uploaded with B's session.
- Guest study keeps using machine-global `vocab.json`. Signing in does not publish those guest entries.
- Moving guest vocabulary into an account requires an explicit consent flow of its own. This ADR does not define that flow and does not make it automatic.

## Synchronization UX

The indicator describes confirmed local state:

| State | Meaning |
|---|---|
| Synced | The vocabulary outbox and the progress outbox have no `pending` row. The vocabulary download cursor and the progress download cursor are both caught up: the last poll for each returned `has_more` false and its `next_cursor` equals the cursor committed for that stream. No blocking conflict is unresolved. HTTP 200 on one stream is not Synced. |
| Pending | An outbox row is `pending`, a download page is not committed, or the cursor is behind the server. An acknowledged upload with an older cursor stays Pending. Includes a provisional SRS projection for attempts not yet covered by confirmed. |
| Offline | The worker cannot reach the server. Local study continues. The account database still commits new events. |
| Conflict / Action required | A reused `event_id` did not match, an equal `state_version` carried different snapshot content, a page failed validation, a legacy source was truncated or replaced, a replacement overlap is waiting for reconciliation, or a vocabulary revision conflicted. Any one of these blocks Synced. Stored attempts and the newer confirmed snapshot stay. The learner can open the item. An over-long answer is this state for that event, not an endless retry. Ordinary sync does not ask for a click. |

## Security and operational gates

ADR-022 does not pass the Phase 18B.3 gates and does not replace them. Before any production progress sync:

- Restore verification and backup alerting from the accepted backup and alert contracts.
- Encrypted off-box recovery and a successful restore drill.
- Public API rate limits, per-account storage and history quotas, and disk-exhaustion protection, implemented and verified, not merely designed. Answer text is part of that storage quota.
- Logs and alerts stay free of tokens, passwords, API keys, answer text, prompts, and vocabulary content.
- Staging stays on localhost with no production credentials, databases, backups, or public routing.
- Production activation stays a separate authorization. The sync flag remains off. No timer is installed by this ADR. No Windows client is authorized.

## Acceptance scenarios (future tests)

Not implemented. Required when a later milestone builds this:

- Two online devices on one account both show a new answer, including `user_answer`, `expected_answer`, and `prompt`, without a restart.
- A new device from cursor 0 receives every accepted attempt and ends with each vocab's snapshot equal to the server's latest `state_version`.
- Answers made offline appear on the server after reconnect, once each.
- Repeating the same `event_id` and body does not change `seen` or add a second journal row. A different body conflicts and changes nothing.
- Two different ids for one `vocab_id` both count, and the later accepted id determines streak and `due_at`.
- A wrong answer uploaded after another device's mastered answer resets the streak, and both devices show that snapshot after they apply it.
- An `occurred_at` years away from `received_at` does not set `due_at`.
- A long offline batch from two devices converges to one accept order, not to either device's clock order.
- After logout or an account switch, the next session cannot read the previous account's outbox, ledger, or cursor.
- A crash after the local answer transaction still has the event and one pending outbox row. A crash before that commit has neither, and JSONL is not used to invent one.
- A crash after the server accept but before the local ack retries the same `event_id` without a second counter increment.
- A crash during page apply, before commit, leaves the cursor unchanged. A crash after commit does not apply that page again.
- A page whose snapshot version is lower than confirmed still stores a new attempt, does not regress confirmed, and advances the cursor when the rest of the page validates.
- An equal `state_version` with different counters, streak, interval, `due_at`, or `last_event_id` writes nothing and does not advance the cursor.
- A pending outbox row is still present after a page commits, and provisional is that confirmed snapshot plus the pending attempt, not the snapshot alone and not the old provisional streak.
- An upload success updates confirmed and leaves the download cursor unchanged. A later page inserts the gap's attempts, does not insert the acknowledged event again, and does not replace confirmed with an older snapshot.
- With the server unreachable, a signed-in learner can still commit a new event to the account database.
- Import does not modify `attempts.jsonl`. Two identical lines at different offsets become two events. A second pass at the same offset and hash does not allocate another `event_id`.
- A line with no `vocab_id` stays in the file and is not uploaded. An append past the captured size is not imported in that pass. A partial last line gets no ledger row until it has a newline.
- Truncation keeps the imported event. A hash change at an existing offset does not create a second event and does not delete the first.
- A new file identity at the same path does not import until a new consent, and it does not delete the previous identity's events.
- Replacement consent alone does not upload a line whose hash matches an already imported line. Preflight runs before any outbox insert. Skip writes `skipped_overlap` and leaves the original event. Import-as-distinct creates one new event only after that explicit choice and still does not delete the original. A replacement line with no hash match imports once.
- Synced is false when the vocabulary outbox is pending, when the vocabulary cursor is behind, or when a blocking conflict is open, even if progress is caught up. It is also false when only progress is behind.
- Signed-in vocabulary for one account is not shown or uploaded for another account. Login does not push machine-global `vocab.json`.
- A signed-in answer's day bucket is in that account database and is absent from the other account's database and from `progress.json`. A guest answer still updates only `progress.json` `days`.
- Logs for a failed upload do not contain answer text, prompt text, or tokens.

## Proposed milestones

These are not authorized. Phase 18B.5 through 18B.11 in the production-readiness plan stay in that order and are not skipped.

| Milestone | Scope |
|---|---|
| 18B.5 | Repo-only restore verification. Next possible ops milestone. Not started here. |
| 18C.1 | Schema v3 tables and migration tests in the repo. Flag stays off. No VPS. |
| 18C.2 | Progress ingest and change-page API in the repo, Bearer-only, behind the same default-off flag. |
| 18C.3 | Windows per-account database, outbox, and worker in the repo, local tests only. |
| Later activation | Only after the Phase 18B.3 gates, including 18B.11, plus a separate authorization for progress sync. |

AI Local Reading/Listening remains the next major product priority after the sync sequence. It is not pulled into 18C.

## Open decisions for Leader

1. The numeric rate limit, per-account attempt quota, storage quota, and any UI threshold for displaying a skewed `occurred_at`. Scheduling ignores the device clock either way. The threshold would only affect what the UI may call out. Phase 18B.10 still has to implement and verify the limits before activation.
2. Whether reading-done and listening results ever become events. They are out of this proposal.

## Do not

- Do not create these tables, routes, or the Windows worker from this ADR.
- Do not set `STUDY_SYNC_ENABLED`.
- Do not upload machine-global guest data on login.
- Do not enqueue a replacement line that matches existing provenance unless reconciliation explicitly marks it a distinct attempt.
- Do not show or upload one account's vocabulary as another account's, and do not auto-upload machine-global guest vocabulary.
- Do not rewrite `attempts.jsonl` to add `event_id`.
- Do not use the line hash alone as the import identity.
- Do not sum `progress.json` files or treat daily activity as account-wide sync.
- Do not write signed-in day buckets into `progress.json`, or share them between accounts.
- Do not abort a download page only because a snapshot is older than confirmed or provisional.
- Do not claim one atomic commit across the account database and the JSON/JSONL files.
- Do not treat a client `user_id` or `device_id` as account identity.
- Do not log answer text, prompts, vocabulary content, tokens, or secrets.
- Do not change vocabulary tombstone or revision rules to store progress.
- Do not start Phase 18B.5 or 18C from this document.
