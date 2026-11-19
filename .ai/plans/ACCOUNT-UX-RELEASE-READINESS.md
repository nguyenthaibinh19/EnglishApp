# Account UX & Cross-Device Release Readiness

Status: **STOP for Architect review — R2** (`APP_ACCOUNT_UX_RC_R2_READY`). Implementation PR open; not merge-authorized until Accepted.

## Product Owner feedback addressed

- StudyMaster / FreeHome lacked Log in / Log out / Switch account → **Account panel** added.
- Guest mode was confusing → Guest / Not signed in + local-only explanation.
- Localhost-only testing cannot serve another PC → **Production Release Candidate** EXE prepared separately (HTTPS backend from production channel manifest).
- Full visual redesign deferred.

## Architect R1 corrections (this package)

| ID | Correction |
|----|------------|
| **F1** | Transactional `switch_account`: authenticate B first; cancel/invalid credentials keep A; commit B only after auth; stop A worker → commit B → start B → rebind views; pending-sync confirmation preserved; tokens never logged/dialoged. |
| **F2** | FreeHome + StudyMaster close Vocabulary / Progress / Mistake Book (and other account-bound children) before rebind; logout to Guest does not leave A's private windows open. |
| **F3** | Explicit RC smoke mode (`langstudyguard-rc.exe` / `--rc-smoke` / `LG_RC_SMOKE=1`) skips auto-install and Startup. Genuine `langstudyguard.exe` install unchanged. See [RC_SMOKE_PRODUCT_OWNER.md](../procedures/RC_SMOKE_PRODUCT_OWNER.md). |

## Acceptance scenarios

### Scenario A — Account isolation
Two accounts on one data root / profile: A vocabulary must not appear under B; returning to A restores local A state. Logout never deletes `accounts/{id}/` SQLite.

### Scenario B — Same-account synchronization
Same account on two temporary data roots against a synthetic localhost sync server: vocabulary uploaded on device 1 appears on device 2; offline write converges; no duplicate vocab ids. **Also:** learning attempts sync and drive derived Progress / SRS / Mistake Book on device 2.

Automated: `tests/test_account_ux_two_device.py` (+ install RC smoke regressions in `tests/test_install.py`).

## Screenshots (full windows)

`qa-evidence/account-ux-release/screenshots/`:

- `03_freehome_guest.png` / `04_freehome_signed_in.png`
- `05_studymaster_guest.png` / `06_studymaster_signed_in.png`

(Earlier `01_`/`02_` AccountPanel-only shots are supplementary; acceptance evidence is the full-window set.)

## Production Release Candidate

- Build: `build_production_rc.bat` → `dist-rc/langstudyguard-rc.exe`
- Channel: production (`build_manifest.json`)
- Must **not** overwrite `dist/langstudyguard.exe` / ZIP / backups
- Safe Owner path: [RC_SMOKE_PRODUCT_OWNER.md](../procedures/RC_SMOKE_PRODUCT_OWNER.md)
- No public GitHub Release until separate approval
- Clean-PC smoke: Owner runs RC on a second Windows PC without Python — document result when available; workspace cannot substitute an independent PC

## Remote sync pilot — PREPARATION ONLY

Production `STUDY_SYNC_ENABLED` remains **OFF**. This task does **not** enable it.

### Findings

| Item | Status |
|------|--------|
| Client Account Sync engine | Present in source (18C) |
| Server sync HTTP | Present in source; production deploy historically returns 404 when flag unset |
| Per-account allowlist / pilot gate | **Absent** — flag is global `STUDY_SYNC_ENABLED=1` only |
| Schema v3 progress tables | Client + server source; deployed server version must be verified before enable |
| Backup / restore scripts | Present; production backup timer posture must be verified before enable |
| GitHub merge updates VPS | **No** — deploy is a separate Owner-authorized step |

### GO / NO-GO

**NO-GO** for production Cloud Sync pilot until:

1. Explicit Owner authorization to enable sync on a controlled path.
2. Pilot restriction exists (allowlist or equivalent) — **currently missing → blocker**.
3. Deployed server SHA matches schema-v3 capable package; migration/rollback notes recorded.
4. Pre-enable accounts + study_sync backup verified.
5. Two-PC HTTPS pilot plan with synthetic/test accounts only (not live learners).
6. Reversible disable procedure (`STUDY_SYNC_ENABLED` unset + service restart) rehearsed in docs.

**Recommendation:** Keep Cloud Sync OFF. Ship Account UX + RC for login/AI usability first. Design an allowlist pilot gate before any VPS flag change.

## Status preserved

- ADR-025 Accepted
- 18C.1 / 18C.2 CLOSED
- 18B.9 PAUSED, NOT CLOSED
- Staging RESERVED
- Production Cloud Sync OFF
- Production sync pilot NO-GO
