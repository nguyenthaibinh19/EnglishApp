# Phase 18B.9D5A2D3 — Helper journal evidence recovery

Status: **AUTHORIZED — Stage 0 documentation checkpoint recorded.** Stage 1 WSL investigation not yet executed at the time of this Stage 0 commit.

Baseline `origin/main` at Stage 0 start: `3b01491199a84a1230ef508d6ca91a277e94f8ed`.

## Scope

1. Reconcile ecosystem governance for three confirmed repositories (App public; Web private; AI private exists).
2. Focused WSL synthetic investigation to recover or correctly capture helper-instance journal records for formal gates **A / D / E** from D5A2D2.
3. Documentation-only EnglishApp checkpoints. No App source, Web/AI edits, VPS, Google, OAuth, import merge, or production activation.

## Historical context

D5A2D2 report: [PHASE-18B.9D5A2D2-wsl-isolation.md](PHASE-18B.9D5A2D2-wsl-isolation.md).

- Original overall score: **FAIL** (B/C/F/G/H PASS; A/D/E FAIL on formal journal criteria).
- Lab: `D:\Tools\age-c2d5a2d2-isolation-20261116T2030Z-e7c4b921`
- Evidence: `results-r1/` (also under WSL evidence path recorded in D5A2D2).
- Raw functional hints existed (`ENCRYPTED`, exact `REFUSED`, `LGS1`) but did **not** override formal FAIL.
- Collection defect noted: helper instance journals not captured; `systemctl` warned about invalid unit name `@` / `@*` patterns.

Do **not** rewrite D5A2D2 as PASS.

## Ecosystem facts recorded at Stage 0 (public-safe)

| Repo | Fact |
|---|---|
| App | Active workstream; ChatGPT → Cursor; Phase 18B.9 OPEN; D5A2D2 FAIL |
| Web | Exists private; Product Owner → Antigravity Web; `main` @ `c17c218`; GOV-0B2 review @ `c1296181` not merged; W1.3 @ `b0b5c8a1` not merged; production deploy NOT AUTHORIZED |
| AI | Exists private `nguyenthaibinh19/langstudyguard-ai`; canonical workspace `D:\langstudyguard-ai`; `main` @ `fc021cd4675aedad6cc13d119b44eacb67b7d460`; AI-M0 System Architect Accepted; no inference/training/App integration; `C-APP-AI-001` PROPOSED |
| GOV-0E | Shared GitHub Project future use Owner-accepted; **PLANNED / DEFERRED** — not created |
| GOV-0C | Not automatically authorized |

## Stage 1 plan (after Stage 0 push)

1. Read-only inspect lab units, collection scripts, `results-r1`, and journal with exact instance identifiers.
2. If journals recoverable, evaluate against original A/D/E predicates before any rerun.
3. At most one focused synthetic revalidation of A/D/E into new `results-r2/` if needed; preserve `results-r1`; leave units inactive; no unrestricted loops.

## Results (filled after Stage 1)

_Pending Stage 1 execution._

## Authorization confirmation

Stage 0: documentation only. No WSL experiments, VPS/SSH, Google, OAuth, source edits, Web/AI modifications, GitHub Project creation, or import-branch merge in Stage 0.
