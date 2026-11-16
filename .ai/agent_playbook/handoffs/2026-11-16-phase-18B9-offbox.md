# Handoff — Phase 18B.9 off-box, 2026-11-16

This is the chat-boundary snapshot. After this documentation commit, [current_state.md](../../current_state.md) and [PHASE-18B.9-offbox-status.md](../../plans/PHASE-18B.9-offbox-status.md) are the durable record. The 2026-11-03 handoff is historical and stops before Phase 18B.8 was accepted.

## Repository

- Repository: `https://github.com/nguyenthaibinh19/EnglishApp`
- Documentation commit: this commit, on `main`, made from `phase18b9/local-recovery-poc`.
- Parent: `d4b8588a2bd3401534fff94bed48b5e283d8a7c5`.
- Deployed server source remains `d0f2f004c85ce9f4265d33bd034ba18423f1e3a5`. This commit is not a deploy.
- The checkout `D:\EnglishApp` is an older branch. The Phase 18B.9 worktree is `D:\EnglishApp-worktrees\phase18b9-local-poc`. Do not edit the older checkout for this work.

## Closed, and the open gate

Phase 18B.7, 18B.8, and 18B.9B are closed. Phase 18B.9C1 is the accepted design, with the transfer and age-validation sentences corrected by [ADR-024](../../decisions/ADR-024-offbox-age-drive.md).

Leader accepted 18B.9D4C, 18B.9D5A2B3, and 18B.9D5A2C. Steps 18B.9D4E, 18B.9D5A1, and 18B.9D5A2A completed their one approved operation. 18B.9D5A2B1 is not accepted. 18B.9D5A2B2 repaired the socket and failed encryption; 18B.9D5A2B3 closed that encryption failure.

The active gate is **18B.9D5A2C1, not accepted**. Localhost tests were 37 passed, 0 failed, 0 blocked. The live script SHA-256 is `36973802cf63073e927871770bb467ba1bb3a4ac43389d77f28aae6f0cd147aa`. It has not been executed. Do not run it unless a later brief sets `LG_LIVE_APPROVAL` to exactly `APPROVE D5A2C1 SYNTHETIC DRIVE ONLY`.

## Production

Cloud Sync is OFF. `study_sync.db` is absent. The sync-verify timer is enabled. A `SKIPPED` result is not a successful restore. The sync-backup timer is installed, disabled, and inactive. Accounts backup retention is 14. Google Drive is NOT CONFIGURED. No off-box unit is installed on the VPS. The VPS has `lg-backup` uid 994 gid 977 and an empty mode 0700 `/var/lib/language-guard-backup`. That user is not the WSL lab user with uid 994.

## Do not reopen

Do not enable Cloud Sync, start the sync-backup timer, change `KEEP=14`, read `accounts.db`, read OAuth JSON, print a token or age identity, delete a lab file, or install the WSL units on the VPS. `app/offbox_poc.py` is not the uploader. The empty `socket-repair-r1/snapshot.age` stays empty.

## Next decision

Review the D5A2C1 report. The next decision is whether to accept that localhost transport and, separately, whether to approve one synthetic Drive upload. Those are two decisions. This handoff authorizes neither.
