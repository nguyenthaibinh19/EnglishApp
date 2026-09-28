"""Server tài khoản. API key chỉ đọc từ .env trên máy dev, không gửi cho người học.

Chạy server:
    python account_server.py

Tạo tài khoản (tạm thời chỉ dev tạo, chưa có đăng ký):
    python account_server.py add ten_tai_khoan
    python account_server.py list
    python account_server.py disable ten_tai_khoan
"""

import json
import getpass
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import account_store
import ai_teacher
import config
import languages

# 0.0.0.0 khi chạy trên máy dev. Trên VPS, systemd đặt 127.0.0.1 để chỉ Caddy được vào.
HOST = (os.getenv("ACCOUNT_BIND") or "0.0.0.0").strip() or "0.0.0.0"
PORT = int(os.getenv("ACCOUNT_PORT") or "8765")
_MAX_BODY = 80_000


def _bearer(header: str) -> str:
    value = (header or "").strip()
    if value.lower().startswith("bearer "):
        return value[7:].strip()
    return ""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self._send(200, {"ok": True, "message": "Language Guard account server is running."})

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > _MAX_BODY:
            self._send(400, {"error": "Yêu cầu không hợp lệ."})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeError):
            self._send(400, {"error": "Yêu cầu không hợp lệ."})
            return
        if not isinstance(payload, dict):
            self._send(400, {"error": "Yêu cầu không hợp lệ."})
            return
        try:
            if self.path == "/api/login":
                token = account_store.login(str(payload.get("username") or ""), str(payload.get("password") or ""))
                self._send(200, {"token": token})
                return
            user = account_store.user_for_token(_bearer(self.headers.get("Authorization") or ""))
            if user is None:
                self._send(401, {"error": "Hãy đăng nhập lại."})
                return
            if self.path == "/api/grade":
                self._send(200, _grade(payload))
                return
            if self.path == "/api/reading":
                self._send(200, _reading(payload))
                return
            self._send(404, {"error": "Không có chức năng này."})
        except (ValueError, ai_teacher.AITeacherError) as error:
            self._send(400, {"error": str(error)})
        except Exception as error:
            self._send(500, {"error": f"Lỗi máy chủ: {error}"})

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, status: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _profile(payload: dict) -> dict:
    code = str(payload.get("language") or "").strip().lower()
    profile = dict(languages.get(code) or {})
    if not profile:
        raise ValueError("Ngôn ngữ không được hỗ trợ.")
    profile["code"] = code
    return profile


def _native_label(payload: dict) -> str:
    return "English" if str(payload.get("native") or "").lower() == "en" else "Tiếng Việt"


def _grade(payload: dict) -> dict:
    return ai_teacher.check_sentence(
        str(payload.get("word") or ""),
        str(payload.get("sentence") or ""),
        str(payload.get("meaning") or ""),
        profile=_profile(payload),
        native_label=_native_label(payload),
        level=str(payload.get("level") or config.READING_LEVEL),
    )


def _reading(payload: dict) -> dict:
    words = payload.get("words") or []
    if not isinstance(words, list) or len(words) > 30:
        raise ValueError("Danh sách từ không hợp lệ.")
    entries = []
    for item in words:
        if isinstance(item, dict):
            entries.append({"word": str(item.get("word") or ""), "vi": str(item.get("vi") or "")})
    return ai_teacher.generate_reading(
        entries,
        level=str(payload.get("level") or config.READING_LEVEL),
        passage_words=int(payload.get("passage_words") or config.READING_PASSAGE_WORDS),
        profile=_profile(payload),
        native_label=_native_label(payload),
    )


def serve():
    if not config.looks_like_api_key(config.OPENAI_API_KEY):
        print("Can OPENAI_API_KEY trong .env tren may dev. Key khong dua cho nguoi hoc.")
        return 1
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Account server: http://127.0.0.1:{PORT}")
    if HOST in ("127.0.0.1", "localhost", "::1"):
        print("Chi nghe noi bo. Nguoi hoc vao qua HTTPS.")
    else:
        print("Cua so nay giu server chay. Dung go lenh o day.")
        print("Mo mot terminal khac roi chay: python account_server.py add ten_tai_khoan")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    return 0


def _add():
    if len(sys.argv) < 3:
        print("Dung: python account_server.py add ten_tai_khoan")
        return 1
    username = sys.argv[2]
    first = getpass.getpass("Mat khau: ")
    second = getpass.getpass("Nhap lai mat khau: ")
    if first != second:
        print("Hai lan nhap khong giong nhau.")
        return 1
    try:
        account_store.add_user(username, first)
    except ValueError as error:
        print(error)
        return 1
    print(f"Da tao tai khoan {username.strip().lower()}.")
    return 0


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else "serve"
    if command == "add":
        return _add()
    if command == "list":
        for user in account_store.list_users():
            state = "dang mo" if user["active"] else "da khoa"
            print(f"{user['username']}\t{state}\t{user['created_at']}")
        return 0
    if command == "disable":
        if len(sys.argv) < 3:
            print("Dung: python account_server.py disable ten_tai_khoan")
            return 1
        try:
            account_store.set_active(sys.argv[2], False)
        except ValueError as error:
            print(error)
            return 1
        print("Da khoa tai khoan.")
        return 0
    if command == "serve":
        return serve()
    print("Lenh: serve, add, list, disable")
    return 1


if __name__ == "__main__":
    sys.exit(main())
