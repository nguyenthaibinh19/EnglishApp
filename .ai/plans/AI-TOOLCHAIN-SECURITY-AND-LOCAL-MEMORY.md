# AI toolchain security and local memory

Status: **PROPOSED — NOT AUDITED — NOT AUTHORIZED FOR INSTALLATION**.

Recorded 2026-11-27 from Owner and Architect discussion. This file does not install, build, or execute either repository. GitHub `.ai/` remains the canonical source of approved project knowledge and authorization.

## Taste Skill

Repository: https://github.com/leonxlnx/taste-skill

- Candidate design skill for the Astro website.
- Potentially useful design principles for the desktop UI.
- Not adopted. Not installed.
- Must not override the accepted LanguageGuard design system.
- Source, scripts, dependencies, and network behavior require review before any execution.

## AI Memory

Repository: https://github.com/akitaonrails/ai-memory

Proposed approach, if a later brief authorizes a trial:

- Audit a pinned upstream commit.
- Build locally from reviewed source.
- Start with an isolated synthetic repository.
- Use a local authenticated loopback server.
- No cloud LLM, no cloud embeddings, and no public endpoint.
- No automatic global hooks and no startup service in the initial trial.
- Evaluate Cursor-to-Codex handoff.
- Evaluate Antigravity integration later.
- Native Windows compatibility remains experimental until verified.

AI Memory would be supplementary operational memory. It would not replace ADRs, invariants, or human approval. ChatGPT on the web is not claimed to have access to a local memory server.

## Third-party tool review policy

Proposed, and not yet applied to either repository above:

- Inspect `SKILL.md`, executable scripts, hooks, installers, and build scripts.
- Audit dependencies, permissions, licenses, and outbound data flows.
- Pin reviewed versions and commit SHAs.
- Avoid direct download-and-execute installation commands.
- Use isolated environments and synthetic data.
- Require project-scoped capture allowlists.
- Exclude credentials, production data, and learner information.
- Do not rely solely on secret sanitization.
- Review updates before adoption.
- Preserve existing human authorization boundaries.

A Trusted Skills Registry is a proposed future development-tooling improvement. It is not built.

## Boundary

Do not install, build, clone for execution, or activate hooks for Taste Skill or AI Memory from this record. A later Architect brief is required before any of those actions.
