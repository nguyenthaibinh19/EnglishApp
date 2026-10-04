# How to release (current repository reality)

Documented from existing files only. **No CI/CD pipeline is defined in this repo.**

## Build (developer machine)

```text
build_exe.bat
```

This installs/uses PyInstaller with `DutchGuard.spec` and produces:

```text
dist\langstudyguard.exe
dist\langstudyguard.zip
```

Prefer distributing the **zip** (fewer browser/SmartScreen rough edges than a bare `.exe`).

## Publish

1. Create a GitHub Release on the configured update repo (`UPDATE_REPO` in config).
2. Attach **`langstudyguard.zip`** (and optionally the exe).
3. Tag/version must be understandable by the in-app updater (`app/updater.py` reads GitHub Releases latest).

There is no automated GitHub Actions release workflow in-tree as of this writing.

## Server / account

- Account server runs separately (Hetzner); production OpenAI key lives in server `.env`, not in the desktop build.
- Manual VPS deploy/restart steps are **operator knowledge** — not automated in this repository. Do not invent a deploy script here if none exists.

## Known debt (current)

- **Unsigned** Windows binary → SmartScreen / “unknown publisher” warnings
- Zip-based distribution
- Manual release upload
- Manual VPS operations for the account server

## After release

- Smoke a downloaded zip on a clean Windows machine when possible.
- Confirm auto-update prompt still finds the new tag/asset.
- Do **not** ship `.ai/` as required runtime data.
