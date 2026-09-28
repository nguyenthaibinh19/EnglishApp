"""Máy người học gọi server tài khoản. Không bao giờ nhận API key."""

import json
import urllib.error
import urllib.request

import config


class AccountError(RuntimeError):
    pass


def _post(path: str, payload: dict, token: str = "") -> dict:
    url = config.ACCOUNT_SERVER_URL.rstrip("/") + path
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("User-Agent", "LanguageGuard")
    if token:
        request.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(request, timeout=config.OPENAI_TIMEOUT) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        try:
            message = json.loads(detail).get("error") or detail
        except json.JSONDecodeError:
            message = detail or str(error)
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


def login(username: str, password: str) -> str:
    body = _post("/api/login", {"username": username, "password": password})
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
    words = [{"word": item.get("word") or item.get("nl") or item.get("en") or "", "vi": item.get("vi") or ""} for item in entries]
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
