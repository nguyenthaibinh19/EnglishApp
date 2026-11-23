# Phase 18B.10A — API abuse-resistance audit

Status: **Ready for Architect review** (`APP_18B10A_READY_FOR_ARCHITECT_REVIEW`)  
Baseline: `main` `d6578c0f579d7ee9bd02aec855193339a7d8c124`  
Date: 2026-11-23  
Cloud Sync: **OFF** · 18B.9: **PAUSED, NOT CLOSED** · Staging: **RESERVED** · Sync pilot: **NO-GO**

Repository inspection only. No application source change, no VPS action, no credential use, and no learner-data access. This audit does not authorize implementation, a dark deploy, or `STUDY_SYNC_ENABLED=1`.

The requirement source is [PHASE-18B.3-production-readiness.md](PHASE-18B.3-production-readiness.md) section “Public API abuse-resistance gate” and gate 10. ADR-022 already assigns numeric limits to Phase 18B.10 and forbids silent trimming of accepted attempts.

## 1. Baseline

| Check | Result |
|-------|--------|
| `git rev-parse HEAD` | `d6578c0f579d7ee9bd02aec855193339a7d8c124` |
| Branch | `main`, matching `origin/main` |
| Worktree | Untracked `diff/` only. No source edit in this audit. |
| 18C.3B | CLOSED — Architect Accepted. PR #28 merge `610d979434f8ff10274e8000916563e1e2f57126`. |
| Production flag | `sync_enabled()` is true only when `STUDY_SYNC_ENABLED` is exactly `1`. While unset, every path in `SYNC_PATHS` returns 404 and does not open `study_sync.db`. |

Inspected surfaces: `app/sync_http.py`, `app/sync_store.py`, `app/account_server.py`, `app/account_sync_client.py`, `app/account_sync_engine.py`, ADR-019, ADR-022, and the synthetic sync tests named below. No test suite was rerun. No source changed.

## 2. What the server already bounds

These are real controls. They are not the Phase 18B.10 per-account quota.

- One body ceiling, `SYNC_MAX_BODY = 32768`, applies before the body is read and before `study_sync.db` is opened. `tests/test_sync_api.py::test_excessive_request_size_does_not_open_sync_db` covers it on vocabulary put. The check sits in `handle_request` before route dispatch, so progress and preferences use the same ceiling.
- Vocabulary and progress page sizes are capped (`MAX_CHANGE_LIMIT = 500`, `PROGRESS_CHANGE_LIMIT = 100`). An out-of-range client `limit` is a validation error. No test asserts those ceilings by name.
- Progress text fields are rejected above 500 Unicode code points. The server does not truncate. `tests/test_legacy_attempt_ledger.py::test_server_incompatible_lines_never_enter_the_outbox` rejects a 501-character `user_answer` through the shared server validator and does not enqueue it.
- Vocabulary payloads use an allowlist and reject credential-shaped keys. There is no per-account count of entities or change rows. Word and meaning length are otherwise bounded only by the 32 KiB request.
- `user_id` in JSON is discarded. The session user owns the row.
- Accept, put, and delete each run in `BEGIN IMMEDIATE` and roll back on exception. `tests/test_sync_store.py::test_transaction_rollback_on_error` proves a forced SQLite abort keeps the previous vocabulary revision and does not reserve the failed `operation_id`.
- A duplicate `event_id` with the same body returns the original result and does not insert a second journal row. A different body conflicts and writes nothing. Those rules are tested in `tests/test_account_learning_sync.py`.
- Sync failures log `type(error).__name__` only. Public sync errors are fixed strings: `Invalid sync request.`, `Sync request is too large.`, `Sync store unavailable.`, `Authentication required.`, `Sync conflict.` The 409 body does include the current vocabulary record for the authenticated client. That body is the conflict contract, not a log line.
- `account_server.Handler.log_message` writes the client address, the request line, and the status. It does not write the Authorization header or the JSON body.

## 3. Gap matrix

| # | Requirement | Status | Evidence and gap |
|---|-------------|--------|------------------|
| 1 | Per-account rate limit on vocabulary and progress sync | **Missing** | `sync_http.handle_request` has no counter, bucket, `429`, or `Retry-After`. Bearer auth does not bound request rate. |
| 2 | Same limit on the rest of `SYNC_PATHS` | **Requires an architectural decision** | Preferences get/put sit behind the same flag and the same 32 KiB cap. Leaving them unlimited would bypass a limiter that covered only vocabulary and progress. Recommendation: one write bucket and one read bucket across all seven sync paths. |
| 3 | Per-account vocabulary storage quota | **Missing** | Entities and `vocabulary_changes` grow for as long as puts and edits are accepted. No count or byte check. |
| 4 | Per-account AttemptHistory quota | **Missing** | ADR-022 states the quota is a later 18B.10 gate. `accept_learning_attempt` inserts every new valid event. |
| 5 | Quota rejects a new row and keeps older rows | **Missing** | No rejection path exists. There is also no deletion of accepted attempts to free space. That no-trim behavior matches ADR-022 and must stay when the quota is added. |
| 6 | Idempotent replay does not consume a history slot | **Partial** | Replay and conflict already insert nothing. The quota interaction cannot be tested until a quota exists. A replay must remain success and must not count again. |
| 7 | Disk exhaustion fails the write cleanly | **Partial** | In-transaction abort rolls back and the HTTP adapter turns an unexpected exception into 500 `Sync store unavailable.` There is no `SQLITE_FULL` test, no check that `accounts.db` stays usable, and no check that a failed commit is not returned as 200. `connect()` can `os.makedirs` and create the SQLite file before the write transaction. |
| 8 | Safe HTTP monitoring | **Partial** | Failure logs and the access log avoid tokens and bodies. Nothing records a request-size metric. No test asserts that a failed sync log excludes a token, an answer, or a vocabulary word. The access log does include the client address. |
| 9 | ADR-022 event-first sync stays intact | **Implemented and tested** for accept order, idempotency, and conflict. **Missing** for rate-limit behavior. | The worker backs off on network failure and HTTP 500. HTTP 429 is `SyncClientError` and is not `Retry-After` handling. ADR-022 says the worker slows down when the server reports a rate limit, and a full restore uses that same limit. |
| 10 | Numeric limits | **Requires an architectural decision** | ADR-022 left the numbers open. Section 4 proposes values. They are not approved and are not in code. |
| 11 | Configuration that cannot be raised from the server environment | **Requires an architectural decision** | `SYNC_MAX_BODY` is a source constant. A future quota must not be increasable by `.env` or a systemd drop-in. An env disable switch would let a drop-in turn the control off while the flag looks unset. |
| 12 | Where the rate-limit counter lives | **Requires an architectural decision** | The account server is one `ThreadingHTTPServer` process. An in-process bucket matches that process and resets on restart. It would not be shared by a second process. |
| 13 | Synthetic tests and rollback design | **Partial** | Section 6 can be executed in temporary databases. Dark deploy and “controls are effective” on the running host are not done. |
| 14 | Production verification with the flag still unset | **Requires a production-only verification** | With `STUDY_SYNC_ENABLED` unset, production POSTs return 404 and never reach a limiter. Effectiveness against a live public request requires the flag, which this gate forbids. Section 7 states the only production check that stays valid before 18B.11. |

## 4. Proposed limits

These numbers are a recommendation for Architect approval. They are not implemented.

The honest client polls about once a minute and sends a handful of requests. A consented first upload of the preserved 114-word account is on the order of 114 vocabulary writes plus 114 attempt writes. A tight loop of 32 KiB bodies is the abuse case. Limits are per session `user_id`.

**Write bucket.** Vocabulary put, vocabulary delete, progress accept, preferences put.

- Capacity 40.
- Refill 10 requests per minute (600 per hour).
- A 228-write first import uses the burst, then finishes in about 19 minutes.
- Ordinary study is about one answer per minute and stays inside the refill.

**Read bucket.** Vocabulary changes, progress changes, preferences get.

- Capacity 30.
- Refill 30 requests per minute.
- The normal poll is about three reads per minute.
- A restore of 50,000 attempts at page size 100 is 500 reads, about 17 minutes. ADR-022 says restore does not get a higher limit. The separate bucket keeps that restore from spending the write budget.

**HTTP shape.** `429` and `Retry-After` set to the whole seconds until one token is available. Body: `{"error": "Sync request limit reached."}` No token, answer, vocabulary, path to SQLite, or remaining-quota count. Every request, including an idempotent retry, spends a rate-limit token. Quota accounting is separate and does not charge a replay.

**Vocabulary quota**, checked inside the existing write transaction after the idempotent `operation_id` match:

- 2,000 live entities per account. Deleted entities do not count. The preserved account has 114 Dutch words.
- 20,000 `vocabulary_changes` rows per account. A matching `operation_id` replay does not add a row.
- 32 MiB total stored vocabulary `payload_json` bytes per account, across the entity and the change journal. The 32 KiB request cap still bounds one write.

At the change-row cap, further puts and deletes are both rejected. A delete is itself a change row. The cap is about ten changes per live entity, which covers normal edits. Silent tombstone overflow is not part of this proposal.

**Attempt quota**, checked after the duplicate-`event_id` match and before insert:

- 50,000 accepted `learning_attempts` per account. About 50 answers a day for three years is roughly 55,000, so this is a few years of heavy study.
- 32 MiB total UTF-8 bytes of `word_snapshot`, `user_answer`, `expected_answer`, and `prompt` per account. Max-length fields hit this byte cap before the row cap. Short answers hit the row cap first.
- A duplicate `event_id` does not add a row or bytes. A validation failure or a conflict does not either.
- Older attempts stay. Nothing trims them.

**Quota HTTP shape.** `403` with `{"error": "Sync storage limit reached."}` `409` stays the revision and event-identity conflict. `500` stays an unexpected store failure. The client treats 403 as action required and stops retrying that item. It does not mark the account offline.

**Disk full.** On `sqlite3.OperationalError` whose SQLite code is `SQLITE_FULL`, or whose message is the SQLite disk-full text: roll back, return `500` `Sync store unavailable.`, and do not return the mutation. `accounts.db` is a different file and is not part of the sync transaction. No new status code.

**Monitoring line**, one per sync request, after the status is known:

`[sync] status=<code> bytes=<Content-Length>`

The path is a fixed route and may be included. The line must not include the Authorization value, the body, `user_id`, vocabulary, answers, prompts, or the database path. The existing access log may stay.

**Constants.** Ship the approved numbers as source constants, same pattern as `SYNC_MAX_BODY`. No environment variable raises them. No environment variable turns them off. Rollback is a code rollback, not a drop-in.

**Counter.** Keep the buckets in the one account-server process. Document that a restart clears them and that a second process would not share them. A SQLite counter is unnecessary unless the process model changes. Quota checks are `COUNT` and byte sums inside the write transaction, so a crash cannot desync a stored counter. No `SCHEMA_VERSION` bump.

## 5. Compatibility with ADR-022

The accept transaction stays: one immediate transaction, replay returns the original result, a mismatched replay writes nothing, a new event inserts the attempt, the progress fold, and one journal row, and success is after commit. Quota rejection happens before that insert and does not consume a slot. `occurred_at` stays evidence. `received_at` stays the schedule clock. Confirmed and provisional projections are untouched by this gate.

The worker change is limited to HTTP 429: wait at least `Retry-After`, and at least one poll interval, then retry. A 429 is not offline and not a conflict. A 403 storage limit is action required for that item. Pages, cursors, and outbox acknowledgements keep their current rules.

## 6. Incremental plan

Each slice needs its own Architect acceptance of the numbers in section 4. None of these slices sets the production flag, deploys, or opens Owner data. Tests use temporary databases and synthetic tokens.

**18B.10B — rate limit.** Add the two buckets and 429. Extend the client and worker to honor `Retry-After`. Tests: account A is limited while account B still succeeds; a replay spends a rate token and does not create a second event; oversized `Content-Length` still returns 413 without opening the database; the flag-off path still returns 404 without counting. Acceptance: 429 body is the fixed string, and stderr for that request contains no fixture token or fixture word.

**18B.10C — quotas.** Enforce the vocabulary and attempt caps inside the current transactions. Tests: the next new entity, change, or attempt past each cap is rejected; the previous row remains; a duplicate `event_id` and a duplicate `operation_id` still succeed; a conflict writes nothing; no attempt row disappears. Acceptance: HTTP 403 uses the fixed storage string and the client stops retrying that outbox item.

**18B.10D — disk full.** Force `SQLITE_FULL` from the sync transaction. Tests: response is 500, the seeded revision is unchanged, `PRAGMA integrity_check` is `ok`, and a temporary `accounts.db` still authenticates the synthetic user. Acceptance: the handler does not return 200 for the failed mutation.

**18B.10E — monitoring.** Add the single status line. Tests capture stderr for 401, 400, 413, 409, 429, 403, 500, and one successful put. Acceptance: the fixture token, answer, and vocabulary word are absent; status and byte count are present.

Dark deploy is not one of these slices.

## 7. Future dark deployment, configuration, and rollback

Not authorized here.

18B.3 requires a later Leader authorization to dark-deploy 18B.10 and then to show that the controls are effective, with `STUDY_SYNC_ENABLED` still unset. A production request cannot exercise the limiter while the flag is unset, because the route returns 404 first. Calling that a failed control would be the wrong conclusion. Calling a production 429 a required check would require turning the flag on, which is 18B.11.

Production-only check after a future authorized copy, and not before:

- Deployed sync files match the accepted revision.
- `.env`, systemd `Environment=`, drop-ins, and the process environment agree that `STUDY_SYNC_ENABLED` is unset.
- Sync POSTs on the public host return 404.
- `study_sync.db` stays absent unless it already existed. This audit does not create it.
- Owner RC data, the 114 Dutch words, the 114 pending outbox rows, and recovery backups stay untouched.

Effectiveness of the numbers is the synthetic suite in section 6, run against temporary databases. That suite is the repo acceptance. It is not a production activation.

Rollback of a future dark deploy:

1. Restore the previous server revision. Restart `language-guard.service`.
2. Confirm the effective flag is unset everywhere and sync POSTs return 404.
3. Leave any `study_sync.db` on disk. Do not delete it, vacuum it, or restore over it.
4. Leave the accounts backup timer on `backup_accounts.py`.
5. Do not add an environment switch that disables the limiter.

## 8. Out of scope

- Implementing the limits in this audit.
- Setting `STUDY_SYNC_ENABLED`, deploying, restarting the VPS, or publishing a Release.
- Resuming Phase 18B.9 or starting 18B.11.
- Opening, migrating, or reimporting Owner RC data.
- Changing login, AI, grade, reading, or listening routes. Their 80,000-byte body cap is a different surface.
- Choosing RPO, RTO, or the off-box store.

## 9. STOP

`APP_18B10A_READY_FOR_ARCHITECT_REVIEW`

Implementation waits for Architect approval of the section 4 numbers. Do not activate Cloud Sync. Do not start another milestone from this audit.
