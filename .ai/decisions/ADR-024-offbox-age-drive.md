# ADR-024 Off-box age artifact and Google Drive adapter

Status: **Accepted as the local architecture through Phase 18B.9D5A2C1, 2026-11-16.** D5A2C1 is a localhost milestone. This is not a production deployment. The live Google synthetic test is not authorized. Phase 18B.9C2 is not authorized.

The 2026-11-10 design in [PHASE-18B.9C1-external-readiness.md](../plans/PHASE-18B.9C1-external-readiness.md) chose a standalone age `.age` artifact. This decision records the implementation that followed. It replaces that plan's `rclone copy` transfer. It does not replace the choice of Google Drive as the preferred store or Backblaze B2 as the unprovisioned fallback.

## Decision

- One backup object is an age ciphertext of one integrity-checked SQLite snapshot. The backup host holds the public recipient. The identity stays offline.
- The validated lab binary is age v1.3.2 for Linux amd64. The recipient type is the built-in post-quantum hybrid `age1pq1`. A separate age plugin is not required and was not installed.
- Google Drive is reached through the Drive API with scope `https://www.googleapis.com/auth/drive.file`. The client reserves one file id, uploads, then downloads that same id. `rclone` is not the transfer.
- `VERIFIED` requires the SHA-256 of the downloaded ciphertext to match the local ciphertext. An HTTP success, a filename, upload status, or metadata checksum is not enough. A restore drill is a separate check and does not create `VERIFIED`.
- Local frame verification, local encryption, a downloaded-ciphertext match, a synthetic restore, and a future owner-controlled production drill are different results. A fake or localhost transport cannot satisfy a production retention, recovery, monitoring, or freshness gate.
- After an ambiguous upload the same reserved file id is kept. A second file is not created. `DELETE`, `PATCH`, copy, trash, and metadata update are not part of this adapter.
- The refresh token is root-owned and reaches only the backup worker through `LoadCredential`. The helper does not receive it. Tokens and resumable session URIs are not written to logs or attempt manifests. A session URI may exist only in the private progress file of that attempt.
- WSL lab users are not the VPS `lg-backup` user. Creating the VPS user and the empty backup directory does not activate a schedule.

## Consequences

Phase 18B.9 stays open. Google Drive remains **NOT CONFIGURED** in the daily report. The D5A2C1 localhost transport is accepted, including the R1 corrections, and its source is outside this repository. Its live-test script is not authorized to run. No production age identity, OAuth client, or Drive folder is created by this decision.

See [PHASE-18B.9-offbox-status.md](../plans/PHASE-18B.9-offbox-status.md).
