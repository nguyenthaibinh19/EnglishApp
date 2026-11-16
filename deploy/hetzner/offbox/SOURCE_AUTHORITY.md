# Off-box source authority (D5A2D0-P1)

This directory is a **byte-preserving source archive** for future packaging review. It is **not** a deployment, not an enabled service, and not production activation.

## Authority

- Selected byte-level authority: `D:\Tools\age-c2d5a2c1r1-http-20261116T1303Z-b4e81c20\offbox\`
- Inventory: `.ai/plans/PHASE-18B.9D5A2D0-canonical-source-inventory.md`
- The fifteen Python modules here match that accepted D5A2D0 inventory SHA-256 list.
- D5A2C2-P1 `offbox/` was previously verified bitwise-identical to C1R1; P1 was not chosen merely because it was newer.
- Import milestone: Phase 18B.9D5A2D0-P1 on branch `phase18b9/d5a2d0-p1-source-import`.

## What this is not

- Not installed on the VPS.
- No accepted production systemd unit set is included.
- No production OAuth credentials, refresh tokens, access tokens, age private identities, or Google Drive folder IDs are included.
- `fake_drive.py`, `loopback_drive.py`, and `live_synthetic_once.py` are intentionally absent.
- Production readiness remains **NOT READY**.
- Google Drive production remains **NOT CONFIGURED**.
- Cloud Sync remains **OFF**.

## Verification

See `SHA256SUMS` in this directory for the exact fifteen relative paths and hashes.
