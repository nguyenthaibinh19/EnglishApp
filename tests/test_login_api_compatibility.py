"""Login / session API contract for RC Account UX clients.

Synthetic local account DB + localhost server only. No production traffic.
STUDY_SYNC_ENABLED stays OFF.
"""

from __future__ import annotations

import os
import socket
import threading
from http.server import ThreadingHTTPServer

import pytest

import account_client
import account_server
import account_store
import config
import sync_http


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


@pytest.fixture
def login_lab(tmp_path, monkeypatch):
    """Localhost account server with two synthetic users; sync flag unset."""
    monkeypatch.delenv("STUDY_SYNC_ENABLED", raising=False)
    monkeypatch.setenv("LG_APP_ENVIRONMENT", "development")
    server_dir = tmp_path / "accounts"
    server_dir.mkdir()

    original_db_path = account_store.db_path

    def lab_db_path(folder=None):
        root = folder or str(server_dir)
        return os.path.join(root, account_store.DB_FILE)

    monkeypatch.setattr(account_store, "db_path", lab_db_path)
    account_store.add_user("alice", "alice-secret")
    account_store.add_user("bob", "bob-secret")

    port = _free_port()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), account_server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    monkeypatch.setattr(config, "ACCOUNT_SERVER_URL", base)
    monkeypatch.setattr(config, "SETTINGS_FILE", str(tmp_path / "settings.json"))

    yield {
        "base": base,
        "accounts_dir": str(server_dir),
        "alice": "alice",
        "bob": "bob",
    }
    httpd.shutdown()
    httpd.server_close()
    monkeypatch.setattr(account_store, "db_path", original_db_path)


def test_existing_account_login_returns_stable_user_id(login_lab):
    token, user_id = account_client.login_session("alice", "alice-secret")
    assert token
    assert user_id >= 1
    body = account_client._post(
        "/api/login", {"username": "alice", "password": "alice-secret"}
    )
    assert set(body) >= {"token", "user_id", "username"}
    assert body["username"] == "alice"
    assert int(body["user_id"]) == user_id


def test_wrong_password_rejected(login_lab):
    with pytest.raises(account_client.AccountError):
        account_client.login_session("alice", "wrong-password")


def test_session_matches_login_user_id(login_lab):
    token, user_id = account_client.login_session("alice", "alice-secret")
    session = account_client._post("/api/session", {}, token)
    assert int(session["user_id"]) == user_id
    assert session["username"] == "alice"


def test_relogin_preserves_identity(login_lab):
    token1, user_id1 = account_client.login_session("alice", "alice-secret")
    token2, user_id2 = account_client.login_session("alice", "alice-secret")
    assert user_id1 == user_id2
    assert token1 != token2  # new session token each login


def test_two_accounts_remain_isolated(login_lab):
    _, alice_id = account_client.login_session("alice", "alice-secret")
    _, bob_id = account_client.login_session("bob", "bob-secret")
    assert alice_id != bob_id
    token_a, _ = account_client.login_session("alice", "alice-secret")
    session_a = account_client._post("/api/session", {}, token_a)
    assert session_a["username"] == "alice"
    assert int(session_a["user_id"]) == alice_id


def test_ordinary_grade_api_compatible_after_login(login_lab, monkeypatch):
    token, _ = account_client.login_session("alice", "alice-secret")
    monkeypatch.setattr(config, "account_token", lambda: token)
    # Grade without AI key may fail closed on missing key — exercise auth path.
    # A 401 would clear the account; any non-auth response proves token accepted.
    try:
        account_client._post(
            "/api/grade",
            {"word": "huis", "sentence": "Het huis is groot.", "meaning": "house"},
            token,
            timeout=5,
        )
    except account_client.AccountError as error:
        assert not isinstance(error, account_client.SessionExpired)
        message = str(error).lower()
        assert "đăng nhập" not in message or "hãy" not in message


def test_study_sync_remains_off(login_lab, monkeypatch):
    assert os.environ.get("STUDY_SYNC_ENABLED") != "1"
    assert sync_http.sync_enabled() is False
    token, _ = account_client.login_session("alice", "alice-secret")
    status, body = sync_http.handle_request(
        "/api/sync/vocabulary/changes",
        {"Authorization": f"Bearer {token}", "Content-Length": "2"},
        _Body(b"{}"),
    )
    assert status == 404
    assert body.get("error")


class _Body:
    def __init__(self, data: bytes):
        self._data = data
        self._pos = 0

    def read(self, n: int = -1):
        if n < 0:
            chunk = self._data[self._pos :]
            self._pos = len(self._data)
            return chunk
        chunk = self._data[self._pos : self._pos + n]
        self._pos += len(chunk)
        return chunk


def test_client_session_fallback_when_login_omits_user_id(login_lab, monkeypatch):
    """Older login shape {token} + modern /api/session still yields stable id."""
    real_post = account_client._post
    calls = {"login": 0}

    def patched(path, payload, token="", timeout=None):
        if path == "/api/login":
            calls["login"] += 1
            body = real_post(path, payload, token, timeout=timeout)
            return {"token": body["token"]}  # strip user_id/username
        return real_post(path, payload, token, timeout=timeout)

    monkeypatch.setattr(account_client, "_post", patched)
    token, user_id = account_client.login_session("alice", "alice-secret")
    assert token
    assert user_id >= 1
    assert calls["login"] == 1


def test_rc_login_banner_text_not_plain_production(monkeypatch):
    identity = type(
        "I",
        (),
        {
            "identity_error": "",
            "rc_smoke": True,
            "runtime_environment": "production",
            "display_title": lambda self, name="Language Guard": (
                f"{name} — PRODUCTION BACKEND · RC TEST DATA"
            ),
        },
    )()
    monkeypatch.setattr(config, "environment_identity", lambda: identity)
    import setup_wizard

    assert "RC TEST DATA" in setup_wizard._window_title()
    # Banner helper uses rc_smoke marker.
    texts = []

    class FakeLabel:
        def __init__(self, _parent, text="", **_kwargs):
            texts.append(text)

        def pack(self, **_kwargs):
            return None

    monkeypatch.setattr(setup_wizard.ttk, "Label", FakeLabel)
    setup_wizard._env_banner(object())
    assert texts and texts[0] == "PRODUCTION BACKEND · RC TEST DATA"
