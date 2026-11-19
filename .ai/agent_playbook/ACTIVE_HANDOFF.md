# Active handoff

Rolling coordination checkpoint. See [current_state.md](../current_state.md), [roadmap.md](../roadmap.md), [ACCOUNT-UX-RELEASE-READINESS.md](../plans/ACCOUNT-UX-RELEASE-READINESS.md), and [ADR-025](../decisions/ADR-025-environment-identity-and-isolation.md).

## 1. Checkpoint metadata

- Written: 2026-11-19 (Account UX RC **R2** — Architect R1 F1–F3 corrections).
- **ADR-025 Accepted** (PR #22 merge `2da93c3`).
- **Account UX / Release Candidate** — PR #23 R2 package; tag `APP_ACCOUNT_UX_RC_R2_READY`; **STOP for Architect review** (do not merge/release/deploy until Accepted).
- **18C.1 / 18C.2 CLOSED**. **18B.9 PAUSED, NOT CLOSED**.
- Staging **RESERVED**. Production Cloud Sync **OFF**. Production sync pilot **NO-GO**.

## 2. Last results

- F1 transactional switch (A kept until B authenticates).
- F2 account-bound child windows closed on FreeHome + StudyMaster session change.
- F3 RC smoke mode (`langstudyguard-rc.exe` / `--rc-smoke` / `LG_RC_SMOKE=1`) — no install/Startup overwrite; see [RC_SMOKE_PRODUCT_OWNER.md](../procedures/RC_SMOKE_PRODUCT_OWNER.md).
- Scenario B extended: learning attempts → Progress / SRS / Mistake Book on device 2.
- Full-window FreeHome / StudyMaster Guest + Signed-in screenshots under `qa-evidence/account-ux-release/screenshots/`.
- Production `dist\langstudyguard.exe` not modified by RC rebuild.

## 3. Next

1. Architect review of PR #23 R2 — no merge until Accepted.
2. Owner may smoke-test RC on a clean PC per RC_SMOKE_PRODUCT_OWNER.
3. Do not enable `STUDY_SYNC_ENABLED` or start a new milestone from this handoff.
4. Resume 18B.9 only under new Owner authorization.

## 4. STOP / boundaries

- No VPS/SSH, production DB mutation, production sync flag, Drive/OAuth, public GitHub Release.
- Do not overwrite `D:\EnglishApp\dist\langstudyguard.exe` / `.zip` / `.bak`.
