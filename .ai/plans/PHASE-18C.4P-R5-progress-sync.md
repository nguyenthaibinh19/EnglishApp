# Phase 18C.4P-R5 — Two-way vocabulary and learning progress

Status: **accepted in R5; R6 restart confirmed** (`APP_18C4P_R6_FINAL_ACCEPTANCE_READY_FOR_ARCHITECT_REVIEW`)  
Date: 2026-11-24  
Baseline: `60b967d98917edfa7014aba2f5a72f8855385394`

Production Sync stays **ON**. No server source, account, service, or timer was changed. One verified one-shot sync backup was taken after the tests. The recurring sync backup timer stays disabled.

## Workspace

| Role | Path |
|------|------|
| Machine A client | `D:\EnglishApp\.local\clients\18c4p-r3` |
| Machine A data | `D:\EnglishApp\.local\data\18c4p-r3` |
| Machine A launcher | `D:\EnglishApp\.local\labs\18c4p-r3` |
| Backend | `https://langstudyguard.com` |
| Account | `syncpilot_18c4p` |

Client A is the left window. Client B is the right window on the same computer, data `.local\data\18c4p-r3-b`. This is a same-machine production test. It does not replace the earlier physical two-computer vocabulary result.

## Baseline

This table is the earlier blocked measurement. The same-machine result below is the current state. At the start of this run both clients already showed revision 2, meaning `lab-marker-2`.

| Fact | Machine A | Server |
|------|-----------|--------|
| `syncprobe` | Dutch, revision 1, not deleted, meaning is `lab-marker` | Same |
| Learning attempts for this account | 0 | 0 |
| Progress/SRS row for the marker | Absent | Absent |
| Open conflicts | 0 | Not claimed from the UI |
| Other accounts' vocabulary or attempts | Not read | 0 |

The synthetic account has one additional vocabulary row. Its text was not recorded.

## Evidence categories

| Category | This run |
|----------|----------|
| Automated localhost integration | `test_idempotent_progress_retry_and_outbox_durability` passed again. It does not contact production. |
| Same-machine production | The two processes below, against `https://langstudyguard.com`. |
| Physical two-computer production | Unchanged: vocabulary A → VPS → B is **PASS — Owner confirmed**. This run did not use the second computer. |

## Same-machine production result

Launcher verification: paths distinct, tokens present and not copies, databases present and not byte-identical, device ids present and distinct.

Both processes were signed in as `syncpilot_18c4p`, user id 3, production, Dutch. Before the new edits both already showed `syncprobe` revision 2, meaning `lab-marker-2`, Synced.

| Step | Result |
|------|--------|
| Client B changed the meaning to `lab-marker-b` | Both clients reached revision 3 and Synced. |
| Client A changed the meaning to `lab-marker-a` | Both clients and the server reached revision 4, meaning `lab-marker-a`, not deleted. |
| One quiz answer on Client B | The card showed `lab-marker-a`. The answer `syncprobe` was exact. Each client has 1 acked attempt and confirmed SRS seen 1, correct 1, wrong 0, streak 1, interval 1, state version 1. |
| Server, user 3 only | Schema 3, integrity ok, 2 vocabulary rows, 1 attempt, 1 progress row with the same SRS numbers. Other accounts: 0 vocabulary rows and 0 attempts. |
| Conflicts | 0 open on both clients. Explicit conflict UI was not exercised. |

Production replay of that event was not performed. The localhost idempotent test remains the replay evidence.

## Backup

`study-sync-20261124-111255-200807.db`, 86016 bytes, mode 0600, owner guard, integrity ok, schema 3. The verifier service returned `VERIFIED` for that file. The accounts backup timer stays enabled. The sync backup timer stays disabled. The Sync flag stays on.

## Still open

Explicit conflict, offline reconnect, a production replay of the same event, a second quiz submission, and a quit/reopen persistence check were not part of this run. Client B is still on the quiz after the one correct answer. Do not submit another answer unless a later test asks for a second event.
