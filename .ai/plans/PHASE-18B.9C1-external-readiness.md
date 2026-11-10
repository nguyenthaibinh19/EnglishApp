# Phase 18B.9C1 — External storage readiness

Status: **DESIGN ACCEPTED, 2026-11-10.** Planning only. Not a production deployment. Not a provisioned folder. Google Drive 5 TB is the preferred pre-public store. Backblaze B2 is the fallback. A standalone age `.age` artifact is the approved architecture. A pinned age version and a post-quantum hybrid recipient still require validation before implementation. The production encryption pipeline is not implemented. Phase 18B.9 remains **OPEN**. Phase 18B.9C2 is **NOT AUTHORIZED**. No remote backup has been run. No production uploader exists. No real user data upload is authorized.

Phase 18B.9B is **CLOSED — Leader Accepted, 2026-11-10**, commit `274156e`. That proof is local and synthetic. Its historical full suite was 30 passed and 1 skipped. A later wrong-password check passed, and the full suite was not rerun after that correction. Windows symlink handling was not verified. `app/offbox_poc.py` is not a production uploader and must not be installed as one. The local Restic proof does not produce a standalone encrypted file.

Cloud Sync stays OFF. The Windows Startup `--lock` hotfix stays **DEFERRED** until the affected computer is available. Website W1 is handled by Antigravity in a separate workspace.

## Preferred store

Google Drive is the preferred pre-public store. The owner already has 5 TB through Google AI Pro Student, so this choice adds no storage subscription while that allowance remains. No backup folder is provisioned. No file has been uploaded. The OAuth token does not exist in this repository and does not belong on the development machine.

The backup folder is private to a `drive.file` client created later by the owner. That scope can create and modify files that client created. It is not a view of the owner's other Drive files, and it is not an upload-only scope. `rclone copy` of one new filename is the transfer. `rclone sync` is not used.

## Fallback store

Backblaze B2 EU Central is the fallback. It is not provisioned. The account region is chosen at signup and cannot be moved later. EU Central is the Amsterdam site, a different company and city from the Hetzner VPS in Falkenstein. The owner copies the S3 endpoint from the bucket page. The endpoint published with that region is `s3.eu-central-003.backblazeb2.com`.

Restic 0.19.1 recommends B2's S3-compatible API rather than the native `b2:` backend. The repository URL would be `s3:s3.<region>.backblazeb2.com/<bucket>/language-guard`. The master application key does not work with that API.

The first bucket would be private and empty. Versioning stays at B2's default. **Object Lock stays off. A lifecycle rule that deletes hidden versions stays off.** Those choices are part of the proposed initial test, not a deployment.

## What is not assumed

B2 is not append-only. Restic's S3 backend hides files it no longer needs, and B2 keeps hidden versions unless a later lifecycle rule or a version delete removes them. A local `restic forget` does not prove a B2 permission. One application key has one prefix and one capability set. `writeFiles` is involved in deleting a file by name, and `deleteFiles` is involved in deleting a version. Whether a restricted key can finish a backup, including its lock, is untested.

A 26-hour RPO with a twice-daily backup, and a 4-hour RTO, are **proposals**. They are not accepted production guarantees. A single daily copy does not keep a 26-hour ceiling after one missed run.

## Credentials

The four duties below belong to the B2 fallback. The Google Drive recommendation is different: the backup host holds a public age recipient and an upload token, and the age identity stays offline.

Four separate duties, none of them created yet:

- The repository password stays with the owner, off the VPS, before any backup. Losing it makes the copies unreadable.
- An upload key would be limited to the bucket and prefix. It must not sit in the account-server environment.
- A restore key would list and read, and would stay on the recovery machine with the repository password.
- The Backblaze account login stays offline and is the only place that may later approve cleanup.

## Owner-only actions

The owner handles deletion. `restic forget`, `restic prune`, `restic unlock`, hiding a file, deleting a version, and turning on a deleting lifecycle are not agent procedures. A test that tries a delete in order to see it fail is also owner-controlled. Object Lock is not enabled. A compatibility trial for it would be a separate disposable bucket and a separate approval.

## Encryption format, design accepted

Approved architecture, not an installed pipeline: a standalone [age](https://github.com/FiloSottile/age) ciphertext of one integrity-checked SQLite snapshot. The extension is `.age`. A `.db.restic` name is not used. Restic 0.19.1 remains the accepted local repository proof. It does not by itself write one portable encrypted file.

Two shapes were compared.

Option A packs a whole Restic repository into one archive. `restic init` and `restic backup` write `config`, `keys`, `data`, `index`, and `snapshots`. A finished command removes the lock file it created. The archive is then a tar of that directory. Restore extracts it to a new directory and runs `restic restore`. `restic check` needs the repository password. The tar itself is not an authenticated envelope. The password can both encrypt and decrypt, so the backup host holds a key that can read the data. This shape conflicts with the zero-deletion rule because Restic removes its lock.

Option B encrypts the snapshot with age. The future commands, not run in this phase, are:

```text
age -r <public-recipient> -o <new-unique-name>.age <integrity-checked-snapshot.db>
age -d -i <identity-file> -o <new-restore-path.db> <artifact.age>
```

age exits 0 only when the whole input succeeds. The ciphertext is authenticated. Decryption releases no unauthenticated plaintext. A later `PRAGMA integrity_check` on the new database is still required. age does not delete the input file. `age-keygen -o` refuses to replace an existing identity file. `age -o` does replace an existing output, so the procedure uses a new name and stops when that name already exists. Official builds exist for Windows and Linux. No age binary is pinned or installed here. The current age manual recommends a post-quantum hybrid recipient from `age-keygen -pq` for most uses. The version and hash stay for a later approval.

The backup host receives only the public recipient. The identity file stays offline and on the recovery machine. The daily reporter receives neither the identity nor the OAuth refresh token.

A local snapshot can exist before encryption. Encryption can succeed before upload. A matching remote checksum can succeed before anyone decrypts the file. Only a restore onto a new path, followed by SQLite `integrity_check`, is a successful restore drill.

Migration copies the `.age` files to another provider. It does not depend on a Restic repository layout. A later move to a Restic repository on B2 remains possible and is a separate approval, because that move removes lock files.

## Monitoring, not installed

This is a Phase 18B.9 acceptance gate. The design is recorded in [HEALTH_MONITORING.md](../procedures/HEALTH_MONITORING.md). It is not wired into the running 09:00 report.

Before activation, Google Drive is **NOT CONFIGURED**. The report must not say SUCCESS. When the job is later active, the 09:00 Europe/Amsterdam report includes local VPS backup status, Google Drive status, the last attempt, the last successful remote backup, the age of the last valid backup, the remote artifact check, the last successful restore drill, and Cloud Sync. Cloud Sync stays OFF.

Critical failures alert through the existing Telegram and email incident path when they happen. They do not wait for 09:00. A separate Healthchecks.io check is the missed-job signal. The proposed 26-hour RPO is not the approved stale threshold.

## Not in this phase

No bucket, no key, no upload, no VPS change, no production database read, and no Cloud Sync change. The first external drill, if later authorized as 18B.9C2, would use synthetic data on a non-production machine and would restore into a new directory.
