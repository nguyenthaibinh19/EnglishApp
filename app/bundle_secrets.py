"""Write bundled_secrets.json for an EXE build.

The file may contain the account-server URL. It must not contain an emergency
password, an API key, a session token, or any other value from the developer
environment. The result is not committed.
"""

from __future__ import annotations

import argparse
import json
import sys
from urllib.parse import urlparse

from dotenv import dotenv_values

KNOWN_PRODUCTION_HOSTS = {
    "langstudyguard.com",
    "www.langstudyguard.com",
    "api.langstudyguard.com",
    "account.langstudyguard.com",
}

ALLOWED_KEYS = frozenset({"account_server_url"})


def _host(url: str) -> str:
    parsed = urlparse(url if "://" in url else "http://" + url)
    return (parsed.hostname or "").strip().lower()


def _is_production_host(host: str) -> bool:
    host = host.rstrip(".")
    if host in KNOWN_PRODUCTION_HOSTS:
        return True
    return host.endswith(".langstudyguard.com")


def release_payload(values: dict, channel: str) -> dict:
    """Build the non-secret release document from environment values."""
    payload = {}
    server = str((values or {}).get("ACCOUNT_SERVER_URL") or "").strip()
    if channel in ("staging", "development"):
        forced = "http://127.0.0.1:8765"
        if server:
            host = _host(server)
            if _is_production_host(host) or host not in {"127.0.0.1", "localhost", "::1"}:
                print(
                    f"CANH BAO: bo qua ACCOUNT_SERVER_URL ({host}); "
                    f"channel={channel} dung {forced}"
                )
                payload["account_server_url"] = forced
            else:
                payload["account_server_url"] = server
        else:
            payload["account_server_url"] = forced
    elif server:
        payload["account_server_url"] = server
    assert_release_config(payload)
    return payload


def assert_release_config(payload: dict) -> None:
    """Reject any key other than the account-server URL."""
    if not isinstance(payload, dict):
        raise ValueError("release configuration must be an object")
    extra = set(payload) - ALLOWED_KEYS
    if extra:
        raise ValueError("release configuration contains a forbidden key")
    url = payload.get("account_server_url", "")
    if url and not isinstance(url, str):
        raise ValueError("account server URL must be text")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--channel",
        default="production",
        choices=("development", "staging", "production"),
    )
    parser.add_argument("--output", default="bundled_secrets.json")
    args = parser.parse_args(argv)

    values = dotenv_values(".env")
    try:
        payload = release_payload(values, args.channel)
    except ValueError as error:
        print(str(error))
        return 1
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
        handle.write("\n")
    print(f"Da ghi cau hinh phat hanh, khong co mat khau khan cap (channel={args.channel}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
