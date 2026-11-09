# Roadmap

Directional plan — **not** a rigid release commitment. Update when phases complete or priorities shift.

## Completed

Architecture phases 1–14 (summary only):

| Phase | Theme |
|------:|--------|
| 1 | Scheduler separation from Progress |
| 2 | Canonical `StudyLanguage` registry |
| 3 | AI provider abstraction |
| 4 | pytest foundation (+ retained smoke test) |
| 5 | LearningAttempt history (JSONL) |
| 6 | Mistake Book (latest-attempt attention) |
| 7 | Practice Mistakes (`ReadOnlyVocabView`) |
| 8 | SRS v2 (`interval_days` / `due_at`) |
| 9 | DailyStudyPlanner |
| 10 | StudySession activity state machine |
| 11 | Home Dashboard (FreeHome) |
| 12 | Vocabulary Library + Word Detail |
| 13 | Stable vocabulary UUID identity |
| 14 | Vocabulary Model v2 (`meaning` / `alternatives` / …) |
| 14.5 | Project Memory Foundation (`.ai/`) |
| 15A | Vocabulary Enrichment Data Model (`examples` / IPA / forms storage) |
| 15B | Enrichment draft / review / apply foundation (no production providers) |
| 15C | Production AI vocabulary enrichment v1 (`/api/enrich`, review-before-apply) |
| 16 | Learning Progress Dashboard v1 (derived read-only analytics) |
| 17A | Listening Foundation (optional StudySession activity + audio-provider seam; no production TTS) |
| 17B | Windows Local TTS Provider v1 (System.Speech; per-language voice capability; lazy StudyMaster discovery) |
| 17C | AI-generated Listening content v1 (StudyGuard targets; study-language question; grounded answer; cache/fallback) |
| 18A | Account Cloud Sync Foundation (Leader-approved source; isolated `study_sync.db` vocabulary store; no production sync) |
| 18B.1 | Authenticated vocabulary sync HTTP (closed `599e473` without production deployment; 18B.7 later copied the server source; `STUDY_SYNC_ENABLED` unset; Sync not activated; no Windows sync client) |
| 18B.2 | Sync DB backup and restore (closed `5f4251a` without production deployment; 18B.7 later copied the scripts; `STUDY_SYNC_ENABLED` unset; Sync not activated; scripts not scheduled; no Windows sync client) |
| 18B.3 | Production-readiness plan (accepted `97f7b25`; planning only; no timer, no deploy, no desktop client) |
| 18B.4 | Sync backup timer and alert contract (accepted `d277791`; templates in the repository and `/opt/language-guard/deploy/hetzner/`; not installed into systemd, enabled, or started; no production paging; sync flag off) |
| 18B.5 | Restore verification (GitHub-verified `6930789`; source copied in 18B.7; no production verification job installed or scheduled) |
| 18B.6 | Isolated local staging (CLOSED `39f3a0b`; repository-only; staging unit not installed) |
| 18B.7 | Controlled dark deploy (CLOSED; server source `d0f2f00`; Sync OFF; no sync timer; seven Linux tests deferred) |

Phase 18B.7 is the last fully CLOSED milestone.

## Current

Phase 18B.8 is **OPEN / NOT CLOSED**. Its source is on `main`. Production monitoring is not installed or enabled. Cloud Sync is OFF.

- Health-monitoring source is committed at `24e600b` and merged at `65b045a`. Monitoring Linux QA of that tree: 106 passed, 0 failed, 0 skipped, per the existing QA report.
- Accounts backup mode fix is committed at `09556f9`. Its Linux QA: 127 passed, 0 failed, 0 skipped, per the existing QA report. That fix is not deployed.
- Three production accounts backups from 2026-11-03 through 2026-11-05 are mode `0644`. They block the next operations step. Do not install the monitoring units or grant verifier traverse while they remain looser than `0600`.

```text
Pre-integration baseline: 09556f909b0ce6d8dcc27816800ef6bcd308f1ab (read 2026-11-08)
Windows installer patch committed at 3dff28d3f78a22da0fda73a50168ed9c3d6e9d57
Phase 18B.7 CLOSED — controlled dark deploy; server source still d0f2f00
Phase 18B.8 OPEN / NOT CLOSED — source on main, operations not installed
Cloud Sync OFF; study_sync.db absent at the 18B.7 deploy; no sync timer
Windows installation safety: local exe and dist match the tested binary
Startup shortcut exists with --lock and has not been launched on this build
Emergency Exit under --lock is not verified on this build
ADR-022 remains architecture only; Phase 18C is not implemented
```

## Next

```text
Production accounts-backup remediation is a blocker, not an authorized task
Do not install 18B.8 units, grant verifier traverse, or set STUDY_SYNC_ENABLED
Phase 18C stays unimplemented
Next major product priority after the sync sequence: AI Local Reading / Listening
Optional later: Listening attempt history / analytics (not mastery / SRS)
Dictionary / pronunciation enrichment (review-before-apply)
Reading Lab improvements
```

Directional only. Source on `main` is not deployment. The Windows client in ADR-022 is not started. Do not renumber the product back to Phase 15.

## Near-term (directional)

- Phase 18B.5 restore verification is closed (GitHub-verified `6930789`; source copied in 18B.7; no production verification job installed or scheduled)
- Phase 18B.6 isolated local staging is closed (`39f3a0b`; not a VPS deployment; staging unit not installed). Proof files are new names in the proof directory. The staging `.env` must match the allowlist before listen. Windows symlink tests skipped.
- Article-Matching Hotfix is closed and GitHub-verified at `d0f2f00`. A Dutch legacy answer was evaluated with English articles from active settings. Explicit quiz language takes priority. Legacy `nl`/`en` keys, canonical `word` entries, and explicit articles/elisions remain supported. On 2026-11-02 full pytest was 487 passed, 7 skipped, and smoke passed every check. The seven skips are Linux-only and were not marked passed. The HTTP 413 WinError 10053 abort did not reproduce in five reruns and is follow-up QA only; production HTTP is unchanged.
- The 2026-11-02 Windows RC build from `d0f2f00` is no longer the installed executable or official `dist`. It was unpublished and is not a release. The current local binary is the 2026-11-08 installation-safety executable recorded in [ADR-023](decisions/ADR-023-windows-installation-safety.md).
- Phase 18B.7 controlled dark deploy is closed. Server source `d0f2f00` is on the VPS with `STUDY_SYNC_ENABLED` unset, sync routes at 404, and no sync timer. The seven Linux tests remain deferred.
- Phase 18B.8 health-monitoring source is on `main` (`24e600b`, merge `65b045a`) and is not installed. The 18B.3 plan used the same number for a later timer installation; that installation has not started. No VPS change or Sync activation is authorized.
- Accounts backup creation in `09556f9` reserves new snapshots at mode `0600` with `UMask=0077`. The commit is not deployed. The 2026-11-05 read-only preflight still blocks installation because three production snapshots are mode `0644`.
- Windows installation safety ([ADR-023](decisions/ADR-023-windows-installation-safety.md)) is committed at `3dff28d3f78a22da0fda73a50168ed9c3d6e9d57`. The tested executable is the local installed app and official `dist`. Startup `--lock` is configured and untested on this build.
- ADR-022 event-first automatic account sync (Accepted, architecture only at `d9d0fe3`; does not replace 18B.5 and does not authorize a client or 18C). Includes replacement overlap preflight and per-account vocabulary isolation. Implementation is not started.
- AI Local Reading / Listening (next major product priority after sync readiness)
- Dictionary / pronunciation enrichment
- Reading Lab improvements
- Optional Listening attempt history / analytics (not mastery)
- Optional future explicit cloud TTS provider behind the same seam (never silent fallback)

## Long-term (directional)

- StudyGuard AI / local model (`StudyGuardAIProvider` / `LocalModelProvider`)
- AI evaluation dataset from AttemptHistory
- Cloud sync transport + Progress/AttemptHistory merge (builds on 18A + stable vocab IDs)
- Production distribution / code signing
- Website evolution (`langstudyguard.com`)
- Commercial / payment layer
- Possible mobile / web clients

## Deferred / deliberate non-goals (for now)

- Premature FSRS state mixed into current Progress persistence
- Semantic duplicate headwords as a product feature (IDs allow it later; policy still blocks duplicate normalized adds)
- Embedding production OpenAI keys in the desktop app
- Treating chat history as project source of truth
- Bundling `.ai/` into the frozen executable as runtime data
- Listening history / SRS / mastery persistence (explicitly out of 17C scope)
- Cloud TTS, STT, or pronunciation scoring for Listening
- Dutch `nl-NL` Windows voice missing on some machines — OS voice install, not an app defect
- Linux symlink and `systemd-analyze` tests remain unverified on this Windows host; they are skips, not passes
- Production cloud sync activation / setting `STUDY_SYNC_ENABLED=1` on the VPS / automatic desktop upload (not 18B.1)
