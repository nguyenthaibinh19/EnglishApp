# Local workspace policy

Status: active  
Date: 2026-11-24  
Tag: `APP_LOCAL_MULTI_CLIENT_READY`

The EnglishApp Git root is the main worktree, `D:\EnglishApp`. Disposable pilots live in `D:\EnglishApp\.local`. Reports and project documents live in `.ai/`. Production VPS backup directories are not part of this local workspace.

## Directory structure

| Path | Purpose |
|------|---------|
| `.local/clients/` | Isolated source clients. The active one is `clients/18c4p-r3`. |
| `.local/data/` | Disposable data roots. Client A is `data/18c4p-r3`. Client B is `data/18c4p-r3-b`. |
| `.local/labs/` | Experiment scripts and synthetic labs. `labs/18c4p-r3` is the active launcher. `labs/18c4a` and `labs/18c4p-r1` are archival. |
| `.local/builds/` | Local build output. `builds/18c4p-r1-candidate` is archival and must not be installed. |
| `.local/payloads/` | Local deployment payloads. `payloads/18c4p-r2` is archival. |

`.local/INVENTORY.md` records the move and the retention of each artifact.

## What stays out of Git

The root `.gitignore` excludes `.local/`. Do not commit SQLite databases, session tokens, EXE candidates, deployment payloads, `settings.json`, or credentials. Do not copy the developer `.env` into a test client.

## Cleanup and relocation

- Reuse these folders. Do not create another `D:\lg-*` directory unless the Owner writes down why an existing folder cannot be used.
- Do not accumulate a second clone or build tree for the same phase.
- Move disposable artifacts inside `.local/` on the same drive. Do not move a Git worktree with a plain file move.
- Do not delete an active database, outbox, or backup until its dependencies and recovery copy are checked, and only with explicit approval.
- Remove temporary files when a phase closes. Keep active and archival artifacts listed in the inventory.
- The installed production EXE, the RC account, and recovery backups are outside `.local/` and are not cleanup targets. The physical second computer's files are also outside this workspace. Same-machine Client B data is `.local/data/18c4p-r3-b`.

## Same-machine clients

One shared source, two processes. This is not a second physical computer and not the localhost integration tests.

```text
python D:\EnglishApp\.local\labs\18c4p-r3\launch_client.py a
python D:\EnglishApp\.local\labs\18c4p-r3\launch_client.py b
python D:\EnglishApp\.local\labs\18c4p-r3\launch_client.py verify
```

Client A uses `.local\data\18c4p-r3`. Client B uses `.local\data\18c4p-r3-b`. Each process gets its own `LG_DATA_DIR`, settings, account database, session, and outbox. `device_id` is created inside that database the first time it opens. Do not copy Client A's database or `settings.json` into Client B. The launcher refuses a copied token or a byte-identical database.

Both processes use production identity and `https://langstudyguard.com`. They do not pass `--lock`. `PYTHONDONTWRITEBYTECODE=1` keeps the shared source from being a writable bytecode path. The sync worker global is per process. Source mode does not install an EXE or write the recovery folder.

The window on the left is Client A. The window on the right is Client B. Client B starts on the language screen. Choose Dutch as a study language, continue, then sign in as `syncpilot_18c4p`. Type the password only in that window.

Three evidence categories stay separate:

- Automated local integration tests use a temporary localhost server. They do not contact production.
- Same-machine production tests are these two processes against `https://langstudyguard.com`.
- Physical two-computer production tests require the Owner's other Windows PC. A same-machine result does not replace that record.

## Machine A client

The commands above are the supported launch. A manual shell uses the same variables: `LG_APP_ENVIRONMENT=production`, `LG_DATA_DIR` set to that client's data directory, `ACCOUNT_SERVER_URL=https://langstudyguard.com`, and `PYTHONPATH` set to the shared `app` directory. Leave `LG_RC_SMOKE` unset. Set `OPENAI_API_KEY`, `EMERGENCY_PASSWORD`, and `ACCOUNT_TOKEN` to empty so a developer environment is not inherited.

Do not run `prepare.py` as a script: it refuses to rebuild while Client A's synthetic database exists. After sign-in, the home window title is `langstudyguard`. Before sign-in, Client B shows `Language Guard — PRODUCTION`.

## Future work

1. Use the existing repository.
2. Put disposable artifacts in `.local/`.
3. Put reports and project documentation in `.ai/`.
4. Do not create a new root-level `D:\lg-*` directory without a written reason.
5. Do not keep duplicate clones and build directories.
6. Do not delete active test data or backups without checking dependencies and recovery.
7. Clean temporary artifacts when a phase closes.
