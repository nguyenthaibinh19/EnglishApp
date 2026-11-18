# Off-box clean-host restore runbook

Status: **RUNBOOK ONLY — not executed.** No download, decrypt, or database replace is authorized here.

## Objective

Prove that one age ciphertext of an integrity-checked SQLite snapshot can be restored onto a clean replacement machine using the offline age identity.

## Prerequisites

- Offline age identity (never stored on the VPS).
- One designated ciphertext (lab synthetic first; production artifact only with explicit approval).
- age v1.3.2 capable of `age1pq1`.
- Python ≥ 3.10 with stdlib sqlite3.
- Empty destination path (never overwrite a live `accounts.db` in place).

## Procedure outline

1. On the clean host, place ciphertext at a new path (example: `/tmp/restore/snapshot.age`).
2. Decrypt with offline identity to a new SQLite path (example: `/tmp/restore/accounts.restored.db`).
3. Run `PRAGMA integrity_check` and confirm `ok`.
4. Optionally run the repository `restore_check` recorder against attempt metadata without uploading.
5. Record wall-clock duration for RTO evidence.
6. Delete temporary plaintext only under owner instruction; zero-deletion preference remains for evidence labs.

## Pass criteria

- Integrity check `ok`.
- Restored bytes are not written over production paths.
- No OAuth or Drive call required for the decrypt drill.
- Result is logged as a restore drill, which does **not** by itself create production `VERIFIED`.

## Non-goals

- Not a production cutover.
- Not authorization to enable timers or Cloud Sync.
- Not deletion of the synthetic Drive object.
