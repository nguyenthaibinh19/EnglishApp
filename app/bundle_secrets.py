"""Đọc EMERGENCY_PASSWORD từ .env và ghi bundled_secrets.json để đóng vào file .exe.

File kết quả không được commit. Mật khẩu chỉ nằm trong máy dev và trong bản build.

Staging builds refuse production account-server URLs (ADR-025).
"""

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


def _host(url: str) -> str:
    parsed = urlparse(url if "://" in url else "http://" + url)
    return (parsed.hostname or "").strip().lower()


def _is_production_host(host: str) -> bool:
    host = host.rstrip(".")
    if host in KNOWN_PRODUCTION_HOSTS:
        return True
    return host.endswith(".langstudyguard.com")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--channel",
        default="production",
        choices=("development", "staging", "production"),
    )
    args = parser.parse_args()

    values = dotenv_values(".env")
    password = (values.get("EMERGENCY_PASSWORD") or "").strip()
    if not password:
        print("Thieu EMERGENCY_PASSWORD trong .env")
        return 1
    payload = {"emergency_password": password}
    server = (values.get("ACCOUNT_SERVER_URL") or "").strip()
    if args.channel in ("staging", "development"):
        # Never embed a production URL into a non-production EXE. If .env points
        # at production (common on the owner machine), force localhost instead.
        forced = "http://127.0.0.1:8765"
        if server:
            host = _host(server)
            if _is_production_host(host):
                print(
                    f"CANH BAO: bo qua ACCOUNT_SERVER_URL production ({host}); "
                    f"channel={args.channel} dung {forced}"
                )
                payload["account_server_url"] = forced
            elif host not in {"127.0.0.1", "localhost", "::1"}:
                print(
                    f"CANH BAO: bo qua ACCOUNT_SERVER_URL khong tin cay ({host}); "
                    f"channel={args.channel} dung {forced}"
                )
                payload["account_server_url"] = forced
            else:
                payload["account_server_url"] = server
        else:
            payload["account_server_url"] = forced
    elif server:
        payload["account_server_url"] = server
    with open("bundled_secrets.json", "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    print(f"Da gan mat khau dev vao ban build (channel={args.channel}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
