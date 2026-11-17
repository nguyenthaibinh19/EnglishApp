# Phase 18B.9D5A2D5 — Revised WSL isolation evidence consolidation

Status: **READ-ONLY REVIEW COMPLETE — `REVISED_WSL_GATE_READY_FOR_LEADER_REVIEW`.**  
Final CLOSED acceptance of the isolation milestone remains with ChatGPT. This step does **not** auto-close Phase 18B.9 isolation and does **not** authorize production.

Baseline `origin/main`: `5d178934b5d9d0fe3588ac7f29bed50186bec033`.  
No new tests, source edits, unit changes, or historical evidence modifications.

## Leader decision already in force (D5A2D4)

**D5A2D4 CLOSED — Leader Accepted: REVISE TEST.**

Accepted interrupted-transfer criteria:

| Id | Criterion |
|---|---|
| **E1** | Receiver rejects incomplete/invalid frames and cannot advance a failed transfer to successful backup states. |
| **E2** | A genuine sender-side `send()` failure produces `detail=incomplete`, nonzero return, and no successful transfer claim. |

- Original race-based E predicate is **superseded for future acceptance**, not retroactively rewritten.
- Historical D5A2D2 / D5A2D3 **OVERALL FAIL** records remain unchanged.
- No application-level ACK protocol is required by the current accepted contract (ADR-024 framing + independent Drive download verify).

## Provenance map (labs)

| Step | Lab / evidence | Role |
|---|---|---|
| D5A2D2 | `D:\Tools\age-c2d5a2d2-isolation-20261116T2030Z-e7c4b921\results-r1\` | Original focused WSL isolation suite; historical score **OVERALL FAIL** |
| D5A2D3 | Same lab `\results-r1-recovered\` | Read-only journal re-query of the original Nov 16 run; collection bug fixed in capture only |
| D5A2D4 | `D:\Tools\age-c2d5a2d4-interrupt-20261117T1500Z-a8f3c1e2\results-e1e2-r3\` | Deterministic E1/E2 suite; Leader Accepted REVISE TEST |
| Import | commit `98b590ef5707e0c84bf68175ed59cdc17d8753c5` | Canonical 15-module inventory; **not merged** |

Module hashes:

- D5A2D2 `results-r1/canonical-hash-check.txt`: all 15 listed modules **OK** against lab `offbox/` (copy of accepted inventory).
- D5A2D4 `results-e1e2-r3/canonical-hash-check.txt`: **MATCH 15/15** against import `98b590e` SHA256SUMS.

## Historical scores (unchanged)

### D5A2D2 `results-r1/score.txt`

```text
A_positive_transfer=FAIL
B_stderr_isolated=PASS
C_unauthorized_peers=PASS
D_invalid_cgroup=FAIL
E_interrupted_fail_closed=FAIL
F_missing_credentials=PASS
G_statedir_disposable=PASS
G_note=wsl-disposable-only-not-vps-proof
H_existing_unchanged_and_inactive=PASS
OVERALL=FAIL
```

### D5A2D3 `results-r1-recovered/score-recovered.txt`

```text
A_positive_transfer=PASS
B_stderr_isolated=PASS
C_unauthorized_peers=PASS
D_invalid_cgroup=PASS
E_interrupted_fail_closed=FAIL
… B/C/F/G/H PASS …
OVERALL=FAIL
```

D5A2D3 root cause: helper journals existed; collector used `list-units 'lgd5a2d2-handoff@*'` after instances finished (empty) and set `SINCE` after the intruder. Exact instances recovered: `@0-4097-573_842-991`, `@1-4-584_854-991`, `@2-4098-584_854-991`.

## D5A2D4 harness integrity (read-only)

Harness: `…/age-c2d5a2d4-…/scripts/d5a2d4-e1e2-tests.py` against isolated `offbox/` copies from `98b590e`.

| Concern | Assessment |
|---|---|
| Exercises real framing? | **Yes** — E1 calls `framing.receive` / `encode_frame`; E2 calls `framing.send_all`. |
| Exercises real worker fail-closed? | **Yes** — E1 calls `backup_worker.run(..., connected=MemSock(truncated))`; observes attempt state **FAILED**/`truncated`. |
| Exercises real helper incomplete path? | **Yes** — E2 calls `snapshot_helper.serve`; `MemSock.fail_after` forces `OSError` inside `send_all` → real `except OSError` → `detail=incomplete`. |
| Patches that bypass safety under test? | **No for E1/E2 paths.** Patches are prerequisites only: `probe_source`→`unreadable`, `find_age`/`recipient_rejected` so worker reaches `receive`; `peer_auth`→`accepted` and stub `snapshot_memory` so helper reaches `send_all`. **Not** patched: `framing.receive`, worker `_fail` / state machine after non-verified, helper incomplete/`frame-sent` branches. |
| MemSock vs real Unix socket | Deterministic stand-in for recv/send faults. Sufficient for E1/E2 **contract** proof; not a full systemd Accept=yes integration re-run for E. |
| ACK | Not claimed; not required. |

Authoritative D5A2D4 score (`results-e1e2-r3/score.txt`): **7/7 PASS**.

## Revised criterion matrix (D5A2D5 composite)

Verification method: read-only inspection of lab artifacts listed below. No new runs.

| Criterion | Expected | Evidence | Observed (non-secret) | Method | Revised result | Limitations |
|---|---|---|---|---|---|---|
| **A** Positive transfer + encrypt + helper frame-send | ENCRYPTED; worker success; `decision=accepted`; `detail=frame-sent` | D2 `attempt-states.txt`, `worker-show.txt`; D3 `journal.txt` `@2` | `state=ENCRYPTED`; `Result=success` `ExecMainStatus=0`; `decision=accepted` + `detail=frame-sent size=8192` | Cross-check D2 raw + D3 recovered journal | **PASS** | WSL synthetic; ciphertext not Drive VERIFIED |
| **B** Stderr isolated from protocol | Interrupt prefix = LGS1 magic; `StandardError=journal` | D2 `interrupt-prefix.txt` (`hex=4c475331`); unit `StandardError=journal` | Prefix magic only; no `event=` leak in prefix file | D2 score B PASS + files | **PASS** | Same WSL run |
| **C** Unauthorized peers blocked | DAC errno=13 for non-backup peers | D2 `dac-probe.txt` | `normal-connect=errno=13`, `guard-connect=errno=13` | D2 score C PASS | **PASS** | Socket DAC on WSL |
| **D** Invalid cgroup refused | Exact REFUSED + `refused-not-unit` | D2 `intruder-result.txt`; D3 journal `@0` | `exact-refused=true … first4=52454655 leaf=lgd5a2d2-intruder.service`; `decision=refused-not-unit` | D2 raw + D3 journal | **PASS** | Historical D2 formal D was FAIL only due to missing journal capture |
| **E1** Receiver fail-closed | Truncated/partial → not verified; worker FAILED; no success states | D4 `score.json` e1_* cases; attempt dirs under `results-e1e2-r3/` | `status=truncated`; worker `FAILED`/`truncated`; attempt `FAILED` | D4 suite + harness review | **PASS** | Deterministic MemSock; not systemd E re-run |
| **E2** Sender send failure | `detail=incomplete`; nonzero; no `frame-sent` | D4 e2_* cases | `rc=1`; `incomplete_logged=true`; `frame_sent_logged=false`; audit `transfer-incomplete` | D4 suite + harness review | **PASS** | Injected `OSError`; not race-based early close |
| **F** Missing credentials | Fail closed at CREDENTIALS | D2 `cred-missing-show.txt`, `cred-missing-journal.txt` | `ActiveState=failed`, `ExecMainStatus=243`, CREDENTIALS step failure | D2 score F PASS | **PASS** | |
| **G** StateDirectory disposable | Ownership change on disposable dir | D2 `statedir-before.txt` / `after.txt` | before `700 0 0` / marker root; after dir `755 991 981`, marker uid/gid backup | D2 score G PASS | **PASS** | **WSL disposable only — not VPS proof**; must not apply `StateDirectory=` to existing production backup dir |
| **H** Historical unchanged + inactive | Prior units unchanged; new units inactive | D2 `historical-unchanged.txt`, `unit-state.txt` | `unchanged`; socket inactive/disabled; services inactive (cred-missing recorded failed, not running) | D2 score H PASS | **PASS** | |

### Score lineage (do not relabel history)

| Layer | Result |
|---|---|
| Historical D5A2D2 | **OVERALL FAIL** (A/D/E formal FAIL as scored) |
| Historical D5A2D3 | **OVERALL FAIL** (E still FAIL under original race predicate; A/D recovered) |
| Accepted D5A2D4 semantics | **REVISE TEST** — E1+E2 replace race-based E; suite 7/7 PASS |
| **Proposed D5A2D5 revised composite** | **All revised criteria PASS** → gate ready for Leader review |

Original race-based E remains a historical FAIL. Composite uses **E1+E2**, not a retroactive D2 E PASS.

## Gaps

**No unmet revised WSL acceptance criterion identified** that requires another WSL test.

Optional clarity (not blockers for this review):

- E1/E2 are contract/unit deterministic proofs, not a second full `lgd5a2d2-*` systemd Accept=yes campaign.
- Composite acceptance ≠ production readiness (see below).

## Production readiness delta (untouched VPS)

Local WSL safety evidence ≠ deploy authorization.

Still open:

1. Source-import branch `98b590e` **unmerged**
2. No approved production unit installation
3. Production Python version and SQLite journal mode **unknown**
4. `StateDirectory=` ownership risk on pre-existing dirs (G WSL-only)
5. Google Drive production **NOT CONFIGURED**
6. Daily off-box monitoring and restore drill **not installed**
7. Cloud Sync **OFF**; Phase 18B.9 **OPEN**; production **NOT READY**

## Recommendation to Leader

1. Accept D5A2D5 consolidation as **revised WSL isolation safety gate ready for review**.
2. Keep D5A2D2/D5A2D3 OVERALL FAIL artifacts as historical truth.
3. Treat E1+E2 as the interrupted-transfer acceptance criteria going forward.
4. Do **not** auto-progress to production unit install, import merge, Drive activation, or another phase without a separate brief.

## Authorization confirmation

Read-only evidence review and EnglishApp `.ai/` documentation only. No new synthetic runs, canonical source edits, VPS/SSH, Google/OAuth, import merge, Web/AI changes, Cloud Sync, production backup, or GitHub Project creation.
