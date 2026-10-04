"""Máy người học gọi server tài khoản. Không bao giờ nhận API key."""

import json
import urllib.error
import urllib.request

import config


class AccountError(RuntimeError):
    pass


class SessionExpired(AccountError):
    """Token còn lưu trên máy nhưng server không nhận."""


def _post(path: str, payload: dict, token: str = "", timeout: float = None) -> dict:
    url = config.ACCOUNT_SERVER_URL.rstrip("/") + path
    body = dict(payload)
    if token:
        body["token"] = token
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("User-Agent", "LanguageGuard")
    if token:
        request.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(request, timeout=timeout or config.OPENAI_TIMEOUT) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        try:
            message = json.loads(detail).get("error") or detail
        except json.JSONDecodeError:
            message = detail or str(error)
        if error.code == 401:
            config.clear_account()
            raise SessionExpired(str(message)) from error
        raise AccountError(str(message)) from error
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as error:
        raise AccountError(
            config.ui(
                "Không kết nối được máy chủ tài khoản.",
                "Couldn't reach the account server.",
            )
        ) from error
    if not isinstance(body, dict):
        raise AccountError("Máy chủ trả về dữ liệu lạ.")
    if body.get("error"):
        raise AccountError(str(body["error"]))
    return body


def session_still_valid() -> bool:
    """True nếu phiên còn dùng được hoặc server không trả lời.

    Token hết hạn thì xóa, để app hỏi đăng nhập lại thay vì kẹt ở thông báo lỗi.
    """
    if not config.account_token():
        return False
    try:
        _post("/api/grade", {}, config.account_token(), timeout=8)
    except SessionExpired:
        return False
    except AccountError:
        return True
    return True


def login(username: str, password: str) -> str:
    body = _post("/api/login", {"username": username, "password": password}, timeout=20)
    token = str(body.get("token") or "")
    if not token:
        raise AccountError("Máy chủ không cấp phiên đăng nhập.")
    return token


def grade_sentence(word: str, sentence: str, meaning: str) -> dict:
    profile = config.current_language()
    return _post(
        "/api/grade",
        {
            "word": word,
            "sentence": sentence,
            "meaning": meaning,
            "language": profile["code"],
            "native": config.native_code(),
            "level": config.READING_LEVEL,
        },
        config.account_token(),
    )


def generate_reading(entries: list) -> dict:
    profile = config.current_language()
    from vocabulary_model import wire_meaning_as_vi

    words = wire_meaning_as_vi(entries)
    return _post(
        "/api/reading",
        {
            "words": words,
            "language": profile["code"],
            "native": config.native_code(),
            "level": config.READING_LEVEL,
            "passage_words": config.READING_PASSAGE_WORDS,
        },
        config.account_token(),
    )


def enrich_vocabulary(
    word: str,
    meaning: str,
    part_of_speech: str = "",
    language_code: str = None,
    native_language: str = None,
) -> dict:
    """Request AI enrichment draft via account server. Never receives an API key."""
    profile = config.current_language()
    return _post(
        "/api/enrich",
        {
            "word": word,
            "meaning": meaning,
            "part_of_speech": part_of_speech or "",
            "language": language_code or profile["code"],
            "native": native_language or config.native_code(),
        },
        config.account_token(),
    )
