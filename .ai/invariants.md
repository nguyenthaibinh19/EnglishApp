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

## Adaptive vocabulary preview

- Phase 19.4A is merged source and is not in the installed v1.5.0 download. The production study button and locked sessions stay on the legacy quiz.
- Introduction, multiple choice, and assisted practice do not write an attempt or SRS progress. Only a submitted independent recall uses the existing attempt path.
- An incomplete missing-letter answer is not a failed exercise and does not move the session ladder. A completed assisted answer still does not write SRS.

## Sentence practice (19.5A closed)

- Sentence submissions must never create vocabulary `LearningAttempt` rows, call `Progress.record`, change SRS, clear Mistake Book attention, write PracticeRecord v1, or enqueue vocabulary progress outbox events.
- Reviewed `accepted_answers` are curated content. Outcomes distinguish reviewed correct, definite incorrect, incomplete, unlisted, provisional accept/correct, unavailable, and ungraded.
- Incomplete word-bank input is not a failed exercise. Unlisted open-writing / guided alternatives are not definitive wrong unless a template violation is evidenced.
- Claim conjugation/article/word-order only with sufficient evidence; otherwise use neutral guidance.
- Unavailable AI is not a learner failure. Fake/simulated grading must be labeled as development-only — not a live AI call.
- AI grades are provisional and must not become answer keys or validated grammar rules. Malformed GradeResult fields yield ungraded — not wrong.
- Progress counts distinct achieved levels, not raw correct tallies. Abandon and missing content are not successful completion.
- App exit, account switch, language change, and return to Home must close sentence windows and invalidate deferred Reading/Listening transitions.
- Activation matches Adaptive Study opt-in (`LG_ADAPTIVE_STUDY=1` + isolated `LG_DATA_DIR`). Not on the installed Study button. Not under locked ScreenGuard sessions. Not in frozen installs as a production path.
- Only Dutch A1 ships a curated pack in 19.5A; do not claim complete multilingual grammar coverage or expert linguistic validation.

## Adaptive Study integration (19.4C)

- Adaptive Study requires `LG_ADAPTIVE_STUDY=1` and a validated isolated `LG_DATA_DIR`. Source alone is not enough. Locked ScreenGuard sessions and frozen installs keep `VocabQuizApp`.
- Do not reinterpret a locked required Study child as unlocked merely to open Adaptive Vocabulary.
- Due/new eligible unique vocab ids must equal `planned_vocab_count`. Do not silently shrink the target or pad with future reviews / invalid ids.
- Unique independent successes satisfy that N; recognition/assisted do not. Independent success without an authoritative write must not complete the session.
- Vocabulary completion must not auto-complete Reading or Listening.
- Adaptive windows bind account generation, language, and data root. Late callbacks must not write a previous account's store. Same-language repeats lift; language changes close the bound window.
- Practice `unavailable` must not be reported as saved.

## Practice records

- Recognition and assisted vocabulary events belong in `practice_records.db`. They do not belong in `account_study.db` or AttemptHistory.
- A practice row must not call `Progress.record`, change SRS, clear Mistake Book attention, or enqueue a Cloud Sync progress event.
- Independent recall remains the only vocabulary path that appends a `LearningAttempt`.
- Guest practice is not imported into an account. An exact unaided attempt still outranks assisted practice for the next start, and assisted success does not make a non-mastered word mastered.
- Practice that is older than, or equal to, the latest independent attempt cannot override that attempt's starting-level evidence.
- Observable error classes stay conservative: `near_match` and `incorrect_answer`. Do not invent unsupported linguistic diagnoses.
- The practice store refuses production AppData, protected RC data, and recovery directories for every runtime identity.
- Integrated development sessions open the account/guest practice file for the captured identity. They must not use the standalone 19.4B preview database as the live app store.

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

- Listening stays optional. The settings default remains off. A local Windows provider exists in source after Phase 19.3 and is not part of the installed v1.5.0 download.
- Missing or failed audio leaves Listening unavailable and must not permanently block lock-session completion after required vocabulary work.
- A voice from another language is refused. There is no cloud speech fallback. Saved voice tokens stay on the device and are not synced.
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

Current production, 2026-11-24: `STUDY_SYNC_ENABLED` is exactly `1`, the seven Sync routes are deployed, and `language-guard-sync-backup.timer` is enabled. Sentences below that say the flag is unset or the timer is disabled record the phase in which they were written. Do not turn the flag off or disable the timer to match those older sentences. The live record is [PHASE-18D.2B-production-backend-sync-backup.md](plans/PHASE-18D.2B-production-backend-sync-backup.md).

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
- Phase 18B.1 itself did not perform production deployment, enable production sync, or add a desktop sync client. Accepted HTTP commit: `599e473`. The later Phase 18B.7 dark deploy copied that server source with Sync OFF. At that deploy `STUDY_SYNC_ENABLED` was unset and Sync was not activated. The 2026-11-27 checkpoint is the later statement.
- Sync backup uses SQLite's online backup API, publishes only after `integrity_check`, and never creates a missing `study_sync.db` or deletes the source. Retention touches only the `study-sync-` prefix. Restore refuses an existing destination. Phase 18B.4 timer templates exist in the repository and at `/opt/language-guard/deploy/hetzner/`. Phase 18B.8 installed them into `/etc/systemd/system` and left `language-guard-sync-backup.timer` disabled and inactive. It has not been started. Accepted backup-timer commit: `d277791`. A missing source emits no alert. Backup failure and the retention warning emit safe status events. No production alert destination is configured. Disappearance detection and RPO freshness are not operational. On-VPS retention is not sufficient for activation. Abuse-resistance controls must be implemented and verified effective before the flag is set. Accepted backup commit: `5f4251a`. Accepted planning commit: `97f7b25`.
- Phase 18B.5 restore verification is closed and GitHub-verified at `69307892f779e61de7b99563eb5c76ad4296cbcc`. Phase 18B.7 copied that source to the VPS. Phase 18B.8 enabled the production verifier. A recorded `SKIPPED` result is not a successful restore. It restores the newest validly named `study-sync-*.db` into a new directory, opens that copy read-only, and does not migrate it. `PRAGMA integrity_check` must be `ok` and the schema version must be 2. It must not restore onto the live database, `accounts.db`, the backup file, or `/opt/language-guard`. A missing backup creates no database. An absent live path is a skip and is not proof the database never existed. A live directory, symlink, or other non-file is a failure. The verification root is resolved, including ancestor symlinks, before any directory is created or its mode is changed. Names must be real ASCII timestamps `study-sync-YYYYMMDD-HHMMSS-ffffff.db`. A failed newest backup is not replaced by an older file. Cleanup removes only that run directory.
- Phase 18B.6 local staging is closed at `39f3a0bbbc47dda2c213324a820d198d0f0c3501` and is not a VPS deployment. The staging process uses a copied package so `accounts.db` stays beside that copy, and `STUDY_SYNC_DIR` points only at the staging sync file. The pre-start guard runs before databases are created. When a staging `.env` exists, its fields must be the staging allowlist; the server does not listen until that file exists and matches, while the pre-materialization guard may run before the file exists. Proof files are created only as new names inside the staging proof directory, never by replacing another file. Staging binds only `127.0.0.1`, never port `8765`, and never uses a real provider key. `language-guard-staging.service` is a repository template and is not installed. On Windows, symlink tests skipped because `os.symlink` is unavailable, including the POSIX proof-partial regression. Passing local tests does not authorize a staging host.
- Phase 18B.7 controlled dark deploy is closed. Production runs server source `d0f2f004c85ce9f4265d33bd034ba18423f1e3a5`. Twelve approved files matched their SHA-256 checksums, and `language-guard.service` was restarted. At the 18B.7 deploy `STUDY_SYNC_ENABLED` was unset. While it is unset, the three sync routes stay 404 and must not create `study_sync.db`; that file remained absent after the deploy. The accounts backup timer is unchanged by that deploy. No sync timer was installed in the 18B.7 deploy. The seven Linux symlink and `systemd-analyze` tests are deferred and are not passes. Phase 18B.8 health monitoring is CLOSED — Leader Accepted, 2026-11-10. The collector must not create `study_sync.db`, must not read the live accounts database, and must not treat a skipped sync backup or provider acceptance as success or delivery. The sync-backup timer is installed, disabled, and inactive. The sync-verify timer is enabled and operational. Its `ReadOnlyPaths` line prefixes the absent `/opt/language-guard/app` and `/var/backups/language-guard/study-sync` paths with `-`. The natural run at `2026-11-10 07:00:00 UTC` recorded `SKIPPED` at `2026-11-10T07:00:01Z`. The natural 09:00 report finished at `2026-11-10 08:00:07 UTC`. Commit `09556f9` is deployed: new accounts snapshots are mode `0600`, and the 2026-11-10 snapshot `accounts-20261110-032712.db` is mode `0600`. No verifier traverse grant was added.
- Phase 18B.9 off-box backup is not activated. Google Drive stays **NOT CONFIGURED** until a reviewed production job is active. A fake, localhost, or missing `transport` value cannot satisfy a production retention, recovery, monitoring, or freshness gate. HTTP success alone is not `VERIFIED`. `VERIFIED` requires the SHA-256 of the downloaded ciphertext. A restore drill does not create that state. `SKIPPED` remains not a successful restore. The VPS `lg-backup` user, uid 994 gid 977, is not a WSL lab user. `app/offbox_poc.py` is not the uploader. Phase 18B.9C2 is not authorized, and step 18B.9D5A2C1 is not that phase. No off-box step may delete a snapshot, a lab file, or a Drive object. The map is [PHASE-18B.9-offbox-status.md](plans/PHASE-18B.9-offbox-status.md) and [ADR-024](decisions/ADR-024-offbox-age-drive.md).
- Answer matching uses the study language passed by the caller, then a legacy `nl` or `en` entry key when no language was passed. Explicit `articles` and `elisions` still override that choice. Settings `language` must not replace the language of another quiz. A near match or a hint is not SRS mastery. Recording a new attempt appends a row and does not rewrite older attempt lines. The Article-Matching Hotfix that encodes this is CLOSED and GitHub-verified at `d0f2f004c85ce9f4265d33bd034ba18423f1e3a5`. Canonical `word` entries remain supported. Windows RC QA at that commit: full pytest 487 passed, 7 skipped; smoke all checks passed. Those seven skips are Linux symlink tests and `systemd-analyze`; they are not passes. Windows RC QA at that commit was paused and unpublished. A local executable is not a release, and a Windows pytest pass does not prove Linux runtime safety.
- An oversized sync body is rejected with 413 from `Content-Length` before the database opens. On 2026-10-30 one Windows client then raised WinError 10053. On 2026-11-02 the same test passed in the full suite and in five immediate reruns. That abort is follow-up QA. It is not a reason to change the production HTTP handler.
- ADR-022 is accepted. As of the 18C.3A audit (`dc6dc8a`), Phase 18C.1/18C.2 have implemented the per-account SQLite store, outbox, worker, and progress HTTP in source. The 18C.3A audit recorded production `STUDY_SYNC_ENABLED` off. The 2026-11-24 checkpoint later recorded the controlled pilot on, and that observation was not rechecked on 2026-11-27. The guest AttemptHistory ledger is **18C.3B CLOSED — Architect Accepted** (PR #28, merge `610d979434f8ff10274e8000916563e1e2f57126`). See [PHASE-18C.3B-guest-attempt-ledger.md](plans/PHASE-18C.3B-guest-attempt-ledger.md). Imported `occurred_at` stays evidence. Provisional scheduling for those rows follows outbox order and the enqueue clock. A line that fails the server progress-event rules is not enqueued. A reparse point on the attempt path or an ancestor is refused. It is on `main` and does not enable Cloud Sync. It does not enable `STUDY_SYNC_ENABLED`, add a second desktop client, or treat a client-supplied `user_id` as account identity. The rules below bind the current source and any later milestone. Progress counters must not be merged by adding `progress.json` files together. SRS fold order is server accept order, and `due_at` uses server `received_at` with `ladder-v2`, so a late wrong answer may reset streak and a skewed device clock must not set the schedule. Confirmed and provisional projections stay separate. A download page persists each new attempt once, applies a newer confirmed snapshot, skips an older snapshot without regressing confirmed, and conflicts when an equal `state_version` has different content. Pending local attempts are not dropped. The progress cursor advances only in the commit that applies the whole validated page. An upload acknowledgement must not advance that cursor past changes not yet downloaded. Attempt payloads may contain bounded answer text and must stay account-isolated; logs must not contain that text, prompts, vocabulary content, tokens, or secrets. Machine-global `attempts.jsonl` must not be rewritten in place to add event ids. Import identity is file identity plus byte offset; the line hash is verification only, so identical lines at different offsets stay distinct. Truncation or file replacement must not delete events already imported. A replacement file requires an overlap preflight, and new consent alone must not upload a line whose hash already exists in the ledger. Unreconciled overlaps do not upload. An explicit distinct-attempt choice is the only path to a second event, and it must not delete the original. Guest or other-account files must not upload without explicit consent for that account. The per-account sync database is not an atomic transaction with `progress.json` or `attempts.jsonl`. Signed-in daily activity is stored in that account database and must not be written into another account or into `progress.json`. `progress.json` `days` is guest/legacy only. Account-wide daily analytics are not part of this design. Synced requires a clear vocabulary outbox, a clear progress outbox, both download cursors caught up, and no unresolved blocking conflict. Future signed-in vocabulary is isolated by account. Machine-global guest vocabulary must not automatically appear in or upload to an account.

## Windows installation and Startup

- A frozen executable that is not the installed path must not overwrite `%LOCALAPPDATA%\langstudyguard\langstudyguard.exe` when that file exists, must not start it, and must not create or change Startup ([ADR-023](decisions/ADR-023-windows-installation-safety.md)).
- Launching the installed executable must not copy itself and must not create or rewrite the Startup shortcut.
- Startup registration must not delete or replace an existing `langstudyguard.lnk`, `Dutch Guard.lnk`, or unrelated shortcut.
- A failed first install may remove only the executable and Startup link created by that attempt.
- A successful process spawn is not proof the application finished initializing.
- The hash, Startup state, and remaining `--lock` / Emergency Exit gaps are in [current_state.md](current_state.md). Do not treat a configured shortcut as a tested lock session.

## Test isolation

- Tests must not modify real user AppData.
- Sync store tests must use `tmp_path` only — never write production `accounts.db` or live AppData.
- Tests must not contact production services (OpenAI, VPS, live dictionaries) unless an explicit, isolated fixture says otherwise — prefer fakes / `tmp_path`.

## Language architecture

- Study language and UI/native language are **distinct**.
- Core architecture must not assume Dutch except explicit backward-compatibility / default behavior.
