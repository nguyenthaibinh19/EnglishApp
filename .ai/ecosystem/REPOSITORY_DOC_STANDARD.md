# Repository documentation standard

EnglishApp `.ai/` is the structural reference for every LanguageGuard product repository.

## Required skeleton

```text
.ai/
  README.md
  current_state.md
  roadmap.md
  architecture.md
  invariants.md
  lessons.md
  decisions/          # ADRs
  plans/              # phase records including FAIL/BLOCKED
  procedures/         # how-to checklists
  agent_playbook/
    README.md
    AI_AGENT_WORKFLOW.md   # or repo-adapted workflow
    ENGINEERING_AND_DIFF_STANDARD.md  # when implementation diffs are used
    ACTIVE_HANDOFF.md
    CHAT_HANDOFF_PROTOCOL.md          # optional but recommended
    handoffs/                         # dated snapshots
```

Web may keep additional `docs/design/` outside `.ai/` for visual artifacts.

Future AI repos should add indexes for datasets/evaluations/model artifacts **without** embedding secrets or PII.

## Reading order (new agent in a product repo)

1. Ecosystem [ACTIVE_WORKSTREAM.md](ACTIVE_WORKSTREAM.md) and [ECOSYSTEM_CHARTER.md](ECOSYSTEM_CHARTER.md) if the task is cross-repo
2. Local `.ai/current_state.md`
3. Local `.ai/invariants.md`
4. Local `agent_playbook/ACTIVE_HANDOFF.md` (or Website equivalent until playbook split)
5. Local workflow / diff standard
6. Relevant ADR / architecture / procedure
7. Code and tests named by the brief

## Source-of-truth hierarchy (per repo)

```text
Tests / enforceable behavior
  + current code
  + ADRs / invariants
  + Git history
  + roadmap / current_state
```

Ecosystem governance docs override only on **cross-repo process and contracts**, not on local test truth.

## Documentation checkpoints

- **EnglishApp:** standing documentation-only push policy exists in App `AI_AGENT_WORKFLOW.md` section 11 for `.ai/` under Leader/owner rules already granted for App.
- **Web / AI:** App’s documentation-push authorization does **not** automatically extend. Each repo needs its own Owner-granted checkpoint policy before agents push docs.
- Always record FAIL/BLOCKED durably.
- Do not commit secrets, labs with credentials, or private Web content into public App docs.

## Website-specific rules to retain

When applying this skeleton to Web:

1. Zero-deletion / no unauthorized `dist/` destruction
2. Repository isolation from EnglishApp
3. No DNS/VPS changes without Owner brief
4. Honest download/legal gating

Do not weaken those invariants to “match App.”

## Onboarding checklist

1. Confirm GitHub access for the target repo (public App ≠ private Web/AI).
2. Read ecosystem active workstream.
3. Read local current_state + invariants + ACTIVE_HANDOFF.
4. Confirm baseline SHA from the brief.
5. Stay inside the assigned repository.
