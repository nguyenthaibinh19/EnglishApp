# Off-box monitoring and schedule templates

Status: **TEMPLATES ONLY — not installed, not enabled.**

## Schedule template

Unit file: `deploy/hetzner/language-guard-offbox.timer`

- Proposed `OnCalendar=*-*-* 05:15:00 UTC` with `RandomizedDelaySec=15m`.
- Targets `language-guard-offbox-worker.service`.
- RPO 26h / RTO 4h remain proposals until Product Owner acceptance.
- Stale alerting must not start until a threshold is separately approved.

## Monitoring line template

Helper: `deploy/hetzner/offbox_report_lines.py`

Closed phrases:

- `Google Drive: NOT CONFIGURED` (default and for fake/localhost evidence)
- `Google Drive: VERIFIED` only when `provenance.production_eligible` is true
- `Google Drive: FAILED` / `Google Drive: UNKNOWN`
- `Off-box last attempt: …`
- `Off-box restore drill: NOT RUN` / `RECORDED`
- `Cloud Sync: OFF`

Not wired into `health_report.py` yet. Fitting these into the closed notify socket (`check` / `report` / `backup-incident` / `recovery`, ≤12 lines, no free text) requires a later authorized monitoring wiring session.

## Healthchecks

A dedicated missed-job Healthchecks check is planned when a schedule is accepted. It must not reuse the 09:00 report heartbeat URL.
