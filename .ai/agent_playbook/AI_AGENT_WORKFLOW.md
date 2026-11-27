# AI agent collaboration workflow — Study English App / StudyGuard

This is the canonical collaboration workflow. `.ai/procedures/AI_AGENT_WORKFLOW.md` points here. Product position stays in `.ai/current_state.md`, invariants, ADRs, and the roadmap. GitHub `.ai/` remains the approved project memory. The tools in [AI-TOOLCHAIN-SECURITY-AND-LOCAL-MEMORY.md](../plans/AI-TOOLCHAIN-SECURITY-AND-LOCAL-MEMORY.md) are proposed, not audited, and not authorized for installation.

## 1. Roles and decision authority

| Participant | Responsibility | Must not do without approval |
|---|---|---|
| Project owner (user) | Sets product goals, constraints, budget preferences; approves consequential production actions | Is not expected to inspect raw code or write shell commands |
| ChatGPT (Leader / Architect / Reviewer) | Turns goals into scoped implementation briefs; identifies invariants and gates; reviews Cursor diffs and tests; accepts or rejects milestones | Must not treat a report as independently verified source, or silently authorize later phases |
| Cursor (Developer / Operator only when explicitly authorized) | Inspects actual worktree; implements minimal changes; tests; generates complete reviewable diff and evidence; publishes documentation checkpoints | Must not commit or push application source, SSH, deploy, install timers, change secrets, enable Sync, or publish releases unless that exact action is explicitly allowed. Documentation-only checkpoints under `.ai/` are standing owner authorization; see section 11 |
| Codex (selective independent QA / second reviewer) | Independently challenges high-risk or environment-specific changes under a scoped brief; reports evidence and limitations | Must not become a standing approval gate for every task or perform unauthorized production actions |

The assistant normally communicates with the owner **in Vietnamese**, supplies copy-ready Cursor briefs, and keeps implementation artifacts, code names, and repository documentation in clear technical English. The Leader is responsible for momentum, prioritization, and objective review rather than reflexively repeating full test cycles or reopening closed phases.

## 2. Sources of truth

1. Observed code and tests at a **specified commit or worktree** establish implemented behavior.
2. ADRs and invariants establish accepted intent and non-negotiable contracts.
3. Git history proves accepted, committed changes; `origin/main` does **not** include an uncommitted Cursor working tree.
4. `.ai/current_state.md` + `.ai/roadmap.md` describe milestone position. A documentation checkpoint must be pushed when status changes, including a failure. They may still lag source that exists only in a local lab.
5. Cursor reports are evidence claims until the actual diff, logs or test output are reviewed. Never upgrade 'reported PASS' to 'independently verified' without performing the verification.
6. This handoff and chat history are orientation aids, not a replacement for reading current repository files.

If documents disagree, name the inconsistency; check Git, code, tests and dated acceptance evidence before correcting it. Preserve historical scope statements when they are clearly historical.

## 3. Startup protocol for a new chat or agent

Read `.ai/README.md`, `current_state.md`, `agent_playbook/ACTIVE_HANDOFF.md`, `invariants.md`, `roadmap.md`, relevant ADRs and `AI_AGENT_WORKFLOW.md`. Inspect `architecture.md`, `lessons.md`, relevant procedures, code and tests. Read the live Git baseline, `git status --short`, staged changes, untracked files, and the **active task handoff**. `current_state.md` is the accepted product state. `ACTIVE_HANDOFF.md` is the latest coordination checkpoint and does not replace it. Cursor records a Leader decision only when the Leader or the owner stated it. Never assume the last GitHub commit contains a pending implementation.

Ask only for genuinely missing blockers. If the latest Cursor report already answers a question, use it. The owner usually delegates code execution to Cursor through a detailed, copy-ready brief and brings results back for Leader review.

## 4. Every Cursor / Codex brief must contain

- Exact repository and baseline SHA; task/phase and its current gate.
- Outcome and acceptance criteria (observable behavior, error cases, data safety).
- Authorized files or scope, including allowed tests/documentation edits.
- Explicit exclusions, especially `.env`, live data, VPS, release, and neighboring phases.
- Environment assumptions (Windows vs Linux; availability of `systemd-analyze`, symlinks, credentials).
- Tests and evidence required, with skips differentiated from passes.
- Diff and Git status instructions; explicitly list whether **commit**, **push**, **merge**, **SSH**, or **deploy** are authorized. Multiple steps can be preauthorized together in one brief.
- A STOP condition and expected handback report.

Do not assume 'implement' means 'commit', or a pushed tree means 'deployed'. These are distinct operations, **not necessarily distinct approval conversations**: the Owner can explicitly authorize an entire bounded chain in one brief.

## 5. Lean implementation → review → acceptance cycle (Owner direction 2026-11-19)

**Default: ONE TASK → ONE IMPLEMENTATION → ONE CONSOLIDATED REVIEW → TARGETED FIX (IF NEEDED) → MERGE + DOCS.** Optimize for delivery and token use, not maximum checkpoints.

1. **One complete brief:** set outcome, risk level, constraints, acceptance tests and documentation deliverable. The brief may explicitly authorize a bounded chain (inspect → implement → self-fix → test → document → PR/commit/push/merge) in one go. Do not silently add rights not stated in the authorization.
2. **Developer executes continuously:** baseline/preflight and safety checks are internal steps of the task, not separate approval cycles. Cursor/Antigravity implements, corrects routine defects, runs focused and appropriate adjacent tests, updates docs with the work, and returns one coherent diff/PR and concise evidence report. No request to review each file or interim test unless truly blocked.
3. **Leader reviews once at task completion:** inspect material source, security invariants, tests and documentation; distinguish reported from independently verified results. **Batch all material findings into one review** and one correction brief. Additional rounds only for remaining blocking defects, new scope, or significant high-risk discoveries.
4. **Source closeout:** if commit/push/merge is included in the original authorization, complete it after the specified gates without asking again. If not, get the missing scoped approval. Keep one PR per logical change when practical. Record the merged SHA and operational/not-operational distinction.
5. **Production/high-risk work:** use one explicit, narrowly bounded Owner authorization that may include preflight → controlled write → verification → documentation/report, and conditional substeps when stated in advance. Apply STOP on drift, unforeseen destructive effects, credential/data exposure, or failed safety gates. **No implied consent** for SSH, daemon-reload, service execution, data migration, secrets, Cloud Sync, or activation; specify each permitted operation and rollback boundary in the brief. Never execute out-of-scope steps to reduce latency.
6. **Documentation is mandatory but batched:** update current state, relevant roadmap/decision/procedure/handoff and Issue/PR evidence **at task closure** or immediately at a material FAIL/BLOCKED/UNSAFE status. No duplicate documentation commits after each green test or small micro-step.

**Risk proportionality:** Low-risk UI/docs/small refactor → implement/test/docs and close within preauthorized scope. Medium-risk feature/API/AI changes → one PR and consolidated Leader review. High-risk security/production/DB/credentials → rigorous fail-closed evidence with scoped Owner authorization, but still batch internal checks and minimize unnecessary handoffs.

Historical results, especially security FAIL/UNSAFE, must remain traceable after successful corrections. A previously rejected or skipped test does not become PASS by virtue of a later task.

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

State a concise verdict and exactly one next action. For implementation, send **one consolidated Cursor brief** and **one consolidated feedback batch**, not a sequence of prompts for ordinary internal steps. Review proportionately to risk; do not require repeated approval for preauthorized work. Keep unresolved blockers explicit. Do not promise background completion.

See `ENGINEERING_AND_DIFF_STANDARD.md` and `CHAT_HANDOFF_PROTOCOL.md` for the concrete coding/review and context-transfer checklists.

## 9. Establish the baseline before acting

1. Read [`.ai/current_state.md`](../current_state.md), then the roadmap, invariants, and the ADR for the task.
2. In the worktree named by the brief, run `git rev-parse HEAD`, `git branch --show-current`, and `git status --short`. Uncommitted files are part of the baseline when the brief says so.
3. Treat three trees as different facts: this worktree, GitHub `main` (`git ls-remote origin refs/heads/main` when a push or deploy is in scope), and the deployed VPS source SHA in `current_state.md`. A matching Git SHA does not mean the VPS is running it.
4. Prefer code, tests, ADRs, and dated evidence over a chat summary. If they disagree, name the disagreement and stop before "correcting" production.
5. Update `.ai/` in the same authorized change when a phase, architecture rule, operational state, or safety fix changes. A dated handoff is an immutable snapshot. `ACTIVE_HANDOFF.md` is the rolling coordination checkpoint. Neither overrides `current_state.md`. Cursor does not invent a Leader decision.
6. Report commands, counts, skips, SHAs, and what was not run. Label `UNVERIFIED` when the evidence was not read.
7. Source commit, source push/merge, deploy, timer install, Startup change, release, and `STUDY_SYNC_ENABLED=1` must each be **explicitly within an authorized scope**, but may be bundled in **one upfront approval** when sufficiently bounded. A documentation-only checkpoint under `.ai/` has standing authority. A brief that says only "implement" does not automatically include a push or deploy.
8. Do not write passwords, tokens, `.env` values, learner progress, or private user paths into `.ai/`, diffs meant for GitHub, or issue comments. Use `%LOCALAPPDATA%`, `%APPDATA%`, and repository-relative paths.

## 10. Current collaboration practice (2026-11-08)

This is how the project is being run now. It is not a permanent architecture requirement.

- ChatGPT is Leader, architect, and reviewer.
- Cursor Desktop is the primary implementation agent.
- The user copies prompts and reports between them.
- GitHub-to-Slack notification can ring. It does not start ChatGPT or Cursor work. Autonomous triggering is blocked.
- There is no operational autonomous agent bridge. Do not poll for work and do not start a Cloud Agent unless a later brief authorizes that exact action.
- Codex remains selective QA, not a standing gate.

## 11. Documentation checkpoints

The project owner granted this rule on 2026-11-16. It is standing authorization for documentation only. It is not authorization to commit application source, tests, labs, secrets, or to deploy.

Publish concise documentation as part of the **same logical task** at these moments:

- At task closure/merge/installation when the project status, architecture or next gate changes.
- Immediately for material **FAILED / BLOCKED / UNSAFE** outcomes, even if the task is not accepted.
- Before a genuine agent/conversation handoff or loss of continuity; refresh `ACTIVE_HANDOFF.md` rather than replicating the entire roadmap.
- When long-running work needs a durable checkpoint, only if significant uncommitted state would otherwise be lost.

**Do not** checkpoint after every green test, small subtask, routine correction, or review comment. Prefer one coordinated docs update with the source PR and a single final status sync, keeping historical failures traceable. On a short task, docs in the same PR are sufficient.

Do not wait for ACCEPTED. A failed experiment stays in the history. Do not commit a keystroke, temporary output, or an unchanged status.

Use `.ai/current_state.md` for the active gate, `.ai/roadmap.md` for direction, `.ai/plans/` for task evidence, `.ai/decisions/` for architecture, and `.ai/agent_playbook/handoffs/` for a historical chat snapshot. Refresh `.ai/agent_playbook/ACTIVE_HANDOFF.md` when coordination changes, and publish it through this section. It does not replace `current_state.md`. Label each fact as one of: IMPLEMENTED, TESTED, REPORTED, PENDING REVIEW, CHANGES REQUIRED, ACCEPTED, COMMITTED, PUSHED, DEPLOYED, ACTIVE. A reported pass is not an independent verification. A documentation commit is not a source commit and not a deployment. A failure is not a successful milestone.

For FAILED, BLOCKED, or REJECTED work, record the step, the time, what was attempted, the environment, the result and reason, the lab or worktree identifier, sanitized hashes, what is still unverified, and the STOP condition. When a later correction succeeds, add a new checkpoint that names the earlier failure. Do not rewrite Git history to hide a result.

Before every documentation push: read `git status` and `origin/main`; review the whole staged diff; reject secrets, credentials, session URIs, private identities, production data, and any source file; stage exact `.ai/` paths only; do not use `git add -A`; commit; push a fast-forward only. If the remote has moved or unrelated changes would be included, stop and report BLOCKED. Do not force-push, reset, discard, or stash unrelated work.

Source commits, releases, VPS changes, systemd changes, database operations, Google API calls, credential provisioning, Cloud Sync, and deletion remain separately gated.
