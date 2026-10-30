# Invariants

Rules that must not be broken casually. Tests encode many of these; this file states them for agents and humans.

## Stable vocabulary identity

```text
vocab_id is immutable.
```

- Editing `word` / `meaning` / alternatives must **never** regenerate the ID.
- Rename must preserve Progress, SRS, Attempts, Mistake Book linkage, and Word Detail history.
- See [ADR-009](decisions/ADR-009-stable-vocabulary-identity.md).

## Vocabulary lexical schema

Canonical **local** fields:

```text
meaning
alternatives
part_of_speech   (optional)
examples         (optional; structured)
pronunciation    (optional; ipa only for now)
forms            (optional; small controlled set)
```

Not as primary persisted names:

```text
vi
alt
type
example   (legacy string — migrate to examples[])
```

Legacy fields may remain supported for **reading/migration** only. New writes use canonical fields. Enrichment fields do not affect answer matching. See [ADR-010](decisions/ADR-010-vocabulary-model-v2.md), [ADR-011](decisions/ADR-011-vocabulary-enrichment-model.md).

## Enrichment never silently overwrites

```text
External enrichment must NEVER silently overwrite canonical vocabulary data.
```

- Suggestions arrive as ephemeral `EnrichmentDraft`.
- Learners review and explicitly apply selected fields.
- Missing draft fields must not clear existing canonical values.
- See [ADR-012](decisions/ADR-012-enrichment-review-before-apply.md).

## Progress / SRS

- Progress state follows vocabulary ID (progress.json v3).
- SRS **future** items must not be reported as **due** in Daily Study / Home.
- Legacy missing `due_at` remains due (current Phase 8 behavior).
- Long-term due ≠ within-session requeue.

## Mastery semantics

Current mastery-compatible success (`LearningAttempt.correct` / Progress `correct` increments):

```text
verdict == exact
AND
hint_used == False
```

Near answers and hint-assisted exact answers are **non-mastered**. Do not casually redefine `LearningAttempt.correct`.

## Mistake Book

- Latest **mastered** attempt → item does **not** currently need attention.
- Latest **non-mastered** attempt → item needs attention.
- Not a permanent dump of every historical error.

## AI security

- Production AI credentials stay server-side.
- Never embed the server OpenAI API key into the frozen desktop executable, settings, logs, or test fixtures.
- AI vocabulary enrichment is advisory only (draft → review → Apply); see [ADR-013](decisions/ADR-013-ai-vocabulary-enrichment.md).

## Reading optionality

- Reading remains optional when enabled in settings.
- Reading / AI / network failure must not permanently block lock-session completion after **required** vocabulary work is complete.

## Listening optionality / audio safety

- Listening is optional when enabled; settings default **disabled** until a production audio provider exists.
- Missing / failed audio provider → Listening **unavailable**; must not permanently block lock-session completion after required vocabulary work.
- Listening answer feedback must not redefine vocabulary mastery / SRS. See [ADR-015](decisions/ADR-015-listening-activity.md).

## StudySession vs ScreenGuard

- StudySession decides **logical** completion.
- ScreenGuard / Tkinter owns **lock enforcement**.
- Do not move lock/security behavior into the session-domain model.
- Activity Toplevel construction failures must not leave orphan blank windows or a withdrawn/unusable parent root.
- Optional activity Tk adapters must not equate “unresolved” with “required”.
- Returning to non-lock Home must restore a normal (non-zoomed) window state.
- Internal child navigation must not change the parent window's visible fullscreen/normal state merely to display an owned popup. Use `ScreenGuard.pause_enforcement` / `enforcement_paused`; reserve `release_display` for rare external dialogs.

## Persistence safety

- Schema migration must preserve existing user learning data.
- Destructive migration is unacceptable without an explicit migration design.
- When rewriting user persistence: prefer atomic temp-write + flush/fsync + `os.replace`.
- Migrations must be **idempotent**.

## Account Cloud Sync (foundation)

- Sync persistence (when present) lives in **`study_sync.db`**, not production `accounts.db` ([ADR-018](decisions/ADR-018-account-cloud-sync.md)).
- Vocabulary sync identity is the immutable `vocab_id`; never regenerate IDs on sync write.
- Stale entity `expected_revision` must **conflict without mutation** (no silent overwrite).
- Deleted entities are tombstones; must not be silently resurrected.
- Replay of the same `operation_id` is idempotent only when entity key, delete intent, canonical payload, **and** the operation’s `expected_revision` all match; any mismatch is a conflict.
- Sync payloads must use an explicit allowlist (canonical + supported legacy aliases + valid enrichment). Unsupported fields must be **rejected**, never silently dropped while acknowledging success.
- Sensitive keys (tokens / API keys / passwords) must be rejected recursively, including nested objects and `examples[]` items.
- Numeric sync arguments (`user_id`, revisions, cursors, limits) must be real integers — not bool or float.
- Phase 18A does **not** activate production sync or automatic desktop upload. Accepted store commit: `94f1bf7`.
- Phase 18B.1 HTTP sync is **off** unless `STUDY_SYNC_ENABLED` is exactly `1`. While off, sync routes must not open or create `study_sync.db`.
- Sync HTTP takes `user_id` only from `account_store.user_for_token()` on `Authorization: Bearer`, the same call existing login/AI routes use. Body `token` and JSON `user_id` are not authority. There is no separate account-directory override.
- The Hetzner account-server file list includes the sync import closure. Importing that package with `STUDY_SYNC_ENABLED` unset must not create `study_sync.db`.
- Sync HTTP errors stay non-sensitive: no stack traces, SQLite paths, passwords, tokens, or provider secrets. Page size is at most 500 changes.
- Phase 18B.1 does **not** deploy, enable production sync, or add a desktop sync client. Accepted HTTP commit: `599e473`.
- Sync backup uses SQLite's online backup API, publishes only after `integrity_check`, and never creates a missing `study_sync.db` or deletes the source. Retention touches only the `study-sync-` prefix. Restore refuses an existing destination. Phase 18B.4 timer units exist in the repository and are not installed or enabled. Accepted backup-timer commit: `d277791`. A missing source emits no alert. Backup failure and the retention warning emit safe status events. No production alert destination is configured. Disappearance detection and RPO freshness are not operational. On-VPS retention is not sufficient for activation. Abuse-resistance controls must be implemented and verified effective before the flag is set. Accepted backup commit: `5f4251a`. Accepted planning commit: `97f7b25`.
- Phase 18B.5 restore verification is closed and GitHub-verified at `69307892f779e61de7b99563eb5c76ad4296cbcc`. It is repository-only and is not scheduled or installed. It restores the newest validly named `study-sync-*.db` into a new directory, opens that copy read-only, and does not migrate it. `PRAGMA integrity_check` must be `ok` and the schema version must be 2. It must not restore onto the live database, `accounts.db`, the backup file, or `/opt/language-guard`. A missing backup creates no database. An absent live path is a skip and is not proof the database never existed. A live directory, symlink, or other non-file is a failure. The verification root is resolved, including ancestor symlinks, before any directory is created or its mode is changed. Names must be real ASCII timestamps `study-sync-YYYYMMDD-HHMMSS-ffffff.db`. A failed newest backup is not replaced by an older file. Cleanup removes only that run directory.
- Phase 18B.6 local staging is Leader-approved source, pending GitHub commit verification, and is not a VPS deployment. The staging process uses a copied package so `accounts.db` stays beside that copy, and `STUDY_SYNC_DIR` points only at the staging sync file. The pre-start guard runs before databases are created. When a staging `.env` exists, its fields must be the staging allowlist; the server does not listen until that file exists and matches, while the pre-materialization guard may run before the file exists. Proof files are created only as new names inside the staging proof directory, never by replacing another file. Staging binds only `127.0.0.1`, never port `8765`, and never uses a real provider key. `language-guard-staging.service` is a repository template and is not installed. On Windows, symlink tests skipped because `os.symlink` is unavailable, including the POSIX proof-partial regression. Follow-up QA: `test_excessive_request_size_does_not_open_sync_db` once raised `ConnectionAbortedError` (WinError 10053) after a 413; a rerun passed and the full suite did not reproduce it. Passing local tests does not authorize a staging host. Phase 18B.7 is not authorized.
- ADR-022 is accepted as architecture only and is not implemented. It does not enable `STUDY_SYNC_ENABLED`, add a desktop client, or treat a client-supplied `user_id` as account identity. These rules apply when a later milestone implements it; they are not current code. Progress counters must not be merged by adding `progress.json` files together. SRS fold order is server accept order, and `due_at` uses server `received_at` with `ladder-v2`, so a late wrong answer may reset streak and a skewed device clock must not set the schedule. Confirmed and provisional projections stay separate. A download page persists each new attempt once, applies a newer confirmed snapshot, skips an older snapshot without regressing confirmed, and conflicts when an equal `state_version` has different content. Pending local attempts are not dropped. The progress cursor advances only in the commit that applies the whole validated page. An upload acknowledgement must not advance that cursor past changes not yet downloaded. Attempt payloads may contain bounded answer text and must stay account-isolated; logs must not contain that text, prompts, vocabulary content, tokens, or secrets. Machine-global `attempts.jsonl` must not be rewritten in place to add event ids. Import identity is file identity plus byte offset; the line hash is verification only, so identical lines at different offsets stay distinct. Truncation or file replacement must not delete events already imported. A replacement file requires an overlap preflight, and new consent alone must not upload a line whose hash already exists in the ledger. Unreconciled overlaps do not upload. An explicit distinct-attempt choice is the only path to a second event, and it must not delete the original. Guest or other-account files must not upload without explicit consent for that account. The per-account sync database is not an atomic transaction with `progress.json` or `attempts.jsonl`. Signed-in daily activity is stored in that account database and must not be written into another account or into `progress.json`. `progress.json` `days` is guest/legacy only. Account-wide daily analytics are not part of this design. Synced requires a clear vocabulary outbox, a clear progress outbox, both download cursors caught up, and no unresolved blocking conflict. Future signed-in vocabulary is isolated by account. Machine-global guest vocabulary must not automatically appear in or upload to an account.

## Test isolation

- Tests must not modify real user AppData.
- Sync store tests must use `tmp_path` only — never write production `accounts.db` or live AppData.
- Tests must not contact production services (OpenAI, VPS, live dictionaries) unless an explicit, isolated fixture says otherwise — prefer fakes / `tmp_path`.

## Language architecture

- Study language and UI/native language are **distinct**.
- Core architecture must not assume Dutch except explicit backward-compatibility / default behavior.
