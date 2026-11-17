# Phase 18B.9D5A2D4 — Interrupted transfer safety contract review

Status: **INVESTIGATION COMPLETE — recommendation REVISE TEST.** Not a VPS install. Not production activation. Does **not** rewrite D5A2D2/D5A2D3 as PASS. Isolation gate remains FAIL until Leader revises E acceptance criteria and accepts a replacement proof.

Baseline `origin/main`: `6bfee89fc30edcd47528ae4ef27cccea642e7606`.  
Import source inspected at `98b590ef5707e0c84bf68175ed59cdc17d8753c5` (branch-only; **not merged**).

## Scope

Separate and test:

| Property | Meaning |
|---|---|
| **E1 — Receiver fail-closed** | Truncated / malformed / interrupted frame must never become a verified snapshot; worker must not continue to encryption/upload success states from that frame. |
| **E2 — Sender failure detection** | If the helper’s socket **send** actually fails (`OSError`), helper must log `detail=incomplete`, exit nonzero, and must not claim successful transfer. |

Do **not** assume that a peer closing after four bytes causes a sender-side `OSError`. A successful send is local socket write completion, not application-level ACK.

## Source inspection (import `98b590e`)

### `framing.py`

- `encode_frame` / `send_all`: loop `sock.send` until all bytes written; `count <= 0` → `OSError("short-write")`.
- `receive`: short read → status `"truncated"` with empty payload; only `"verified"` returns a body after size+SHA-256 check.
- Docstring: *“A short read is an incomplete transfer, not a snapshot.”*

### `snapshot_helper.py`

- After accepted peer + `SNAPSHOTTED`, calls `framing.send_all(sock, framing.encode_frame(...))`.
- `except OSError` → audit `FAILED`/`transfer-incomplete`, log `detail=incomplete`, return `1`.
- On success → log `detail=frame-sent`, return `0`.
- `frame-sent` means **local send completed**, not receiver acknowledgment.

### `backup_worker.py`

- `status, payload = framing.receive(sock)`.
- If `status != "verified"` → `_fail(attempt_dir, status)` → state **FAILED**; return. No `RECEIVED` / `ENCRYPTED` / `UPLOADING` / `VERIFIED` from that path.
- Truncation is therefore a **receiver** fail-closed path (E1), independent of helper journaling.

ADR-024 and the accepted architecture describe length-and-hash framing and independent download verification for Drive. They do **not** require an application-level ACK on the handoff socket.

## Why D5A2D2 `@1` logged `detail=frame-sent`

Exact instance: `lgd5a2d2-handoff@1-4-584_854-991.service` (D5A2D3 recovery).

1. Interrupt client read four bytes (`LGS1`) then closed (`wsl-interrupt-sequence.py`).
2. Helper still ran snapshot + `send_all` of a small synthetic frame (~8 KiB).
3. Kernel socket buffer accepted the full write → **no** `OSError`.
4. Helper therefore logged `decision=accepted` and `detail=frame-sent`, then exited 0 for that instance.
5. The original E predicate required `detail=incomplete` in the journal — which only appears when `send_all` raises.

So the original E test **did not force a failed send**. It assumed early client close ⇒ sender-side exception. That assumption is false for small frames when the write completes locally.

## What the worker does after a truncated frame

`framing.receive` returns `"truncated"`. Worker records **FAILED** / `truncated` and stops. It does not transition to RECEIVED, ENCRYPTED, UPLOADING, or VERIFIED from that transfer.

## Acknowledgment protocol?

A stronger **end-to-end delivery** guarantee (sender knows receiver verified the frame) would need an explicit ACK (or equivalent). That is **absent** from the accepted architecture. It is a possible future proposal, not an implemented requirement. D5A2D4 does **not** implement a protocol change.

For the current contract, E1 (receiver fail-closed) + E2 (sender detects real send failures) match the code as written.

## Lab and commands

| Field | Value |
|---|---|
| Lab | `D:\Tools\age-c2d5a2d4-interrupt-20261117T1500Z-a8f3c1e2` |
| Modules | Isolated copies from `98b590e` under `offbox/` — **15/15 SHA-256 MATCH**; canonical import bytes not edited |
| Authoritative evidence | `results-e1e2-r3/` |
| Prior setup attempts preserved | `results-e1e2/` (setup miss), `results-e1e2-r2/` (age path miss) — not deleted |
| D5A2D2 / D5A2D3 evidence | Unchanged |

Commands:

```text
# byte-preserving extract of offbox from 98b590e + SHA256SUMS check (15/15)
PYTHONDONTWRITEBYTECODE=1 python scripts/d5a2d4-e1e2-tests.py
# authoritative output: results-e1e2-r3/score.txt and score.json
```

Test harness (lab-only): `scripts/d5a2d4-e1e2-tests.py` — fault-injecting `MemSock`; does not alter historical labs.

## Deterministic results (`results-e1e2-r3`)

| Case | Property | Result |
|---|---|---|
| `e1_framing_magic_only` | E1 | PASS — `receive(LGS1)` → `truncated` |
| `e1_framing_partial_body` | E1 | PASS — partial frame → `truncated` |
| `e1_worker_truncated_fail_closed` | E1 | PASS — worker `FAILED`/`truncated`; attempt state FAILED; no RECEIVED/ENCRYPTED |
| `e1_worker_partial_frame_fail_closed` | E1 | PASS — same |
| `e2_send_all_raises` | E2 | PASS — `send_all` raises on failing socket |
| `e2_helper_incomplete_on_send_fail` | E2 | PASS — helper `rc=1`, `detail=incomplete`, audit FAILED/`transfer-incomplete`, no `frame-sent` |
| `e2_helper_incomplete_mid_send` | E2 | PASS — mid-frame send inject → incomplete |
| **Suite** | | **7 passed, 0 failed** |

These results prove E1 and E2 under deterministic faults. They do **not** silently convert historical D5A2D2 test E to PASS.

## Decision matrix

| Question | Answer |
|---|---|
| Original E test sufficiently proves the intended safety requirement? | **No** — it conflates early client close with sender `OSError` / `incomplete`. |
| Original E test requires a deterministic replacement? | **Yes** — replace with explicit E1 + E2 predicates/tests. |
| Receiver-side fail-closed (E1) proven? | **Yes** — framing + worker suite above. |
| Sender-side error handling (E2) proven? | **Yes** — fault-injected send failure → `incomplete` / nonzero. |
| Stronger acknowledgment protocol needed for current accepted architecture? | **No** (not required by ADR-024 / current framing). Optional future proposal only if Owner wants delivery ACK. |

## Recommendation

**REVISE TEST**

1. Keep D5A2D2 overall FAIL / E FAIL as historical record of the race-based predicate.
2. Accept D5A2D4 E1+E2 as the contract clarification and replacement proof for interrupted-transfer **safety** under the existing protocol.
3. Do **not** CHANGE PROTOCOL unless Owner separately requires ACK semantics.
4. Do not treat this as production readiness or VPS authorization.

## Preserved gates

- D5A2D2 **OVERALL FAIL** (unchanged)
- D5A2D3 **OVERALL FAIL** (E unproven under original predicate; investigation accepted)
- Phase 18B.9 **OPEN**; production **NOT READY**; Drive **NOT CONFIGURED**; Cloud Sync **OFF**
- Import branch **not merged**

## Authorization confirmation

No VPS/SSH, Google/OAuth, canonical source edits, import merge, production units/backup, Cloud Sync, Website/AI modifications, or protocol implementation changes occurred.
