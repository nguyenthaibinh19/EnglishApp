"""Local staging checklist for Phase 18B.2. No VPS, secrets, or real accounts."""

from __future__ import annotations

import json
import os
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import account_server
import account_store
import sync_store
from sync_backup import backup_database, restore_database
from test_hetzner_package import (
    test_packaged_account_server_imports_without_opening_sync_db,
)

VOCAB = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def _use_tmp_accounts(monkeypatch, folder: Path) -> None:
    def db_path(explicit=None):
        root = explicit or str(folder)
        return os.path.join(root, account_store.DB_FILE)

    monkeypatch.setattr(account_store, "db_path", db_path)


def _post(port: int, path: str, payload: dict, token: str = ""):
    import urllib.error
    import urllib.request

    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
    )
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


def test_staging_checklist_flag_off_then_local_flag_on(tmp_path, monkeypatch):
    package_root = tmp_path / "package"
    package_root.mkdir()
    test_packaged_account_server_imports_without_opening_sync_db(package_root)

    _use_tmp_accounts(monkeypatch, tmp_path)
    monkeypatch.delenv("STUDY_SYNC_ENABLED", raising=False)
    monkeypatch.setenv("STUDY_SYNC_DIR", str(tmp_path))
    monkeypatch.setattr(account_server, "_grade", lambda payload: {"mock": "grade"})
    monkeypatch.setattr(account_server, "_reading", lambda payload: {"mock": "reading"})
    monkeypatch.setattr(account_server, "_listening", lambda payload: {"mock": "listening"})
    monkeypatch.setattr(account_server, "_enrich", lambda payload: {"mock": "enrich"})
    account_store.add_user("staging", "secret1")
    token = account_store.login("staging", "secret1")

    server = ThreadingHTTPServer(("127.0.0.1", 0), account_server.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        login, login_body = _post(
            port,
            "/api/login",
            {"username": "staging", "password": "secret1"},
        )
        assert login == 200 and login_body["token"]
        for path, marker in (
            ("/api/grade", "grade"),
            ("/api/reading", "reading"),
            ("/api/listening", "listening"),
            ("/api/enrich", "enrich"),
        ):
            status, body = _post(port, path, {"word": "huis"}, token)
            assert status == 200 and body == {"mock": marker}
        hidden, hidden_body = _post(
            port,
            "/api/sync/vocabulary/put",
            {
                "language_code": "nl",
                "vocab_id": VOCAB,
                "payload": {"id": VOCAB, "word": "huis", "meaning": "house"},
                "expected_revision": 0,
                "operation_id": "op-1",
            },
            token,
        )
        assert hidden == 404
        assert hidden_body["error"] == "Không có chức năng này."
        assert not (tmp_path / "study_sync.db").exists()

        monkeypatch.setenv("STUDY_SYNC_ENABLED", "1")
        created, created_body = _post(
            port,
            "/api/sync/vocabulary/put",
            {
                "language_code": "nl",
                "vocab_id": VOCAB,
                "payload": {"id": VOCAB, "word": "huis", "meaning": "house"},
                "expected_revision": 0,
                "operation_id": "op-1",
            },
            token,
        )
        assert created == 200
        assert created_body["revision"] == 1
        sync_path = tmp_path / "study_sync.db"
        assert sync_path.is_file()
        published = backup_database(str(sync_path), str(tmp_path / "backups"))
        assert published is not None and published.retention_warning is None
        restored = tmp_path / "restored.db"
        restore_database(published.path, str(restored))
        restored_conn = sync_store.connect(str(restored))
        try:
            record = sync_store.get_vocabulary(
                restored_conn,
                user_id=account_store.user_for_token(token)["id"],
                language_code="nl",
                vocab_id=VOCAB,
            )
            assert record is not None and record.revision == 1
        finally:
            restored_conn.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
