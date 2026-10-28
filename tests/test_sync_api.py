"""Phase 18B.1 — authenticated vocabulary sync HTTP (local only)."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

import account_server
import account_store
import sync_http
import sync_store

VOCAB_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
VOCAB_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


def _payload(vocab_id: str = VOCAB_A, meaning: str = "house") -> dict:
    return {"id": vocab_id, "word": "huis", "meaning": meaning}


def _put_body(**overrides) -> dict:
    body = {
        "language_code": "nl",
        "vocab_id": VOCAB_A,
        "payload": _payload(),
        "expected_revision": 0,
        "operation_id": "op-create",
    }
    body.update(overrides)
    return body


class _Api:
    def __init__(self, port: int, folder: Path, token: str, user_id: int):
        self.port = port
        self.folder = folder
        self.token = token
        self.user_id = user_id

    def post(self, path: str, payload=None, *, auth=None, raw: bytes = None, use_auth: bool = True):
        import urllib.error
        import urllib.request

        if raw is None:
            data = json.dumps(payload if payload is not None else {}).encode("utf-8")
        else:
            data = raw
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=data,
            method="POST",
        )
        request.add_header("Content-Type", "application/json")
        if use_auth:
            header = self.token if auth is None else auth
            if header:
                request.add_header("Authorization", "Bearer " + header)
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            text = error.read().decode("utf-8")
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = {"_raw": text}
            return error.code, parsed

    def sync_db(self) -> Path:
        return self.folder / "study_sync.db"


def _use_tmp_accounts(monkeypatch, folder: Path) -> None:
    """Test-only override. Production login never passes a folder."""

    def db_path(explicit=None):
        root = explicit or str(folder)
        return os.path.join(root, account_store.DB_FILE)

    monkeypatch.setattr(account_store, "db_path", db_path)


@pytest.fixture
def api(tmp_path, monkeypatch):
    _use_tmp_accounts(monkeypatch, tmp_path)
    monkeypatch.delenv("STUDY_SYNC_ENABLED", raising=False)
    monkeypatch.setenv("STUDY_SYNC_DIR", str(tmp_path))
    account_store.add_user("learner", "secret1")
    token = account_store.login("learner", "secret1")
    user = account_store.user_for_token(token)
    server = ThreadingHTTPServer(("127.0.0.1", 0), account_server.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = _Api(server.server_address[1], tmp_path, token, int(user["id"]))
    try:
        yield client
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _enable(monkeypatch):
    monkeypatch.setenv("STUDY_SYNC_ENABLED", "1")


def _entity_rows(folder: Path):
    connection = sqlite3.connect(str(folder / "study_sync.db"))
    try:
        return connection.execute(
            "SELECT user_id, language_code, vocab_id, revision, deleted, payload_json "
            "FROM vocabulary_entities ORDER BY user_id, vocab_id"
        ).fetchall()
    finally:
        connection.close()


def _change_count(folder: Path) -> int:
    connection = sqlite3.connect(str(folder / "study_sync.db"))
    try:
        return int(
            connection.execute("SELECT COUNT(*) FROM vocabulary_changes").fetchone()[0]
        )
    finally:
        connection.close()


def test_disabled_flag_does_not_create_sync_db(api, monkeypatch):
    app_sync = Path(sync_store.db_path())
    existed = app_sync.exists()
    opened = []

    def forbid(path):
        opened.append(path)
        raise sqlite3.OperationalError("should-not-open")

    monkeypatch.setattr(sync_store, "connect", forbid)
    status, body = api.post("/api/sync/vocabulary/put", _put_body())
    assert status == 404
    assert body["error"] == "Không có chức năng này."
    assert opened == []
    assert not api.sync_db().exists()

    monkeypatch.setenv("STUDY_SYNC_ENABLED", "true")
    status, _body = api.post("/api/sync/vocabulary/put", _put_body())
    assert status == 404
    assert opened == []
    assert not api.sync_db().exists()
    assert app_sync.exists() == existed


def test_missing_invalid_expired_and_disabled_account_tokens(api, monkeypatch, tmp_path):
    _enable(monkeypatch)
    opened = []

    def forbid(path):
        opened.append(path)
        raise AssertionError("sync db should stay closed")

    monkeypatch.setattr(sync_store, "connect", forbid)

    missing, missing_body = api.post(
        "/api/sync/vocabulary/put",
        _put_body(token=api.token),
        use_auth=False,
    )
    assert missing == 401
    assert missing_body["error"] == "Authentication required."

    invalid, _invalid_body = api.post(
        "/api/sync/vocabulary/put", _put_body(), auth="not-a-real-token"
    )
    assert invalid == 401

    connection = sqlite3.connect(str(tmp_path / "accounts.db"))
    connection.execute("UPDATE sessions SET expires_at = 1")
    connection.commit()
    connection.close()
    expired, _expired_body = api.post("/api/sync/vocabulary/put", _put_body())
    assert expired == 401

    account_store.login("learner", "secret1")
    fresh = account_store.login("learner", "secret1")
    connection = sqlite3.connect(str(tmp_path / "accounts.db"))
    connection.execute("UPDATE users SET active = 0 WHERE username = 'learner'")
    connection.commit()
    connection.close()
    disabled, _disabled_body = api.post(
        "/api/sync/vocabulary/put", _put_body(), auth=fresh
    )
    assert disabled == 401
    assert opened == []
    assert not api.sync_db().exists()


def test_authenticated_create_update_delete(api, monkeypatch):
    _enable(monkeypatch)
    created, created_body = api.post("/api/sync/vocabulary/put", _put_body())
    assert created == 200
    assert created_body["revision"] == 1
    assert created_body["deleted"] is False
    assert created_body["expected_revision"] == 0
    assert "user_id" not in created_body

    updated, updated_body = api.post(
        "/api/sync/vocabulary/put",
        _put_body(
            payload=_payload(meaning="home"),
            expected_revision=1,
            operation_id="op-update",
        ),
    )
    assert updated == 200
    assert updated_body["revision"] == 2
    assert updated_body["payload"]["meaning"] == "home"
    assert updated_body["expected_revision"] == 1

    deleted, deleted_body = api.post(
        "/api/sync/vocabulary/delete",
        {
            "language_code": "nl",
            "vocab_id": VOCAB_A,
            "expected_revision": 2,
            "operation_id": "op-delete",
        },
    )
    assert deleted == 200
    assert deleted_body["deleted"] is True
    assert deleted_body["revision"] == 3
    assert deleted_body["expected_revision"] == 2
    assert _entity_rows(api.folder)[0][0] == api.user_id


def test_cross_account_isolation(api, monkeypatch, tmp_path):
    _enable(monkeypatch)
    status, _body = api.post("/api/sync/vocabulary/put", _put_body())
    assert status == 200

    account_store.add_user("other", "secret2")
    other_token = account_store.login("other", "secret2")
    other = account_store.user_for_token(other_token)
    other_id = int(other["id"])
    assert other_id != api.user_id

    page, page_body = api.post(
        "/api/sync/vocabulary/changes",
        {"after_cursor": 0, "limit": 50},
        auth=other_token,
    )
    assert page == 200
    assert page_body["changes"] == []

    copied, copied_body = api.post(
        "/api/sync/vocabulary/put",
        _put_body(operation_id="op-other"),
        auth=other_token,
    )
    assert copied == 200
    assert copied_body["revision"] == 1
    rows = _entity_rows(api.folder)
    assert [row[0] for row in rows] == [api.user_id, other_id]
    assert all(row[2] == VOCAB_A for row in rows)


def test_payload_user_id_is_ignored(api, monkeypatch):
    _enable(monkeypatch)
    status, body = api.post(
        "/api/sync/vocabulary/put",
        _put_body(user_id=999999),
    )
    assert status == 200
    assert "user_id" not in body
    rows = _entity_rows(api.folder)
    assert len(rows) == 1
    assert rows[0][0] == api.user_id
    assert rows[0][0] != 999999


def test_stale_revision_conflicts_without_mutation(api, monkeypatch):
    _enable(monkeypatch)
    assert api.post("/api/sync/vocabulary/put", _put_body())[0] == 200
    before = _entity_rows(api.folder)
    before_changes = _change_count(api.folder)

    status, body = api.post(
        "/api/sync/vocabulary/put",
        _put_body(
            payload=_payload(meaning="stale"),
            expected_revision=4,
            operation_id="op-stale",
        ),
    )
    assert status == 409
    assert body["error"] == "Sync conflict."
    assert body["current"]["revision"] == 1
    assert "Stale" not in json.dumps(body)
    assert _entity_rows(api.folder) == before
    assert _change_count(api.folder) == before_changes


def test_matching_operation_retry_is_idempotent(api, monkeypatch):
    _enable(monkeypatch)
    first_status, first = api.post("/api/sync/vocabulary/put", _put_body())
    second_status, second = api.post("/api/sync/vocabulary/put", _put_body())
    assert first_status == 200
    assert second_status == 200
    assert second["revision"] == first["revision"] == 1
    assert second["change_cursor"] == first["change_cursor"]
    assert _change_count(api.folder) == 1


def test_mismatched_operation_id_reuse_conflicts(api, monkeypatch):
    _enable(monkeypatch)
    assert api.post("/api/sync/vocabulary/put", _put_body())[0] == 200
    before = _entity_rows(api.folder)
    status, body = api.post(
        "/api/sync/vocabulary/put",
        _put_body(payload=_payload(meaning="different")),
    )
    assert status == 409
    assert body["error"] == "Sync conflict."
    assert _entity_rows(api.folder) == before
    assert _change_count(api.folder) == 1
    assert json.loads(before[0][5])["meaning"] == "house"


def test_change_cursor_pagination_and_tombstones(api, monkeypatch):
    _enable(monkeypatch)
    assert api.post("/api/sync/vocabulary/put", _put_body())[0] == 200
    assert (
        api.post(
            "/api/sync/vocabulary/put",
            _put_body(
                vocab_id=VOCAB_B,
                payload=_payload(VOCAB_B, "book"),
                operation_id="op-b",
            ),
        )[0]
        == 200
    )
    assert (
        api.post(
            "/api/sync/vocabulary/delete",
            {
                "language_code": "nl",
                "vocab_id": VOCAB_A,
                "expected_revision": 1,
                "operation_id": "op-del-a",
            },
        )[0]
        == 200
    )

    status, page = api.post(
        "/api/sync/vocabulary/changes",
        {"after_cursor": 0, "limit": 2},
    )
    assert status == 200
    assert page["limit"] == 2
    assert page["has_more"] is True
    assert [item["vocab_id"] for item in page["changes"]] == [VOCAB_A, VOCAB_B]
    assert page["changes"][0]["deleted"] is False
    assert page["next_cursor"] == page["changes"][-1]["cursor"]

    status, rest = api.post(
        "/api/sync/vocabulary/changes",
        {"after_cursor": page["next_cursor"], "limit": 2},
    )
    assert status == 200
    assert rest["has_more"] is False
    assert len(rest["changes"]) == 1
    assert rest["changes"][0]["vocab_id"] == VOCAB_A
    assert rest["changes"][0]["deleted"] is True
    assert rest["changes"][0]["revision"] == 2
    assert rest["next_cursor"] == rest["changes"][0]["cursor"]


def test_excessive_request_size_does_not_open_sync_db(api, monkeypatch):
    _enable(monkeypatch)
    opened = []

    def forbid(path):
        opened.append(path)
        raise AssertionError("sync db should stay closed")

    monkeypatch.setattr(sync_store, "connect", forbid)
    status, body = api.post(
        "/api/sync/vocabulary/put",
        raw=b"x" * (sync_http.SYNC_MAX_BODY + 1),
    )
    assert status == 413
    assert body["error"] == "Sync request is too large."
    assert opened == []
    assert not api.sync_db().exists()


def test_malformed_json_and_unexpected_payload(api, monkeypatch):
    _enable(monkeypatch)
    opened = []
    original_connect = sync_store.connect

    def track(path):
        opened.append(path)
        return original_connect(path)

    monkeypatch.setattr(sync_store, "connect", track)

    malformed, malformed_body = api.post(
        "/api/sync/vocabulary/put",
        raw=b"{",
    )
    assert malformed == 400
    assert malformed_body == {"error": "Invalid sync request."}
    assert opened == []

    unexpected, unexpected_body = api.post(
        "/api/sync/vocabulary/put",
        _put_body(admin=True),
    )
    assert unexpected == 400
    assert unexpected_body["error"] == "Invalid sync request."
    assert opened == []

    nested, nested_body = api.post(
        "/api/sync/vocabulary/put",
        _put_body(payload={"id": VOCAB_A, "word": "huis", "meaning": "house", "password": "nope"}),
    )
    assert nested == 400
    assert nested_body["error"] == "Invalid sync request."
    assert "nope" not in json.dumps(nested_body)
    if api.sync_db().exists():
        assert _entity_rows(api.folder) == []


def test_internal_sqlite_error_is_sanitized(api, monkeypatch):
    _enable(monkeypatch)

    def boom(_path):
        raise sqlite3.OperationalError(
            r"unable to open database file D:\secret\study_sync.db"
        )

    monkeypatch.setattr(sync_store, "connect", boom)
    status, body = api.post("/api/sync/vocabulary/put", _put_body())
    assert status == 500
    assert body == {"error": "Sync store unavailable."}
    rendered = json.dumps(body).lower()
    assert "secret" not in rendered
    assert "study_sync" not in rendered
    assert "operationalerror" not in rendered
    assert "traceback" not in rendered
    assert "sqlite" not in rendered


def test_legacy_routes_do_not_match_query_strings(api, monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setattr(account_server, "_grade", lambda payload: {"mock": "grade"})
    opened = []

    def forbid(path):
        opened.append(path)
        raise AssertionError("sync db should stay closed")

    monkeypatch.setattr(sync_store, "connect", forbid)
    grade, grade_body = api.post("/api/grade?x=1", {"word": "huis"})
    assert grade == 404
    assert grade_body["error"] == "Không có chức năng này."
    exact, exact_body = api.post("/api/grade", {"word": "huis"})
    assert exact == 200
    assert exact_body == {"mock": "grade"}
    sync, sync_body = api.post("/api/sync/vocabulary/put?x=1", _put_body())
    assert sync == 404
    assert sync_body["error"] == "Không có chức năng này."
    assert opened == []
    assert not api.sync_db().exists()


def test_existing_account_routes_still_work_while_sync_is_off(api, monkeypatch):
    monkeypatch.setattr(account_server, "_grade", lambda payload: {"mock": "grade"})
    monkeypatch.setattr(account_server, "_reading", lambda payload: {"mock": "reading"})
    monkeypatch.setattr(account_server, "_listening", lambda payload: {"mock": "listening"})
    monkeypatch.setattr(account_server, "_enrich", lambda payload: {"mock": "enrich"})

    login_status, login_body = api.post(
        "/api/login",
        {"username": "learner", "password": "secret1"},
        use_auth=False,
    )
    assert login_status == 200
    assert isinstance(login_body["token"], str) and login_body["token"]

    grade_body_token, grade_body = api.post(
        "/api/grade",
        {"token": api.token, "word": "huis", "sentence": "Dit is een huis.", "meaning": "nhà"},
        use_auth=False,
    )
    assert grade_body_token == 200
    assert grade_body == {"mock": "grade"}

    for path, marker in (
        ("/api/grade", "grade"),
        ("/api/reading", "reading"),
        ("/api/listening", "listening"),
        ("/api/enrich", "enrich"),
    ):
        status, body = api.post(path, {"word": "huis"})
        assert status == 200
        assert body == {"mock": marker}

    missing, missing_body = api.post("/api/grade", {"word": "huis"}, use_auth=False)
    assert missing == 401
    assert missing_body["error"] == "Hãy đăng nhập lại."

    sync_status, _sync_body = api.post("/api/sync/vocabulary/changes", {"after_cursor": 0})
    assert sync_status == 404
    assert not api.sync_db().exists()
