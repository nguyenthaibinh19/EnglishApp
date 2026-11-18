# Off-box VPS prerequisite checklist (read-only)

Status: **TEMPLATE — not executed.** No SSH or VPS change is authorized by this file.
Phase 18B.9 remains OPEN. Google Drive remains **NOT CONFIGURED**. Cloud Sync remains **OFF**.

Use during a separately authorized read-only VPS probe. Record answers; do not invent them.

## Identity and paths (expected today)

| Check | Expected / note |
|---|---|
| `id lg-backup` | uid 994, gid 977 (D5A1); confirm before copying unit env |
| `id guard` | uid 995, gid 982 historically; confirm |
| `/var/lib/language-guard-backup` | exists, `lg-backup:lg-backup`, mode `0700`, empty of production ciphertext until activation |
| `/var/lib/language-guard-helper` | **Absent** today; later create `guard:guard` `0700` under a write-approved session |
| `/opt/language-guard/offbox/` | Absent until an authorized packaging install |
| `/etc/systemd/system/language-guard-offbox*` | Must remain absent until authorized unit install |
| age binary | Not on VPS; planned `/usr/local/lib/language-guard-age/age` v1.3.2 |
| `/etc/language-guard/age-recipient` | Absent; public recipient only when owner provides it |
| `/etc/language-guard/oauth-refresh` | Absent; production token not created by packaging |

## Read-only commands (authorized session only)

```bash
# Python used by the app venv
/opt/language-guard/venv/bin/python -V

# accounts.db journal mode (read-only pragma; does not start backup)
/opt/language-guard/venv/bin/python - <<'PY'
import sqlite3
db="/opt/language-guard/accounts.db"
con=sqlite3.connect(f"file:{db}?mode=ro", uri=True)
print(con.execute("PRAGMA journal_mode").fetchone())
con.close()
PY

# Confirm backup dir ownership without writing
stat -c '%U:%G %a %n' /var/lib/language-guard-backup
# Confirm offbox units are not installed/enabled
systemctl list-unit-files 'language-guard-offbox*' || true
systemctl is-enabled language-guard-offbox.timer 2>/dev/null || echo 'timer-absent-or-disabled'
```

## Pass criteria for this checklist

1. Python version ≥ 3.10 recorded.
2. Journal mode recorded (`wal`, `delete`, or other) without changing it.
3. `lg-backup` uid/gid recorded and matched to unit templates before install.
4. No offbox unit enabled; no Drive credentials present.
5. Historical D5A2D2/D5A2D3 FAIL evidence is not rewritten by this probe.
