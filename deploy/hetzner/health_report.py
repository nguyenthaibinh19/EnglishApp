"""Run one health check or one daily report.

Exit 0 means the collector finished. It does not mean a provider accepted
the message, and provider acceptance does not mean a person received it.
A full VPS outage cannot send Telegram or email; external monitors cover that.

Provider secrets stay in the notifier process. This collector sends one
bounded request over the local socket and does not read credentials.
"""

from __future__ import annotations

import os
import sys

APP_DIR = "/opt/language-guard"
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
for _path in (os.path.join(_ROOT, "app"), _ROOT, APP_DIR):
    if os.path.isdir(_path) and _path not in sys.path:
        sys.path.insert(0, _path)

import health_handoff  # noqa: E402
import health_monitor  # noqa: E402


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args not in (["check"], ["report"]):
        sys.stderr.write("usage: health_report.py check|report\n")
        return 2
    mode = args[0]
    config = health_monitor.HealthConfig(
        state_path=os.environ.get("HEALTH_STATE_PATH", "/var/lib/language-guard/health-state.json"),
        witness_path=os.environ.get("HEALTH_WITNESS_PATH", "/var/lib/language-guard/study-sync-observed"),
        accounts_backup_dir=os.environ.get("ACCOUNTS_BACKUP_DIR", "/var/backups/language-guard"),
        accounts_live_db=os.environ.get("ACCOUNTS_LIVE_DB", "/opt/language-guard/accounts.db"),
        sync_live_db=os.environ.get("STUDY_SYNC_DB", "/opt/language-guard/study_sync.db"),
        sync_backup_dir=os.environ.get("STUDY_SYNC_BACKUP_DIR", "/var/backups/language-guard/study-sync"),
        systemd_dir=os.environ.get("SYSTEMD_UNIT_DIR", "/etc/systemd/system"),
        verify_result_path=os.environ.get(
            "HEALTH_VERIFY_RESULT_PATH",
            "/var/lib/language-guard-verify/result.json",
        ),
        rpo_hours=_rpo(os.environ.get("STUDY_SYNC_RPO_HOURS")),
    )
    socket_path = (os.environ.get("HEALTH_NOTIFY_SOCKET") or "").strip()
    transport = None
    if socket_path:
        def transport(channels, envelope, heartbeat):
            return health_handoff.transact(
                socket_path,
                channels,
                envelope["event"],
                envelope["lines"],
                heartbeat=heartbeat,
                report_date=envelope.get("report_date", ""),
            )

    result = health_monitor.run_health(
        mode,
        config,
        _probes(),
        {"telegram": None, "email": None},
        transport=transport,
    )
    sys.stdout.write(result.text + "\n")
    for line in result.logs:
        sys.stderr.write(line + "\n")
    return 0


def _rpo(value: str | None):
    text = (value or "").strip()
    if not text:
        return None
    return float(text)


def _probes() -> dict:
    return {
        "service": _service_state(),
        "public_health": _public_health(),
        "disk": _disk(),
        "flags": _flags(),
    }


def _service_state():
    return _systemctl_active("language-guard.service")


def _systemctl_active(unit: str):
    import shutil
    import subprocess

    if shutil.which("systemctl") is None:
        return None
    result = subprocess.run(
        ["systemctl", "is-active", unit],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    return (result.stdout or "").strip() or None


def _public_health():
    url = (os.environ.get("HEALTH_PUBLIC_URL") or "").strip()
    if not url:
        return None
    import urllib.request

    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            body = response.read().decode("utf-8", "replace")
    except Exception:
        return None
    if health_monitor.HEALTH_MESSAGE in body:
        return health_monitor.HEALTH_MESSAGE
    return "unexpected"


def _disk():
    path = os.environ.get("ACCOUNTS_BACKUP_DIR", "/var/backups/language-guard")
    try:
        usage = __import__("shutil").disk_usage(path)
    except OSError:
        return None
    return (usage.total, usage.used)


def _flags() -> list:
    readings = []
    env_path = os.environ.get("HEALTH_ENV_FILE", "/opt/language-guard/.env")
    readings.append(_env_flag(env_path))
    readings.append({"name": "process", "readable": True, "value": os.environ.get("STUDY_SYNC_ENABLED")})
    unit_dir = os.environ.get("SYSTEMD_UNIT_DIR", "/etc/systemd/system")
    readings.extend(_unit_flags(unit_dir))
    return readings


def _env_flag(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("STUDY_SYNC_ENABLED="):
                    return {"name": "env", "readable": True, "value": line.split("=", 1)[1].strip()}
    except OSError:
        return {"name": "env", "readable": False, "value": ""}
    return {"name": "env", "readable": True, "value": ""}


def _unit_flags(unit_dir: str) -> list:
    readings = [_assignment(os.path.join(unit_dir, "language-guard.service"), "unit")]
    dropin = os.path.join(unit_dir, "language-guard.service.d")
    if os.path.isdir(dropin):
        try:
            names = sorted(os.listdir(dropin))
        except OSError:
            return readings + [{"name": "dropin", "readable": False, "value": ""}]
        readings.extend(
            _assignment(os.path.join(dropin, name), "dropin")
            for name in names
            if name.endswith(".conf")
        )
    elif os.path.lexists(dropin):
        readings.append({"name": "dropin", "readable": False, "value": ""})
    return readings


def _assignment(path: str, name: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            value = ""
            for line in handle:
                stripped = line.strip()
                if "STUDY_SYNC_ENABLED=" not in stripped:
                    continue
                value = stripped.split("STUDY_SYNC_ENABLED=", 1)[1].split()[0].strip("\"'")
            return {"name": name, "readable": True, "value": value}
    except OSError:
        return {"name": name, "readable": False, "value": ""}


if __name__ == "__main__":
    raise SystemExit(main())
