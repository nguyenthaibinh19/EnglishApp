# Local workspace policy

Status: active  
Date: 2026-11-23  
Tag: `APP_LOCAL_WORKSPACE_CONSOLIDATED`

The EnglishApp Git root is the main worktree, `D:\EnglishApp`. Disposable pilots live in `D:\EnglishApp\.local`. Reports and project documents live in `.ai/`. Production VPS backup directories are not part of this local workspace.

## Directory structure

| Path | Purpose |
|------|---------|
| `.local/clients/` | Isolated source clients. The active one is `clients/18c4p-r3`. |
| `.local/data/` | Disposable data roots. The active one is `data/18c4p-r3`. |
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
- The installed production EXE, the RC account, recovery backups, and Machine B data are outside `.local/` and are not cleanup targets.

## Machine A client

From a new terminal:

```text
LG_APP_ENVIRONMENT=production
LG_DATA_DIR=D:\EnglishApp\.local\data\18c4p-r3
ACCOUNT_SERVER_URL=https://langstudyguard.com
PYTHONPATH=D:\EnglishApp\.local\clients\18c4p-r3\app
```

Leave `LG_RC_SMOKE` unset. Set `OPENAI_API_KEY`, `EMERGENCY_PASSWORD`, and `ACCOUNT_TOKEN` to empty so a developer environment is not inherited. The saved synthetic session stays in the data directory.

```text
python D:\EnglishApp\.local\clients\18c4p-r3\app\main.py
```

Do not pass `--lock`. Do not run `prepare.py` as a script: it refuses to rebuild while the synthetic database exists. The window title should be `Language Guard — PRODUCTION`.

## Future work

1. Use the existing repository.
2. Put disposable artifacts in `.local/`.
3. Put reports and project documentation in `.ai/`.
4. Do not create a new root-level `D:\lg-*` directory without a written reason.
5. Do not keep duplicate clones and build directories.
6. Do not delete active test data or backups without checking dependencies and recovery.
7. Clean temporary artifacts when a phase closes.
