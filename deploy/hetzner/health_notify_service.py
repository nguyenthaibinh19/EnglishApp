"""Notifier entry point. systemd passes the accepted socket as stdin.

This process is the only health process that reads provider credentials.
It sends one validated request and exits. It does not open a path from
the request, and it does not read accounts or backup files.
"""

from __future__ import annotations

import os
import socket
import sys

NOTIFIER_APP = "/opt/language-guard-notify/app"
GUARD_TREE = "/opt/language-guard"


def _trusted_import_dir() -> str:
    """Import only the directory that contains this file when it is trusted.

    Production execution uses ``python -I`` and inserts
    ``/opt/language-guard-notify/app`` before import. A copy under the
    guard-owned application tree must not run.
    """
    here = os.path.realpath(os.path.dirname(os.path.abspath(__file__)))
    if here == os.path.realpath(GUARD_TREE) or here.startswith(os.path.realpath(GUARD_TREE) + os.sep):
        raise SystemExit(1)
    return here


_trusted = _trusted_import_dir()
if _trusted == os.path.realpath(NOTIFIER_APP) and _trusted not in sys.path:
    sys.path.insert(0, _trusted)

import health_handoff  # noqa: E402
import health_notify  # noqa: E402


def _credential(name: str) -> str:
    directory = os.environ.get("CREDENTIALS_DIRECTORY") or ""
    if not directory:
        return ""
    path = os.path.join(directory, name)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError:
        return ""


def _senders() -> tuple:
    token = _credential("telegram.token")
    chat = _credential("telegram.chat")
    key = _credential("brevo.key")
    sender = _credential("brevo.sender")
    recipient = _credential("brevo.recipient")
    senders = {"telegram": None, "email": None}
    secrets = [value for value in (token, chat, key, sender, recipient, _credential("heartbeat.url")) if value]
    if token and chat:
        senders["telegram"] = health_notify.telegram_post(token, chat)
    if key and sender and recipient:
        senders["email"] = health_notify.brevo_post(key, sender, recipient, "Language Guard health")
    return senders, secrets


def _ping(url: str):
    if not url:
        return None

    def ping() -> bool:
        import urllib.request

        with urllib.request.urlopen(url, timeout=5) as response:
            return 200 <= getattr(response, "status", 200) < 300

    return ping


def main() -> int:
    here = os.path.realpath(os.path.dirname(os.path.abspath(__file__)))
    if os.environ.get("HEALTH_NOTIFIER_ALLOW_SOURCE") != "1":
        if here != os.path.realpath(NOTIFIER_APP):
            return 1
    senders, secrets = _senders()
    ledger = health_handoff.AttemptLedger(
        os.environ.get("HEALTH_NOTIFIER_STATE_PATH", "/var/lib/language-guard-notify/attempts.json")
    )
    connection = socket.socket(fileno=sys.stdin.fileno())
    try:
        health_handoff.serve_one(
            connection,
            senders,
            secrets,
            _ping(_credential("heartbeat.url")),
            ledger=ledger,
        )
    finally:
        try:
            connection.close()
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
