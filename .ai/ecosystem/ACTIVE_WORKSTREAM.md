# Active workstream

**Effective:** 2026-11-18 (GOV-0E CLOSED — Leader Accepted).  
**Product Owner final authority:** yes.  
**Next governance phases:** GOV-0C **NOT AUTHORIZED**. GOV-0E **CLOSED**; GOV-0E-A2 **CLOSED — Leader Accepted** (live smoke). Ordinary Project label tracking in use; see [GITHUB_PROJECT_OPERATIONS.md](GITHUB_PROJECT_OPERATIONS.md).

## Current assignment

| Field | Value |
|---|---|
| Active workstream | **APP** — `nguyenthaibinh19/EnglishApp` |
| Active Workstream Lead | **ChatGPT** |
| Technical agent | **Cursor** |
| System Leader / Architect | **ChatGPT** (ecosystem-wide) |
| Web day-to-day | Product Owner → Antigravity Web (milestone reports to ChatGPT) |
| AI day-to-day | Product Owner → Antigravity AI (milestone reports to ChatGPT) |
| Shared Project | Private `LangstudyGuard` — https://github.com/users/nguyenthaibinh19/projects/1 |

## Reporting depth

- App: detailed technical evidence to ChatGPT — see [AGENT_REPORTING_STANDARD.md](AGENT_REPORTING_STANDARD.md).
- Web/AI: milestone-level to ChatGPT unless contract/security escalation.

## Preserved App gates (unchanged by GOV-0E)

- Phase 18B.9: **OPEN**
- Production: **NOT READY**
- Google Drive: **NOT CONFIGURED**
- Cloud Sync: **OFF**
- D5A2D2: **OVERALL FAIL** (formal tests A/D/E not proven; do not rewrite as PASS)
- D5A2D3: **OVERALL FAIL** (E); historical FAIL preserved
- D5A2D7-P1: **CLOSED — Leader Accepted** — review branch only; **PR NOT CREATED; NOT MERGED; NOT DEPLOYED**
- Canonical source import: branch-only `phase18b9/d5a2d0-p1-source-import` @ `98b590ef5707e0c84bf68175ed59cdc17d8753c5` — **not merged**

## Confirmed sibling repositories (existence ≠ integration)

- Web: `nguyenthaibinh19/langstudyguard-web` (private) — exists
- AI: `nguyenthaibinh19/langstudyguard-ai` (private) — exists; AI-M2 implementation committed @ `5cd4dd2`; architectural acceptance pending; no App↔AI integration accepted
- `C-APP-AI-001`: **PROPOSED / IN REVIEW** — not ACCEPTED; App LocalAIProvider **NOT AUTHORIZED**

## Later checkpoint — 2026-11-27

The 2026-11-18 assignment and gate table above are historical. Read [current_state.md](../current_state.md) for the accepted position. Do not rewrite D5A2D2 or D5A2D3 into a pass.

- Phase 19.3 multilingual audio is merged to main (PR #32, `7aedf7a423d2ef244ce37b5d3f348c7f75ed0241`). It is not in the installed public release v1.5.0.
- Phase 19.2B UI is merged (PR #31, `5f8f3c0ad175a82ad61866e23eac64af1bfe47ed`) and is also not in v1.5.0.
- Cloud Sync for the production pilot was ON as of the 2026-11-24 checkpoint. That observation was not rechecked on 2026-11-27.
- Google Drive remains **NOT CONFIGURED**. Phase 18B.9 remains **PAUSED, NOT CLOSED**.
- `C-APP-AI-001` v0.2.0 is accepted. `LocalAIProvider` is not authorized. The private website is not deployed. Existence of the web and AI repositories is not integration.
- Next product implementation is Adaptive Vocabulary, pending a separate Architect brief.

## Change control

Update this file only when a [LEADERSHIP_HANDOFF_PROTOCOL.md](LEADERSHIP_HANDOFF_PROTOCOL.md) handoff completes or the Owner corrects a factual error.
