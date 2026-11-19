# Phase 18C.1 — GUI integration boundary

Status: **18C.1 local core sync demonstration** (Architect review). Not production activation. Not full signed-in GUI integration (that is **18C.2**).

## Owner priority (official)

- **18C Account Data Sync — ACTIVE**
- **18B.9 Off-box Recovery — PAUSED, NOT CLOSED**
- Cloud Sync production remains **OFF**
- Security, quotas, off-box recovery, and operational gates remain required before public activation

## What 18C.1 actually wires in the Windows app

| Path | Uses account-local SQLite (`accounts/{user_id}/account_study.db`) | Uses machine-global guest files (`languages/{code}/`) |
|---|---|---|
| `setup_wizard` login → `maybe_start_account_sync()` | Starts background sync **engine** for the session | Does **not** copy guest vocab/progress/attempts into the account |
| `main` startup / `atexit` stop | Same engine lifecycle | Guest files unchanged |
| Vocabulary Manager / Word Detail (`vocabulary_app`, `VocabStore`) | **No** | **Yes** — `vocab.json` |
| Quiz / Study (`quiz_app`, `quiz_engine`, `Progress`, `AttemptHistory`) | **No** | **Yes** — `progress.json`, `attempts.jsonl` |
| Mistake Book / Progress views / Home / Library | **No** | **Yes** — guest aggregation |
| Localhost demo `tools/demo_18c1_account_sync.py` | **Yes** — direct `AccountLocalStore` + engine | Writes a guest file only to prove it is **not** uploaded |
| Sync HTTP client/engine | **Yes** — outbox/cursors against staging/server when flag is on | Never reads guest files for upload |

## Explicit non-claims

- Background bootstrap + the synthetic two-device demo are **not** complete end-to-end GUI account sync.
- Signed-in Tkinter study and vocabulary flows still read/write **guest** machine-global files.
- Login does **not** auto-import guest data into an account.
- Cross-device daily streak / account preferences / consent migration remain **18C.2**.

## 18C.2 roadmap (deferred)

- Wire signed-in Vocabulary + Quiz + Mistake Book + Progress UI to `AccountLocalStore`
- Account preferences and language settings for synced study
- Device-local day buckets / streak UX across devices (account-scoped, not guest `progress.json` days)
- Legacy consent import / replacement overlap from ADR-022
- Keep guest and account data from mixing; no silent guest upload
