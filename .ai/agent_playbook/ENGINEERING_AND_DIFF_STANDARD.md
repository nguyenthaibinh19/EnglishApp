# Engineering, test, diff and QA standard — StudyGuard

This is the canonical engineering, test, diff, and review standard. Read it with `.ai/invariants.md`, `AI_AGENT_WORKFLOW.md`, `HOW_TO_RUN_TESTS.md`, and the relevant ADRs. Code and tests remain the authority for exact interfaces.

## 1. Implementation style

- Make the **smallest safe change** consistent with the current approved phase. No opportunistic cleanup, frameworks, dependencies, deployment rewrites, or broad refactors.
- Keep business/domain rules out of Tkinter callbacks. Make services and validation independently testable; use explicit inputs and return values.
- Preserve compatibility, persistence schema and public API contract unless the brief explicitly changes them. Do not reuse existing fields with different semantics.
- Keep UI operations off blocking background work; preserve the ScreenGuard and child-window lifecycle contracts. Do not alter Windows installed files or AppData in tests.
- Prefer standard library and existing requirements; justify each new dependency, particularly on the production VPS.
- For filesystem writes: validate paths, reject unsafe symlinks/aliases where required; use private permissions; write to a fresh temp file; flush/fsync and atomically publish; no-clobber and durable identity when relevant. Do not delete old user data to make a test pass.
- For concurrent jobs and state files: coordinate locks, atomic updates, crash recovery and deduplication; test concurrent invocations, partial failure and retry behavior.
- For alerts/monitoring: record exactly which check ran and what it proved; `SKIPPED` / `UNKNOWN` / `NOT INSTALLED` must not masquerade as success. A provider accepting an HTTP request is not proof the user read a message. Preserve durable pending incidents per channel until acceptance or explicitly specified resolution.
- Never log or commit secrets, tokens, passwords, raw user vocabulary/answers, provider response bodies or sensitive production paths. Minimize blast radius; separate privileged components and audit same-UID exposure.
- For database verification, operate on a completed snapshot opened read-only; do not migrate, touch the live database, or conflate a missing database with a verified restore.
- Avoid replacing the accounts backup scheduler, modifying production `.env`, or enabling Cloud Sync under an unrelated milestone.

## 2. Test design and reporting

- Favor `tmp_path`, fake providers, synthetic SQLite databases, deterministic clocks and explicit environment injection. No real provider, production VPS, genuine AppData or live backup paths in unit tests.
- Tests should enforce behavior and invariants: success, failure, identity, tamper/symlink protection, stale state, missing config, concurrency, retries and rollback semantics.
- Run focused tests for each touched subsystem; run adjacent regression tests. Full `python -m pytest` and `python app/smoke_test.py` are standard when relevant and within current scope, not invented as past PASS for a different tree.
- Test reports include **command, working platform/interpreter, exact PASS/FAIL/SKIP counts**, exit code, skipped-test reasons, and what was not run. Windows symlink/systemd skips are unresolved Linux coverage, never PASS.
- Report evidence truthfully: 'Cursor reports 69 passed, 5 skipped' is not independent verification until test artifacts or a separate run are checked.
- Codex selective independent QA is a scoped step, not an automatic additional gate. Codex must not alter production unless expressly authorized.

## 3. Diff location and complete visibility

Store local review artifacts at **`diff/<phase>-<short-topic>.diff`** (for example `diff/phase18b8-health.diff`). This is a local QA artifact: generally **do not stage or commit `diff/`**. The attached diff contents, not merely its name, must be available to Leader. Keep logs in local untracked QA paths; do not stage them.

Before review:

```bash
git rev-parse HEAD
git status --short
git diff --name-only
git diff --cached --name-only
```

**Untracked new source files do not appear in plain `git diff`.** To include them without staging their contents, use intent-to-add for **exact authorized new paths**:

```bash
git add -N -- app/health_monitor.py app/health_notify.py
# Include other approved new paths explicitly — do not use git add -A.
git diff HEAD --check
git diff HEAD > diff/phase18b8-health.diff
git diff --cached --name-only
```

`git add -N` creates index intent entries (often the empty blob `e69de29...`), **not real staged source**. The cached-name output should contain no real staged modifications unless deliberately authorized. A commit with only intent-to-add does not add file contents. Explain the technique and its limits in the report. If `git add -N` is undesirable, use separate no-index diffs for each untracked file and attach them; do not omit them silently.

Run `git diff HEAD --check`; report any line-ending warning separately from whitespace errors. Preserve existing line endings; do not rewrite entire files to address cosmetic warnings. Verify the diff is complete and excludes unrelated untracked artifacts.

## 4. Code review checklist

- Scope: changed paths match brief; unrelated production paths and data untouched.
- Correctness: public APIs, schema/identity, status transitions, timer schedule/timezone, error semantics.
- Security: least privilege, credentials, filesystem permissions, symlinks and traversal, log redaction, safe HTTP requests.
- Reliability: atomic state, file identity, idempotency, concurrent timers, retry failure and recovery behavior.
- Deploy separation: source copied to app tree is **not** a unit installed in `/etc/systemd/system`; an installed unit is not necessarily enabled or working.
- QA: tests are appropriate, counts exact, skipped cases visible, synthetic fixtures isolated.
- Documentation: ADR/invariants and milestone status accurately updated; no future work declared completed.

## 5. After explicit commit approval

```bash
git status --short
git diff HEAD --check
# Stage only the exact approved file paths; do not stage diff/, logs, .cursor/, QA data.
git add -- <approved paths explicitly>
git diff --cached --check
git diff --cached --name-status
git diff --cached
# Inspect the entire staged diff, then commit only if the Leader authorized it.
```

After an authorized push, report full SHA, parent, exact filenames, commit message, remote branch SHA and final `git status --short`. The Leader should independently verify the remote commit. A clean *tracked* status may coexist with pre-existing untracked local artifacts.

**Important:** Commit/push, production installation, service restart, cron/systemd enablement, `.env` or credential edits, DNS edits, Sync activation, and Windows release are separate explicitly authorized actions. Never infer one from another.

## 6. Operational changes require extra gates

A production runbook must identify pinned source hashes, exact touched files/units, preflight checks, backups and restoration path, allowed restart scope, prohibited operations, rollback steps and post-deploy acceptance evidence. No `setup.sh` for narrow dark deployment. Verify account login, authenticated AI, health and disabled Sync behavior only if appropriate to the authorized change. Report what is proven and what was not tested. Do not treat a source-only milestone as an operations authorization.
