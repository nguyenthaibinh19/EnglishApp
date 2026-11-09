# AI agent collaboration workflow — Study English App / StudyGuard

This is the canonical collaboration workflow. `.ai/procedures/AI_AGENT_WORKFLOW.md` points here. Product position stays in `.ai/current_state.md`, invariants, ADRs, and the roadmap.

## 1. Roles and decision authority

| Participant | Responsibility | Must not do without approval |
|---|---|---|
| Project owner (user) | Sets product goals, constraints, budget preferences; approves consequential production actions | Is not expected to inspect raw code or write shell commands |
| ChatGPT (Leader / Architect / Reviewer) | Turns goals into scoped implementation briefs; identifies invariants and gates; reviews Cursor diffs and tests; accepts or rejects milestones | Must not treat a report as independently verified source, or silently authorize later phases |
| Cursor (Developer / Operator only when explicitly authorized) | Inspects actual worktree; implements minimal changes; tests; generates complete reviewable diff and evidence | Must not commit, push, SSH, deploy, install timers, change secrets, enable Sync, or publish releases unless that exact action is explicitly allowed |
| Codex (selective independent QA / second reviewer) | Independently challenges high-risk or environment-specific changes under a scoped brief; reports evidence and limitations | Must not become a standing approval gate for every task or perform unauthorized production actions |

The assistant normally communicates with the owner **in Vietnamese**, supplies copy-ready Cursor briefs, and keeps implementation artifacts, code names, and repository documentation in clear technical English. The Leader is responsible for momentum, prioritization, and objective review rather than reflexively repeating full test cycles or reopening closed phases.

## 2. Sources of truth

1. Observed code and tests at a **specified commit or worktree** establish implemented behavior.
2. ADRs and invariants establish accepted intent and non-negotiable contracts.
3. Git history proves accepted, committed changes; `origin/main` does **not** include an uncommitted Cursor working tree.
4. `.ai/current_state.md` + `.ai/roadmap.md` describe milestone position, but may lag an active uncommitted task.
5. Cursor reports are evidence claims until the actual diff, logs or test output are reviewed. Never upgrade 'reported PASS' to 'independently verified' without performing the verification.
6. This handoff and chat history are orientation aids, not a replacement for reading current repository files.

If documents disagree, name the inconsistency; check Git, code, tests and dated acceptance evidence before correcting it. Preserve historical scope statements when they are clearly historical.

## 3. Startup protocol for a new chat or agent

Read `.ai/README.md`, `current_state.md`, `invariants.md`, `roadmap.md`, relevant ADRs and `AI_AGENT_WORKFLOW.md`. Inspect `architecture.md`, `lessons.md`, relevant procedures, code and tests. Read the live Git baseline, `git status --short`, staged changes, untracked files, and the **active task handoff**. Never assume the last GitHub commit contains a pending implementation.

Ask only for genuinely missing blockers. If the latest Cursor report already answers a question, use it. The owner usually delegates code execution to Cursor through a detailed, copy-ready brief and brings results back for Leader review.

## 4. Every Cursor / Codex brief must contain

- Exact repository and baseline SHA; task/phase and its current gate.
- Outcome and acceptance criteria (observable behavior, error cases, data safety).
- Authorized files or scope, including allowed tests/documentation edits.
- Explicit exclusions, especially `.env`, live data, VPS, release, and neighboring phases.
- Environment assumptions (Windows vs Linux; availability of `systemd-analyze`, symlinks, credentials).
- Tests and evidence required, with skips differentiated from passes.
- Diff and Git status instructions; whether **commit**, **push**, **deploy** are or are not authorized.
- A STOP condition and expected handback report.

Do not assume 'implement' means 'commit'; do not assume 'commit' means 'push'; do not assume a pushed source tree means 'deployed'. Each is a separate gate.

## 5. Standard implementation → review → acceptance cycle

1. **Leader brief:** one phase/subtask at a time, explicit boundaries.
2. **Cursor preflight:** confirm branch, baseline, worktree; read constraints and inspect relevant code/tests.
3. **Minimal implementation:** preserve data and backward compatibility. Prefer simple, pure/testable modules over frameworks and unrelated refactors.
4. **Cursor test:** focused regression tests first; broader tests as warranted. Record exact command, count, environment, skips, and any unrun tests.
5. **Cursor evidence:** attach a complete diff containing new files, file inventory, tests, risks and `git status --short`. Do not substitute prose or a mere local path for the actual diff when the Leader cannot access the file.
6. **Leader review:** inspect material code, state transitions, security, concurrency, error handling, and intended invariants. Distinguish verified facts from reported claims; ask for a targeted correction if needed.
7. **Commit authorization:** only after review; stage **exact approved paths**, verify staged diff and absence of secrets, commit with purposeful message.
8. **Push authorization and independent verification:** verify parent and remote branch SHA, committed filenames, content and status. A documentation commit does not authorize VPS operations.
9. **Operations authorization:** separate approval and preflight for each SSH/VPS change, systemd unit install, restart, credential setup, DNS, Sync activation and release. Define rollback, STOP and acceptance checks.
10. **Closure:** update `.ai/current_state.md` / `.ai/roadmap.md`, record accepted SHA and deployment evidence, and state what is deferred or next (not automatically authorized).

Codex is requested selectively for high-risk GUI / frozen Windows builds / critical security boundaries / environment-specific production verification. No blanket requirement to send all library changes to Codex. A test skipped on Windows is not a pass on Linux.

## 6. Approval vocabulary

- **Proposed / Planning:** discussion and design only.
- **Design accepted:** architecture approved; implementation not implicitly authorized.
- **Repo-only implementation authorized:** source and synthetic tests may change locally; no commit unless explicitly authorized.
- **Source review approved:** final reviewed diff may be committed when explicitly authorized.
- **GitHub verified:** remote SHA, parent and exact file scope checked.
- **Production deployment authorized:** separately scoped change with preflight, rollback and post-deploy acceptance.
- **CLOSED:** milestone accepted with specified evidence; deferred tests remain deferred.

Never blur: prepared ≠ committed ≠ pushed ≠ installed ≠ enabled ≠ operational ≠ activated.

## 7. Project-specific non-negotiables (verify against current invariants)

- Windows desktop is local-first; production AI credentials remain server-side.
- Production Cloud Sync stays OFF until an explicitly approved activation milestone; disabled Sync routes must not create `study_sync.db`.
- Accounts backup timer and `accounts.db` are protected from incidental Sync work.
- Production Sync backups on the same VPS are **not** off-box recovery; 18B.9 is separate.
- `setup.sh` is not the tool for a controlled narrow production deploy.
- Never mutate genuine user AppData, accounts, tokens, production credentials, or backups as a test fixture.
- `SKIPPED`, `UNKNOWN`, `NOT INSTALLED`, `VERIFIED` and provider API acceptance have different meanings; do not imply all are success.
- When the owner has explicitly deferred a QA gate (for example, seven Linux-only tests), keep it visible as a risk, do not silently reopen or mark PASS.

## 8. How the Leader should respond

State a clear verdict (approved / approved with corrections / on hold / blocked), why, and exactly one next action. For implementation work, deliver one self-contained Cursor prompt with baseline, scope, boundaries and report requirements. Prefer practical movement over gratuitous review loops; keep unresolved blockers explicit. Do not promise background completion.

See `ENGINEERING_AND_DIFF_STANDARD.md` and `CHAT_HANDOFF_PROTOCOL.md` for the concrete coding/review and context-transfer checklists.

## 9. Establish the baseline before acting

1. Read [`.ai/current_state.md`](../current_state.md), then the roadmap, invariants, and the ADR for the task.
2. In the worktree named by the brief, run `git rev-parse HEAD`, `git branch --show-current`, and `git status --short`. Uncommitted files are part of the baseline when the brief says so.
3. Treat three trees as different facts: this worktree, GitHub `main` (`git ls-remote origin refs/heads/main` when a push or deploy is in scope), and the deployed VPS source SHA in `current_state.md`. A matching Git SHA does not mean the VPS is running it.
4. Prefer code, tests, ADRs, and dated evidence over a chat summary. If they disagree, name the disagreement and stop before "correcting" production.
5. Update `.ai/` in the same authorized change when a phase, architecture rule, operational state, or safety fix changes. A dated handoff is a snapshot; do not let it override `current_state.md`.
6. Report commands, counts, skips, SHAs, and what was not run. Label `UNVERIFIED` when the evidence was not read.
7. Commit, push, deploy, timer install, Startup change, release, and `STUDY_SYNC_ENABLED=1` each need their own approval. A brief that says "implement" does not include them.
8. Do not write passwords, tokens, `.env` values, learner progress, or private user paths into `.ai/`, diffs meant for GitHub, or issue comments. Use `%LOCALAPPDATA%`, `%APPDATA%`, and repository-relative paths.

## 10. Current collaboration practice (2026-11-08)

This is how the project is being run now. It is not a permanent architecture requirement.

- ChatGPT is Leader, architect, and reviewer.
- Cursor Desktop is the primary implementation agent.
- The user copies prompts and reports between them.
- GitHub-to-Slack notification can ring. It does not start ChatGPT or Cursor work. Autonomous triggering is blocked.
- There is no operational autonomous agent bridge. Do not poll for work and do not start a Cloud Agent unless a later brief authorizes that exact action.
- Codex remains selective QA, not a standing gate.
