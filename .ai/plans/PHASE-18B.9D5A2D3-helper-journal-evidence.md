# Phase 18B.9D5A2D3 — Helper journal evidence recovery

Status: **FOCUSED INVESTIGATION COMPLETE — OVERALL FAIL** (E remains unproven). Not a VPS install. Not production activation. D5A2D2 is **not** rewritten as PASS.

Stage 0 baseline `origin/main`: `3b01491199a84a1230ef508d6ca91a277e94f8ed`.  
Stage 0 docs commit: `23917a5f77bdde7af18c9d8a8b166683d42e8aec`.

## Scope

1. Reconcile ecosystem governance for three confirmed repositories (App public; Web private; AI private exists).
2. Recover or correctly capture helper-instance journal records for formal gates **A / D / E**.
3. Documentation-only EnglishApp checkpoints. No App source, Web/AI edits, VPS, Google, OAuth, import merge, or production activation.

## Test environment

| Field | Value |
|---|---|
| Host | WSL `MyAphrodite` (not VPS) |
| Lab | `D:\Tools\age-c2d5a2d2-isolation-20261116T2030Z-e7c4b921` |
| Original evidence | `results-r1/` (**preserved unchanged**) |
| Recovered evidence | `results-r1-recovered/` (new; read-only journal re-query + re-score) |
| Synthetic rerun | **NOT PERFORMED** |
| Canonical modules | Lab `offbox/` SHA-256 check from r1: unchanged **YES** |

## Stage 0 ecosystem sync (public-safe)

| Repo | Fact |
|---|---|
| App | Active workstream; ChatGPT → Cursor; Phase 18B.9 OPEN; D5A2D2 FAIL |
| Web | Private; Product Owner → Antigravity Web; `main` @ `c17c218`; GOV-0B2 review @ `c1296181` not merged; W1.3 @ `b0b5c8a1` not merged; production deploy NOT AUTHORIZED |
| AI | Private `nguyenthaibinh19/langstudyguard-ai` exists; workspace `D:\langstudyguard-ai`; `main` @ `fc021cd4675aedad6cc13d119b44eacb67b7d460`; AI-M0 System Architect Accepted; no inference/training/App integration; `C-APP-AI-001` PROPOSED |
| GOV-0E | Shared GitHub Project future use Owner-accepted; **PLANNED / DEFERRED** |
| GOV-0C | Not authorized |

## Journal collection root cause (established)

**Cause class: (2) Journal collection/query error** (not missing runtime logs for A/D; not invalid runtime for helper journaling itself).

1. Collector used `systemctl list-units --all --no-legend 'lgd5a2d2-handoff@*'`. Finished `Accept=yes` template instances disappear from `list-units`, so the loop captured **no** helper units.
2. Do not treat a template or `@*` pattern as an actual helper instance.
3. `journalctl -u lgd5a2d2-handoff@.service` (template name alone) returned no entries for these Accept=yes instances.
4. `SINCE` was set **after** the intruder test, so a `--since`-filtered helper query would also miss D even if instances were listed.
5. Helper stderr **did** reach the journal (`StandardError=journal` works). Original `results-r1/journal.txt` omitted those lines (worker/intruder/socket systemd lines only + empty helper loop → `-- No entries --`).

Exact original instances:

```text
lgd5a2d2-handoff@0-4097-573_842-991.service   # intruder → refused-not-unit
lgd5a2d2-handoff@1-4-584_854-991.service       # interrupt path → accepted + frame-sent (not incomplete)
lgd5a2d2-handoff@2-4098-584_854-991.service    # positive worker → accepted + frame-sent
```

Evidence paths:

- `results-r1-recovered/helper-instances.txt`
- `results-r1-recovered/journal.txt`
- `results-r1-recovered/collection-root-cause.txt`
- Query scripts (lab-only, new): `scripts/d5a2d3-journal-ro.sh`, `d5a2d3-journal-ro2.sh`, `d5a2d3-journal-recover.sh`, `d5a2d3-score-recovered.sh`

No historical `results-r1` file was modified.

## Scores

### Original D5A2D2 (`results-r1/score.txt`) — preserved

| Test | Score |
|---|---|
| A | FAIL |
| B | PASS |
| C | PASS |
| D | FAIL |
| E | FAIL |
| F | PASS |
| G | PASS (WSL disposable only) |
| H | PASS |
| **OVERALL** | **FAIL** |

### D5A2D3 recovered re-score (`results-r1-recovered/score-recovered.txt`)

Same predicates (`scripts/wsl-score.py`); journal replaced with correctly queried helper instance logs.

| Test | Score | Evidence |
|---|---|---|
| A | **PASS** | `state=ENCRYPTED` + worker success + `decision=accepted` + `detail=frame-sent` on `@2` |
| D | **PASS** | `exact-refused=true` + leaf `lgd5a2d2-intruder.service` + `refused-not-unit` on `@0` |
| E | **FAIL** | Interrupt prefix `hex=4c475331` present, but helper `@1` logged `detail=frame-sent`, **not** `detail=incomplete` |
| B/C/F/G/H | prior PASS retained via r1 inputs | Not re-executed |
| **OVERALL** | **FAIL** | E unproven |

`incomplete` is logged only when `framing.send_all` raises `OSError`. On this run the small synthetic frame completed into the socket after the client read `LGS1` and closed.

## Synthetic rerun

**Not performed.** Original journals were recoverable; the brief requires evaluate-before-rerun. Chasing E with a new interrupt race would be a new experiment, not journal recovery.

## Unit cleanup / inactivity

Observed after investigation (no units started by D5A2D3):

```text
lgd5a2d2-handoff.socket inactive (disabled)
lgd5a2d2-worker.service inactive
lgd5a2d2-intruder.service inactive
lgd5a2d2-cred-missing.service inactive
lgd5a2d2-statedir.service inactive
```

Historical lab users/units/evidence preserved. No destructive cleanup.

## Production limitations (unchanged)

- WSL-only; not VPS proof; not production readiness.
- No accepted production unit set installed.
- Import branch `98b590e` not merged.
- Google Drive **NOT CONFIGURED**; Cloud Sync **OFF**; Phase 18B.9 **OPEN**.
- Production Python / `accounts.db` journal mode still unread.
- Keep `StateDirectory=` off the existing production backup directory.

## Pending Leader review

D5A2D3 overall **FAIL** (E). A/D formal journal predicates are satisfied by recovered original journals. Do not auto-start another correction cycle or production-readiness phase.

## Authorization confirmation

No App canonical source edits, Web/AI repo modifications, VPS/SSH, Google API, OAuth, production DB access, import-branch merge, Cloud Sync activation, or GitHub Project creation occurred.
