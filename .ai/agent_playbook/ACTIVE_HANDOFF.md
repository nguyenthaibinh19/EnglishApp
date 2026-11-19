# Active handoff

Rolling coordination checkpoint. The detailed history remains in [current_state.md](../current_state.md), [roadmap.md](../roadmap.md), [Phase 18B.9 status](../plans/PHASE-18B.9-offbox-status.md), and [ADR-024](../decisions/ADR-024-offbox-age-drive.md). Do not treat a commit/merge as a live activation.

## 1. Checkpoint metadata

- Written: 2026-11-19.
- **PRODUCTION REUSE READINESS PACKAGE** prepared (source PR + runbook). Not activation.
- Baseline: `dc9ec43355f686f62842d0cddabf16ce05ca2d72`. Post-fix Gate A PASS + Gate B CONFIG PASS remain current VPS evidence.
- Historical pre-fix audit **UNSAFE**; D5A2D2/D5A2D3 **FAIL** preserved.

## 2. Last completed / accepted results

- Inactive install + post-fix audit/config (Issue #8) — accepted; VPS units inactive.
- Readiness inventory: age v1.3.2 / `age1pq1`, Drive adapter, D5A2C2 one-shot are **reusable as validated designs/artifacts**; production identity/OAuth/folder/binary install remain Owner actions.
- Source-only packager fix: installed-layout `verify`/`verify-deps` resolve `<root>/offbox` (frozen module bytes unchanged). See readiness PR.

## 3. Next App task

1. Architect review/merge of the production-reuse readiness source PR (packager path + tests + runbook/docs).
2. **OWNER ACTION REQUIRED** (separate authorizations): production age identity/recipient; durable OAuth + Drive folder; VPS binary/credential install; isolation execution; restore drill; monitoring; activation.
3. Canonical runbook: [OFFBOX_PRODUCTION_DEPLOYMENT_RUNBOOK.md](../procedures/OFFBOX_PRODUCTION_DEPLOYMENT_RUNBOOK.md).

## 4. STOP / boundaries

- No SSH/VPS, Google API, credential provisioning, isolation execution, or activation without new Owner approval.
- Phase 18B.9 **OPEN / PRODUCTION NOT READY**. Drive **NOT CONFIGURED**. Cloud Sync **OFF**. AI-M4 **NOT AUTHORIZED**.
