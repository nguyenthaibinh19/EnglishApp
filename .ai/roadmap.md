# Roadmap

Directional plan — **not** a rigid release commitment. Update when phases complete or priorities shift.

## Latest operational checkpoint — 2026-11-19 (supersedes older narrative below)

- **Active priority: Phase 18B.9 OFF-BOX — OPEN / PRODUCTION NOT READY.** PR #12 / PR #13 merged; inactive VPS packaging installed (old app-tree paths). Executable-path audit **ACCEPTED UNSAFE** ([Issue #8](https://github.com/nguyenthaibinh19/EnglishApp/issues/8#issuecomment-7009010670)).
- **Source-only remediation in review:** dedicated root-owned `/opt/language-guard-offbox` execution tree; systemd templates use `/usr/bin/python3 -I`; packager `install-execution-tree`; offline deps + trust regressions. Design: [OFFBOX_RUNTIME_TRUST.md](procedures/OFFBOX_RUNTIME_TRUST.md). **Not deployed. No auto-merge.**
- **Outstanding VPS gate (needs separate Owner auth):** corrective write to install the execution tree and replace inactive unit files; then read-only re-audit must report **PASS** before any isolation/activation. No daemon-reload/start in the default corrective scope unless newly authorized.
- **Cloud Sync:** OFF. **Google Drive production:** NOT CONFIGURED. **age / recipient / OAuth:** not provisioned for offbox. **Historical D5A2D2 and D5A2D3:** FAIL preserved.
- **AI:** `C-APP-AI-001` v0.2.0 accepted; PR #14 conformance MERGED. `LocalAIProvider` / AI-M4 NOT AUTHORIZED.

**Historical sections below contain dated design/lab milestones and may use superseded phrases such as “PROPOSED” or “not installed”; do not use them as an authorization or current deployment statement.**

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
| 18B.4 | Sync backup timer and alert contract (accepted `d277791`; 18B.8 installed the unit and left the timer disabled; no production paging; sync flag off) |
| 18B.5 | Restore verification (GitHub-verified `6930789`; 18B.8 enabled the production verifier; `SKIPPED` is not a successful restore) |
| 18B.6 | Isolated local staging (CLOSED `39f3a0b`; repository-only; staging unit not installed) |
| 18B.7 | Controlled dark deploy (CLOSED; server source `d0f2f00`; Sync OFF; no sync timer in that deploy; seven Linux tests deferred) |
| 18B.8 | Production health monitoring (CLOSED — Leader Accepted, 2026-11-10; monitoring only; Cloud Sync OFF; sync-verify enabled; sync-backup timer installed and disabled) |
| 18B.9B | Local encrypted recovery proof (CLOSED — Leader Accepted, 2026-11-10, `274156e`; synthetic restic only; historical suite 30 passed, 1 skipped; later wrong-password check passed; full suite not rerun; not a production uploader) |

Phase 18B.9B is a CLOSED historical sub-milestone. Later 18B.9D5A2* gates and source/inactive packaging milestones are documented in the latest operational checkpoint above. Phase 18B.9 itself remains OPEN.

## Current

The active phase is still 18B.9. **The following paragraph records older 2026-11-16 context; use the 2026-11-19 operational checkpoint above for current state.** Step 18B.9D5A2C1 is CLOSED — Leader Accepted, 2026-11-16, as the localhost HTTPS transport milestone. Step 18B.9D5A2C2 is CLOSED — Leader Accepted, 2026-11-16, as one synthetic Google Drive live shot only, checkpoint `29317d0`. Neither step is production off-box backup. A second live attempt is NOT AUTHORIZED. The synthetic Drive object remains until separate deletion approval. 18B.9D5A2C3 Production Readiness Review is Leader Accepted as PLANNING COMPLETE ([PHASE-18B.9D5A2C3-production-readiness.md](plans/PHASE-18B.9D5A2C3-production-readiness.md)); overall NOT READY. D5A2D0 canonical source inventory remains planning basis ([PHASE-18B.9D5A2D0-canonical-source-inventory.md](plans/PHASE-18B.9D5A2D0-canonical-source-inventory.md)). D5A2D0-P1 is CLOSED — Leader Accepted, 2026-11-16, for controlled source import only (`phase18b9/d5a2d0-p1-source-import` @ `98b590e`); not merged. D5A2D2 WSL isolation focused run scored OVERALL FAIL and remains FAIL ([PHASE-18B.9D5A2D2-wsl-isolation.md](plans/PHASE-18B.9D5A2D2-wsl-isolation.md)). GOV-0A is Leader Accepted with corrections. GOV-0B1 is CLOSED — Leader Accepted ([ecosystem/README.md](ecosystem/README.md)). AI repo `langstudyguard-ai` exists (private); App↔AI not integrated; `C-APP-AI-001` PROPOSED. GOV-0C is NOT AUTHORIZED. GOV-0E GitHub Project is PLANNED / DEFERRED. D5A2D3 helper-journal recovery remains historical **OVERALL FAIL** ([PHASE-18B.9D5A2D3-helper-journal-evidence.md](plans/PHASE-18B.9D5A2D3-helper-journal-evidence.md)). D5A2D4 is CLOSED — Leader Accepted REVISE TEST ([PHASE-18B.9D5A2D4-interrupted-transfer-semantics.md](plans/PHASE-18B.9D5A2D4-interrupted-transfer-semantics.md)). D5A2D5 is CLOSED — Leader Accepted revised WSL isolation safety gate ([PHASE-18B.9D5A2D5-revised-isolation-evidence.md](plans/PHASE-18B.9D5A2D5-revised-isolation-evidence.md)). D5A2D6 is CLOSED — Leader Accepted READY_FOR_SOURCE_INTEGRATION_REVIEW ([PHASE-18B.9D5A2D6-source-integration-readiness.md](plans/PHASE-18B.9D5A2D6-source-integration-readiness.md)); not merge approval. D5A2D7-R2/P1 CLOSED — Leader Accepted; source on review branch `e2160e7` — NOT MERGED ([PHASE-18B.9D5A2D7-source-integration-candidate.md](plans/PHASE-18B.9D5A2D7-source-integration-candidate.md)). GOV-0E CLOSED — Leader Accepted ([GITHUB_PROJECT_OPERATIONS.md](ecosystem/GITHUB_PROJECT_OPERATIONS.md)). The map is [PHASE-18B.9-offbox-status.md](plans/PHASE-18B.9-offbox-status.md). Google Drive 5 TB is the accepted preferred pre-public store and adds no storage subscription. Backblaze B2 is the fallback and is not provisioned. Phase 18B.9C1 remains DESIGN ACCEPTED, 2026-11-10. Age v1.3.2 with an `age1pq1` recipient is validated on WSL only. [ADR-024](decisions/ADR-024-offbox-age-drive.md) is the local Drive adapter. Nothing from that adapter is installed on the VPS. Daily off-box monitoring, failure and stale alerts, and a restore drill are mandatory and are not installed. No production remote backup has been run. Phase 18B.9 remains OPEN. Phase 18B.9C2 is NOT AUTHORIZED. Google Drive production stays NOT CONFIGURED. Cloud Sync stays OFF. The Windows Startup `--lock` hotfix is DEFERRED until the affected computer is available. It is not diagnosed. Website W1 is handled by Antigravity in a separate workspace.

Phase 18B.8 is **CLOSED — Leader Accepted, 2026-11-10**. The closure is monitoring infrastructure. Vocabulary Cloud Sync stays OFF. `study_sync.db` is absent.

- Accounts backup safety from `09556f9` is deployed. The 2026-11-10 natural snapshot `accounts-20261110-032712.db` is mode `0600`, `guard:guard`, and 20480 bytes. Retention is 14. The backup directory is mode `0700`.
- Health monitoring is operational. The socket, health timers, and sync-verify timer are enabled. The sync-backup timer is installed, disabled, and inactive.
- The natural verifier ran at `2026-11-10 07:00:00 UTC` and recorded `SKIPPED` at `2026-11-10T07:00:01Z`. That is not a successful sync backup or restore.
- The natural 09:00 report ran at `2026-11-10 08:00:00 UTC`. Telegram and email were `PROVIDER_ACCEPTED`, and the user received both. Healthchecks accepted `2026-11-10`. The latest observed 30-minute check was `2026-11-10 11:30:20 UTC`.
- The one-line `ReadOnlyPaths` hotfix is in commit `f57bcc6`.
- UptimeRobot external uptime monitor: UNVERIFIED / DEFERRED. It is not an operational pass.

```text
Pre-integration baseline: 09556f909b0ce6d8dcc27816800ef6bcd308f1ab (read 2026-11-08)
Windows installer patch committed at 3dff28d3f78a22da0fda73a50168ed9c3d6e9d57
Phase 18B.7 CLOSED — controlled dark deploy; server source still d0f2f00
Phase 18B.8 CLOSED — Leader Accepted, 2026-11-10; monitoring only
Cloud Sync OFF; study_sync.db absent; sync-verify timer enabled; sync-backup timer installed and disabled
UptimeRobot external uptime monitor: UNVERIFIED / DEFERRED
Windows installation safety: local exe and dist match the tested binary
Startup shortcut exists with --lock and has not been launched on this build
Emergency Exit under --lock is not verified on this build
ADR-022 remains architecture only; Phase 18C is not implemented
```

## Next

```text
Phase 18B.9 remains OPEN. Google Drive 5 TB is the preferred pre-public store. No new storage subscription
Backblaze B2 EU Central is the fallback and is not provisioned
B2 is not assumed to be append-only. Object Lock and a deleting lifecycle stay off
Phase 18B.9C1 DESIGN ACCEPTED, 2026-11-10. The age `.age` artifact remains the architecture. WSL validated age v1.3.2 and an age1pq1 recipient. ADR-024 replaces rclone
The local adapter is not installed. 18B.9D5A2C, 18B.9D5A2C1, and 18B.9D5A2C2 are Leader accepted. D5A2C1 is localhost; D5A2C2 is one synthetic live shot only
Daily 09:00 Europe/Amsterdam off-box status, failure and stale alerts, and a restore drill are mandatory and are not installed
Before activation, Google Drive is NOT CONFIGURED. No production remote backup has been run
Cloud Sync stays OFF
18B.9C2 external synthetic drill is NOT AUTHORIZED. D5A2C3 planning accepted; D5A2D0-P1 import accepted on review branch only (unmerged); D5A2D2/D5A2D3 FAIL preserved; D5A2D4 CLOSED — REVISE TEST; D5A2D5 CLOSED — revised WSL gate; D5A2D6 CLOSED — Leader Accepted READY_FOR_SOURCE_INTEGRATION_REVIEW (not merge); D5A2D7-R2/P1 CLOSED — Leader Accepted (review branch only; NOT MERGED; PR NOT CREATED); GOV-0A accepted with corrections; GOV-0B1 CLOSED — Leader Accepted; GOV-0C NOT AUTHORIZED; GOV-0E CLOSED — Leader Accepted; GOV-0E-A1 merged (PR #10); GOV-0E-A2 CLOSED — Leader Accepted; D5A2D7 SOURCE MERGED — NOT DEPLOYED (PR #12 / `c03a0f5`); next: production packaging (inactive units) without enablement; AI-M2 acceptance pending; LocalAIProvider NOT AUTHORIZED; production NOT READY
A second D5A2C2 live attempt is NOT AUTHORIZED. Synthetic Drive object deletion needs separate approval
RPO 26h and RTO target 4h remain proposals, not accepted guarantees
Windows Startup --lock hotfix is DEFERRED until the affected computer is available
Website W1 is handled by Antigravity in a separate workspace
Do not enable the sync backup timer
Do not set STUDY_SYNC_ENABLED
Phase 18C stays unimplemented
Next major product priority after the sync sequence: AI Local Reading / Listening
Optional later: Listening attempt history / analytics (not mastery / SRS)
Dictionary / pronunciation enrichment (review-before-apply)
Reading Lab improvements
```

Directional only. Source on `main` is not deployment. The Windows client in ADR-022 is not started. Do not renumber the product back to Phase 15.

## Near-term (directional)

- Phase 18B.5 restore verification source is closed. Phase 18B.8 enabled the production verifier. Its natural `SKIPPED` result is not a successful restore.
- Phase 18B.6 isolated local staging is closed (`39f3a0b`; not a VPS deployment; staging unit not installed). Proof files are new names in the proof directory. The staging `.env` must match the allowlist before listen. Windows symlink tests skipped.
- Article-Matching Hotfix is closed and GitHub-verified at `d0f2f00`. A Dutch legacy answer was evaluated with English articles from active settings. Explicit quiz language takes priority. Legacy `nl`/`en` keys, canonical `word` entries, and explicit articles/elisions remain supported. On 2026-11-02 full pytest was 487 passed, 7 skipped, and smoke passed every check. The seven skips are Linux-only and were not marked passed. The HTTP 413 WinError 10053 abort did not reproduce in five reruns and is follow-up QA only; production HTTP is unchanged.
- The 2026-11-02 Windows RC build from `d0f2f00` is no longer the installed executable or official `dist`. It was unpublished and is not a release. The current local binary is the 2026-11-08 installation-safety executable recorded in [ADR-023](decisions/ADR-023-windows-installation-safety.md).
- Phase 18B.7 controlled dark deploy is closed. Server source `d0f2f00` is on the VPS with `STUDY_SYNC_ENABLED` unset and sync routes at 404. No sync timer was installed in that deploy. The seven Linux tests remain deferred.
- Phase 18B.8 is CLOSED — Leader Accepted, 2026-11-10. Monitoring is operational. The natural verifier at 07:00 UTC recorded `SKIPPED`, which is not a successful restore. The natural 09:00 report was provider-accepted, and the user received Telegram and email. The sync-verify timer is enabled. The sync-backup timer is installed and disabled. Cloud Sync is OFF. UptimeRobot is UNVERIFIED / DEFERRED.
- Accounts backup creation in `09556f9` is deployed. The 2026-11-10 snapshot `accounts-20261110-032712.db` is mode `0600`. Retention is 14.
- Windows installation safety ([ADR-023](decisions/ADR-023-windows-installation-safety.md)) is committed at `3dff28d3f78a22da0fda73a50168ed9c3d6e9d57`. The Startup `--lock` hotfix is DEFERRED until the affected computer is available. The shortcut targets the installed executable with `--lock`. Normal GUI launch passed. Automatic Startup and Emergency Exit under `--lock` are not verified, and the failure is not diagnosed.
- Phase 18B.9B is CLOSED — Leader Accepted, 2026-11-10, commit `274156e`. It is a local synthetic restic proof, not the production artifact. The historical suite was 30 passed and 1 skipped. A later wrong-password check passed, and the full suite was not rerun. Phase 18B.9 remains OPEN. The step map is [PHASE-18B.9-offbox-status.md](plans/PHASE-18B.9-offbox-status.md). `18B9D4C` means Phase 18B.9 step D4C, not Phase 18B.4. Leader accepted D4C, D5A2B3, D5A2C, D5A2C1, and D5A2C2. D5A2B1 is not accepted. D5A2C1 is CLOSED — Leader Accepted, 2026-11-16, localhost only. D5A2C2 is CLOSED — Leader Accepted, 2026-11-16, one synthetic live shot, checkpoint `29317d0`. A second live attempt is NOT AUTHORIZED. The synthetic Drive object remains until separate deletion approval. Next is D5A2C3 production-readiness review, planning only. Age v1.3.2 and an `age1pq1` recipient are validated on WSL only. [ADR-024](decisions/ADR-024-offbox-age-drive.md) replaces `rclone`. The adapter is not installed. Google Drive is NOT CONFIGURED. Phase 18B.9C2 is NOT AUTHORIZED. A 26-hour RPO and a 4-hour RTO remain proposals.
- ADR-022 event-first automatic account sync (Accepted, architecture only at `d9d0fe3`; does not replace 18B.5 and does not authorize a client or 18C). Includes replacement overlap preflight and per-account vocabulary isolation. Implementation is not started.
- AI Local Reading / Listening remains the product priority after the sync sequence, including the still-open Phase 18B.9. Website W1 is handled by Antigravity in a separate workspace.
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
