# Phase 18C.4P-R5 — Two-way vocabulary and learning progress

Status: **BLOCKED on Owner GUI** (`APP_18C4P_R5_BLOCKED_OWNER_GUI`)  
Date: 2026-11-24  
Baseline: `39fc564ea8867fb7a76bb474d8abcce5eb6bcbe9`

Production Sync stays **ON**. No server source, account, or timer was changed. The recurring sync backup was not run, because these scenarios did not finish.

## Workspace

| Role | Path |
|------|------|
| Machine A client | `D:\EnglishApp\.local\clients\18c4p-r3` |
| Machine A data | `D:\EnglishApp\.local\data\18c4p-r3` |
| Machine A launcher | `D:\EnglishApp\.local\labs\18c4p-r3` |
| Backend | `https://langstudyguard.com` |
| Account | `syncpilot_18c4p` |

Machine A is open, PID 4708, title `langstudyguard`. Its identity is production and its stored Cloud Sync state is Synced. Machine B keeps the Owner's existing isolated client. No new `D:\lg-*` directory was created.

## Baseline

Machine A and the server agree before any new edit:

| Fact | Machine A | Server |
|------|-----------|--------|
| `syncprobe` | Dutch, revision 1, not deleted, meaning is `lab-marker` | Same |
| Learning attempts for this account | 0 | 0 |
| Progress/SRS row for the marker | Absent | Absent |
| Open conflicts | 0 | Not claimed from the UI |
| Other accounts' vocabulary or attempts | Not read | 0 |

The synthetic account has one additional vocabulary row. Its text was not recorded.

## Scenario results

| Scenario | Result |
|----------|--------|
| 1. Bidirectional vocabulary | **BLOCKED**. Server and Machine A still show revision 1. Machine B was not observed. No edit was made. |
| 2. Attempts, Progress, and SRS | **BLOCKED**. Attempt count is still 0. No quiz answer was submitted. |
| 3. Idempotent replay | **UNVERIFIED**. There is no accepted learning event to replay, and there is no production harness that can retransmit one without reading the saved session token. |

No Conflict label was observed because no edit was made.

## Owner actions

Wait until Cloud Sync says **Synced** after each save. Do not copy a database between the computers.

1. On B, confirm `syncprobe` / `lab-marker`. Open **Vocabulary**, edit that item, change the meaning to `lab-marker-b`, and save.
2. After B says Synced, confirm A shows `lab-marker-b` and neither client says Conflict.
3. On the open Machine A window, edit the same item to `lab-marker-a` and save.
4. Confirm B shows `lab-marker-a` and both say Synced.
5. On B, choose **Start today's study**. Answer exactly one card for `syncprobe`, then stop. If that card is not offered, add one synthetic Dutch word through **Add word**, then answer that one card only.
6. After both clients say Synced, report the meaning each computer shows, whether either said Conflict, and the attempt count each computer shows.

Do not send the password or a screenshot of the session.
