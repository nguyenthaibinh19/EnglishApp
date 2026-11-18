"""Test group C — D5A2D4 E1/E2 interrupted-transfer fail-closed semantics."""

from __future__ import annotations

import json
from pathlib import Path

from offbox_support import MemSock, ensure_offbox_on_path, exclusive_write, latest_state

ensure_offbox_on_path()
import age_encrypt  # noqa: E402
import backup_worker  # noqa: E402
import framing  # noqa: E402
import logutil  # noqa: E402
import peer_auth  # noqa: E402
import snapshot_copy  # noqa: E402
import snapshot_helper  # noqa: E402

FORBIDDEN_SUCCESS_STATES = frozenset(
    {"RECEIVED", "ENCRYPTED", "UPLOADING", "VERIFIED", "RECONCILED"}
)


def _fake_age(tmp_path: Path) -> str:
    path = tmp_path / "fake-age.bin"
    exclusive_write(path, "fake-age-not-executed\n")
    return str(path)


def _state_history(attempt_dir: Path) -> list[str]:
    states: list[str] = []
    for path in sorted(attempt_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        states.append(str(data.get("state", "")))
    return states


def _assert_e1_fail_closed(result, attempt_dir: Path, *, encrypt_calls: list, publish_calls: list) -> None:
    history = _state_history(attempt_dir)
    st, detail = latest_state(attempt_dir)
    assert result.status == "FAILED"
    assert result.detail == "truncated"
    assert st == "FAILED"
    assert detail == "truncated"
    assert history, "expected at least one attempt state record"
    assert all(state not in FORBIDDEN_SUCCESS_STATES for state in history), history
    assert "RECEIVED" not in history
    assert "ENCRYPTED" not in history
    assert "UPLOADING" not in history
    assert "VERIFIED" not in history
    assert "RECONCILED" not in history
    assert encrypt_calls == []
    assert publish_calls == []


def test_e1_truncated_frame_worker_fail_closed(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    cred = tmp_path / "cred"
    cred.mkdir()
    exclusive_write(cred / "oauth-refresh", "fake-refresh-not-a-real-token\n")
    age_path = _fake_age(tmp_path)

    encrypt_calls: list[object] = []
    publish_calls: list[object] = []
    real_find = age_encrypt.find_age
    real_rej = age_encrypt.recipient_rejected
    real_probe = backup_worker.probe_source
    real_encrypt = age_encrypt.encrypt_bytes
    real_publish = backup_worker._publish

    def spy_encrypt(*args, **kwargs):
        encrypt_calls.append((args, kwargs))
        return real_encrypt(*args, **kwargs)

    def spy_publish(*args, **kwargs):
        publish_calls.append((args, kwargs))
        return real_publish(*args, **kwargs)

    age_encrypt.find_age = lambda p: age_path
    age_encrypt.recipient_rejected = lambda r: False
    backup_worker.probe_source = lambda path: "unreadable"
    age_encrypt.encrypt_bytes = spy_encrypt
    backup_worker._publish = spy_publish
    try:
        result = backup_worker.run(
            state_dir=str(state),
            source_db=str(tmp_path / "missing.db"),
            socket_path=str(tmp_path / "unused.sock"),
            recipient="age1pq1" + ("a" * 1500),
            age_exe=age_path,
            attempt_id="d5a2d7-e1-trunc",
            credential_dir=str(cred),
            free_bytes=10 * 1024 * 1024 * 1024,
            connected=MemSock(b"LGS1"),
            transport=None,
        )
    finally:
        age_encrypt.find_age = real_find
        age_encrypt.recipient_rejected = real_rej
        backup_worker.probe_source = real_probe
        age_encrypt.encrypt_bytes = real_encrypt
        backup_worker._publish = real_publish

    _assert_e1_fail_closed(
        result,
        state / "d5a2d7-e1-trunc",
        encrypt_calls=encrypt_calls,
        publish_calls=publish_calls,
    )


def test_e1_partial_frame_worker_fail_closed(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    cred = tmp_path / "cred"
    cred.mkdir()
    exclusive_write(cred / "oauth-refresh", "fake-refresh-not-a-real-token\n")
    age_path = _fake_age(tmp_path)

    encrypt_calls: list[object] = []
    publish_calls: list[object] = []
    real_find = age_encrypt.find_age
    real_rej = age_encrypt.recipient_rejected
    real_probe = backup_worker.probe_source
    real_encrypt = age_encrypt.encrypt_bytes
    real_publish = backup_worker._publish

    def spy_encrypt(*args, **kwargs):
        encrypt_calls.append((args, kwargs))
        return real_encrypt(*args, **kwargs)

    def spy_publish(*args, **kwargs):
        publish_calls.append((args, kwargs))
        return real_publish(*args, **kwargs)

    age_encrypt.find_age = lambda p: age_path
    age_encrypt.recipient_rejected = lambda r: False
    backup_worker.probe_source = lambda path: "unreadable"
    age_encrypt.encrypt_bytes = spy_encrypt
    backup_worker._publish = spy_publish
    frame = framing.encode_frame(b"y" * 200)[:20]
    try:
        result = backup_worker.run(
            state_dir=str(state),
            source_db=str(tmp_path / "missing2.db"),
            socket_path=str(tmp_path / "unused.sock"),
            recipient="age1pq1" + ("b" * 1500),
            age_exe=age_path,
            attempt_id="d5a2d7-e1-partial",
            credential_dir=str(cred),
            free_bytes=10 * 1024 * 1024 * 1024,
            connected=MemSock(frame),
            transport=None,
        )
    finally:
        age_encrypt.find_age = real_find
        age_encrypt.recipient_rejected = real_rej
        backup_worker.probe_source = real_probe
        age_encrypt.encrypt_bytes = real_encrypt
        backup_worker._publish = real_publish

    _assert_e1_fail_closed(
        result,
        state / "d5a2d7-e1-partial",
        encrypt_calls=encrypt_calls,
        publish_calls=publish_calls,
    )


def test_e2_helper_incomplete_on_send_failure(tmp_path: Path) -> None:
    logs: list[str] = []

    def capture(event, **fields):
        parts = [f"event={event}"] + [f"{k}={v}" for k, v in fields.items()]
        logs.append(" ".join(parts))

    real_log = logutil.log_event
    real_auth = peer_auth.authorize_socket
    real_snap = snapshot_copy.snapshot_memory
    logutil.log_event = capture
    peer_auth.authorize_socket = lambda *a, **k: "accepted"

    class Snap:
        status = "SNAPSHOTTED"
        detail = "ok"
        sha256 = "0" * 64
        image = b"Z" * 64

    snapshot_copy.snapshot_memory = lambda *a, **k: Snap()
    sock = MemSock()
    sock.fail_after = 0
    audit = tmp_path / "audit"
    audit.mkdir()
    env = {
        "LG_ATTEMPT_ID": "d5a2d7-e2-incomplete",
        "LG_SOURCE_DB": str(tmp_path / "unused.db"),
        "LG_AUDIT_DIR": str(audit),
        "LG_FORBIDDEN_PLAINTEXT_DIR": str(tmp_path / "forbidden"),
        "LG_EXPECTED_UID": "991",
        "LG_EXPECTED_GID": "981",
        "LG_EXPECTED_UNIT": "lgd5a2d7-worker.service",
    }
    try:
        rc = snapshot_helper.serve(sock, env)
    finally:
        logutil.log_event = real_log
        peer_auth.authorize_socket = real_auth
        snapshot_copy.snapshot_memory = real_snap

    joined = "\n".join(logs)
    st, detail = latest_state(audit)
    assert rc == 1
    assert "detail=incomplete" in joined
    assert "detail=frame-sent" not in joined
    assert st == "FAILED"
    assert detail == "transfer-incomplete"


def test_e2_helper_incomplete_mid_send(tmp_path: Path) -> None:
    logs: list[str] = []

    def capture(event, **fields):
        parts = [f"event={event}"] + [f"{k}={v}" for k, v in fields.items()]
        logs.append(" ".join(parts))

    real_log = logutil.log_event
    real_auth = peer_auth.authorize_socket
    real_snap = snapshot_copy.snapshot_memory
    logutil.log_event = capture
    peer_auth.authorize_socket = lambda *a, **k: "accepted"

    class Snap:
        status = "SNAPSHOTTED"
        detail = "ok"
        sha256 = "1" * 64
        image = b"Q" * 4096

    snapshot_copy.snapshot_memory = lambda *a, **k: Snap()
    sock = MemSock()
    sock.fail_after = 8
    audit = tmp_path / "audit"
    audit.mkdir()
    env = {
        "LG_ATTEMPT_ID": "d5a2d7-e2-midsend",
        "LG_SOURCE_DB": str(tmp_path / "unused2.db"),
        "LG_AUDIT_DIR": str(audit),
        "LG_FORBIDDEN_PLAINTEXT_DIR": str(tmp_path / "forbidden"),
        "LG_EXPECTED_UID": "991",
        "LG_EXPECTED_GID": "981",
        "LG_EXPECTED_UNIT": "lgd5a2d7-worker.service",
    }
    try:
        rc = snapshot_helper.serve(sock, env)
    finally:
        logutil.log_event = real_log
        peer_auth.authorize_socket = real_auth
        snapshot_copy.snapshot_memory = real_snap

    joined = "\n".join(logs)
    assert rc == 1
    assert "detail=incomplete" in joined
    assert "detail=frame-sent" not in joined
