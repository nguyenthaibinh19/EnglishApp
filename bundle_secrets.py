"""Đọc EMERGENCY_PASSWORD từ .env và ghi bundled_secrets.json để đóng vào file .exe.

File kết quả không được commit. Mật khẩu chỉ nằm trong máy dev và trong bản build.
"""

import json
import sys

from dotenv import dotenv_values


def main():
    password = (dotenv_values(".env").get("EMERGENCY_PASSWORD") or "").strip()
    if not password:
        print("Thieu EMERGENCY_PASSWORD trong .env")
        return 1
    with open("bundled_secrets.json", "w", encoding="utf-8") as handle:
        json.dump({"emergency_password": password}, handle)
    print("Da gan mat khau dev vao ban build.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
