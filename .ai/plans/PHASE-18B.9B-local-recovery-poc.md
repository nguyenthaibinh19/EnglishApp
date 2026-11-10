# Phase 18B.9B — Local recovery proof of concept

Status: **CLOSED — Leader Accepted, 2026-11-10.** Local synthetic proof only, commit `274156e`. Not a production uploader. The historical results below stay as written: the full suite was 30 passed and 1 skipped; the later wrong-password check passed; the full suite was not rerun after the final wording change.

## Production-reuse warning

**THIS MODULE IS A LOCAL SYNTHETIC RECOVERY POC, NOT A PRODUCTION BACKUP UPLOADER.**

The following controls are not implemented:

- `_child_env` inherits parent environment variables outside a short deny list. Production code must use an explicit minimal environment allowlist.
- `remove_private_tree` is unsafe for production cleanup because Windows junctions and other path aliases are not fully protected. That helper is not part of the accepted recovery execution path. Production cleanup requires a separately reviewed design.
- Synthetic accounts validation is not a real production accounts verifier.
- Symlink and junction protections are not fully verified.
- Local restic repository testing does not prove external storage security.
- B2 restricted permissions, Object Lock, retention, and recovery access remain unverified.

18B.9A is conditionally accepted. This draft corrects the earlier storage assumptions and records the local proof in `app/offbox_poc.py`. It does not choose a production RPO or RTO, does not purchase storage, and does not authorize a VPS change.

Phase 18B.8 stays closed. Cloud Sync stays off. The Windows Startup `--lock` hotfix stays deferred because that computer is unavailable. This proof document, as written, did not edit `.ai/current_state.md` or `.ai/roadmap.md`. A later memory sync recorded the closure there. The evidence below is unchanged.

## Corrected assumptions

- Backblaze B2 is the fallback storage candidate recorded by this local proof. It is not purchased and not approved for production. A later decision prefers the existing Google Drive allowance for pre-public copies. The later accepted remote architecture is a standalone age `.age` file. This local proof did not implement it. This proof did not upload anywhere.
- The production candidate, if later approved, uses restic through B2's **S3-compatible API**. This local proof does not open that API. Compatibility is untested.
- B2 append-only behavior is **not** a property of restic or of the repository password. A disposable local repository can delete a snapshot with `restic forget` when the caller has the password. That result is not evidence that a B2 key is append-only. A B2 key that cannot delete objects still has to be demonstrated before production.
- Four credentials have different jobs. They are not one shared secret.
  - **Repository password.** Encrypts and decrypts snapshot data. Loss makes the repository unreadable. It is not a B2 login.
  - **Upload credentials.** A limited B2/S3 key used only by the off-box job to write new packs and list what it needs. It must not be the account-server environment. Whether it can delete is unknown until a permission test.
  - **Restore credentials.** A read-only B2/S3 key plus the repository password. Enough to restore onto a new path. Not enough, by itself, to prune.
  - **Administrative credentials.** The B2 account or a full key, kept offline with the owner. Used to create the limited keys, rotate them, and run `forget` / `prune`. Not placed on the VPS.
- Object Lock stays off until a disposable bucket shows that restic backup, restore, check, forget, and prune behave as intended with that lock. Do not enable it on a repository that has not had that test.
- A 26-hour freshness window **cannot** tolerate one fully missed daily backup. A miss leaves the newest copy about 48 hours old. The local freshness function rejects a 48-hour-old timestamp when the caller supplies a 26-hour window. That window is a test knob, not an accepted RPO. The check did not read a restic repository.
- A 4-hour RTO remains an **unverified target**. This proof did not measure provisioning, owner availability, or a restore onto a new machine.

## What the local proof does

The proof uses temporary directories and synthetic SQLite files. It calls the existing online backup functions:

- `app/sync_backup.py` `backup_database` for the schema-v2 sync fixture.
- `deploy/hetzner/backup_accounts.py` `backup_file` for the synthetic accounts fixture.

It does not copy a live database with a raw file read as the backup step. The SQLite half was executed: both synthetic databases were published with the existing online-backup functions, the sync snapshot was restored to a new path, and the restored file passed `PRAGMA integrity_check`, schema version 2, the three required tables, and the synthetic vocabulary marker. The accounts snapshot passed the same integrity check and still had its synthetic marker. Source files and published snapshots were unchanged. Restore onto an existing destination was refused.

The restic half stores the inbox under its directory name. An absolute Windows path is not stored, because restoring one makes restic try to update timestamps on parent directories outside the destination.

A missing sync snapshot is `SKIPPED` only when the caller says the sync database has never existed and Cloud Sync is off. The report status is `ACCOUNTS_RESTORED_SYNC_SKIPPED`, `sync_restore_completed=false`, and `sync_restore=not_performed`. It is not `RESTORED`.

The proof refuses `s3:`, `b2:`, `sftp:`, and other non-local repository names before it starts a process.

## Security follow-up for a later production implementation

Not installed in this phase. No user, credential, timer, or service is created here.

### Collector and `lg-offbox`

- A privileged collector, running only as `ExecStartPre=+`, opens the newest regular `accounts-*.db` snapshot. It refuses a symlink, a directory, or a non-file. It does not change the snapshot mode and does not grant `guard` or `lg-offbox` access to `/var/backups/language-guard`.
- The collector copies bytes into a new directory under `/var/lib/language-guard-offbox/inbox-<id>/`, mode `0700`, file mode `0600`, owner `lg-offbox`. The copy uses an exclusive create. On Linux that open uses `O_NOFOLLOW`.
- If a regular `study-sync-*.db` exists, the collector copies that too. If it does not exist, and Cloud Sync is still off and `study_sync.db` has never existed, the sync input is `SKIPPED`. The accounts copy still runs. The result file must not call that skip a restore.
- If sync has existed, or Cloud Sync is on, a missing sync snapshot is a failure.
- The `lg-offbox` process is a different user from `guard` and from the account server. Its service has `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=strict`, and a write path limited to its state directory. It can read only the inbox the collector just created.
- `LoadCredential=` supplies the repository password and the upload key. Those files live in a root-owned `0400` directory that the account server reaches through `InaccessiblePaths`. They are not in `.env`, not in the `guard` process, and not in Git.
- The inbox directory is removed at the end of the job, and only when its path is inside the off-box state directory. A symlink is not deleted and not followed.
- Logs and the result file contain the snapshot file name, byte size, restic snapshot id, and a status word. They do not contain SQL, account rows, vocabulary, the repository password, or storage keys.

### Failure, freshness, and credentials

- A non-zero restic exit, an integrity failure, or a stale snapshot is a failed result. The health collector can read that result the same way it reads the sync-verify result. Provider acceptance is not success.
- Freshness uses the recovery objective the Leader has accepted. Until that exists, the production job must not invent one. The local checker only honors the window passed into the call.
- Losing the repository password makes every snapshot unreadable. There is no second copy of the data that bypasses it. The owner keeps the password offline before the first production backup.
- Losing the upload key does not make the data unreadable. The owner uses the administrative credential to create a replacement upload key.
- Losing the administrative credential does not, by itself, hide data that the restore key and the repository password can still read. It does block prune and key rotation until the account owner recovers the B2 account.
- Rotation of the repository password is `restic key add`, store the new password offline, update the VPS credential, then `restic key remove` for the old password. Upload-key rotation is a separate B2 action.

### B2 tests required before any production backup

These are questions, not results. This phase did not answer them.

- Does a bucket-scoped S3 key without `DeleteObject` still let restic finish `backup`, `snapshots`, and `restore`?
- Does that same key fail `forget` and `prune`?
- Does a separate read-only key restore without being able to upload or delete?
- Does Object Lock, or bucket versioning, break pack uploads or `restic check` on a disposable bucket?
- Which B2 region and S3 endpoint will be used?
- What is the current minimum charge, storage price, and download price? Earlier figures were not rechecked and are not a cost approval.

### Retention and integrity, unapproved

A later approval could use `restic forget --keep-daily 14 --keep-weekly 8 --keep-monthly 6`, then `prune`, run only with the administrative credential. The VPS upload key would not prune. A weekly `restic check` would use a read credential. On-VPS accounts retention stays 14 and is not changed by this draft. None of these numbers are accepted.

## Suggested future systemd shape

Sketch only. Do not install it from this draft.

- `language-guard-offbox.service`
  - `User=lg-offbox`
  - `Group=lg-offbox`
  - `ExecStartPre=+/usr/local/sbin/language-guard-offbox-collect`
  - `ExecStart=/opt/language-guard-offbox/offbox-backup`
  - `LoadCredential=` for the repository password and the upload key
  - `UMask=0077`
- `language-guard-offbox.timer` at a time after the accounts backup timer. The clock is not chosen here.
- A result file under the off-box state directory, readable by the health collector, with no secrets.
- The account server unit is not edited and is not restarted.
- The sync-backup timer stays disabled. `STUDY_SYNC_ENABLED` stays unset.

## RPO and RTO options, none accepted

| Option | What it would mean | What this proof showed |
|---|---|---|
| Daily copy and a 26-hour ceiling | One fully missed day leaves the newest copy about 48 hours old, which is already outside 26 hours | A 48-hour-old timestamp is stale against a supplied 26-hour window |
| Daily copy and a ceiling of about 50 hours | One missed daily run still leaves a copy inside the ceiling. Two misses do not | Not selected |
| Two copies a day and a 26-hour ceiling | One missed run can still leave the other copy inside 26 hours | Not selected |
| RTO of 4 hours | Target for a new machine after the owner starts recovery | Not measured. Still unverified |

The Leader chooses any production numbers in a later approval. This draft does not.

## Out of scope

No VPS access, no external bucket, no real credentials, no production database reads, no accounts-timer change, no sync-backup enablement, no Windows Startup work, and no Phase 18C work.
