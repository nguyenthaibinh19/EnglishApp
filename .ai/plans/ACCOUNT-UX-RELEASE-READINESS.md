# Account UX & Cross-Device Release Readiness

Status: **Architect Accepted — source merged** (`APP_ACCOUNT_UX_RC_MERGED_ACCEPTED`).

| Field | Value |
|-------|--------|
| PR | [#23](https://github.com/nguyenthaibinh19/EnglishApp/pull/23) |
| Approved source HEAD | `3d44bb50ffe1e37344671560e8958857028f7cc5` |
| Merge commit | `a08a9e09f20b5329a2f864381ac888783f6c0642` |
| Verdict | Architect Accepted (source merge only) |

## Product Owner feedback addressed

- StudyMaster / FreeHome lacked Log in / Log out / Switch account → **Account panel** added.
- Guest mode was confusing → Guest / Not signed in + local-only explanation.
- Localhost-only testing cannot serve another PC → **Production Release Candidate** EXE with isolated RC data + production HTTPS backend.
- Full visual redesign deferred.

## Architect corrections (accepted)

| ID | Status |
|----|--------|
| **F1** | **Accepted** — transactional `switch_account` (A kept until B authenticates). |
| **F2** | **Accepted** — FreeHome + StudyMaster close account-bound windows before rebind. |
| **F3** | **Accepted** — RC smoke uses `%APPDATA%\langstudyguard-rc`; refuses production data-root; no prod token adoption; no auto-updater; title **PRODUCTION BACKEND · RC TEST DATA**. Genuine `langstudyguard.exe` unchanged. See [RC_SMOKE_PRODUCT_OWNER.md](../procedures/RC_SMOKE_PRODUCT_OWNER.md). |

## Acceptance scenarios

### Scenario A — Account isolation
Two accounts on one data root: A vocabulary must not appear under B; returning to A restores local A state. Logout never deletes `accounts/{id}/` SQLite.

### Scenario B — Same-account synchronization
Same account on two temporary data roots: vocabulary + learning attempts → Progress / SRS / Mistake Book on device 2.

Automated: `tests/test_account_ux_two_device.py`, `tests/test_rc_smoke_isolation.py`, `tests/test_install.py`.

## Screenshots (full windows)

`qa-evidence/account-ux-release/screenshots/`: `03`–`06` FreeHome / StudyMaster Guest + Signed-in.

## Production Release Candidate (Owner test only)

- Build: `build_production_rc.bat` → `dist-rc/langstudyguard-rc.exe`
- Data: `%APPDATA%\langstudyguard-rc` (isolated)
- Channel: production backend; RC settings marker `production-rc`
- **Not** a public GitHub Release; **not** an automatic production install
- Safe Owner path: [RC_SMOKE_PRODUCT_OWNER.md](../procedures/RC_SMOKE_PRODUCT_OWNER.md)

## Remote sync pilot — PREPARATION ONLY

Production `STUDY_SYNC_ENABLED` remains **OFF**. **NO-GO** until allowlist + Owner auth.

## Status preserved

- ADR-025 Accepted
- 18C.1 / 18C.2 CLOSED
- 18B.9 PAUSED, NOT CLOSED
- Staging RESERVED
- Production Cloud Sync OFF
- Production sync pilot NO-GO
