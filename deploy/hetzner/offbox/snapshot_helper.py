"""Snapshot helper. One connected socket, one in-memory copy, one frame.

systemd starts this process with Accept=yes. Standard input is the accepted
connection. The helper does not listen, does not read a credential file, and
does not encrypt. The consistent SQLite image stays in process memory until
the frame is sent. No plaintext database file is created.
Protocol bytes are written only through one private socket fd.
stdin, stdout, and a stderr that refers to that same socket are
moved to /dev/null before any status line is written.

Expected uid, gid, and unit are process configuration. They are not taken
from the peer or from bytes on the socket.
"""

from __future__ import annotations

import os
import re
import socket
import sys

sys.dont_write_bytecode = True

if __package__ in {None, ""}:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import attempt_store
import framing
import logutil
import peer_auth
import snapshot_copy

PRODUCTION_UID = 994
PRODUCTION_GID = 977
PRODUCTION_UNIT = "lg-backup.service"
_UNIT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:_.@-]{0,127}$")


def configured_identity(env: dict):
    unit = env.get("LG_EXPECTED_UNIT", PRODUCTION_UNIT)
    if not _UNIT.fullmatch(unit or ""):
        return None
    try:
        uid = int(env.get("LG_EXPECTED_UID", str(PRODUCTION_UID)))
        gid = int(env.get("LG_EXPECTED_GID", str(PRODUCTION_GID)))
    except ValueError:
        return None
    if uid <= 0 or gid <= 0:
        return None
    return uid, gid, unit


def _accepting(sock) -> bool:
    try:
        return sock.getsockopt(socket.SOL_SOCKET, socket.SO_ACCEPTCONN) == 1
    except (AttributeError, OSError):
        return False


def _inside(path: str, parent: str) -> bool:
    if not parent:
        return False
    child = os.path.realpath(path)
    root = os.path.realpath(parent)
    return child == root or child.startswith(root + os.sep)


def serve(sock, environ: dict | None = None) -> int:
    env = os.environ if environ is None else environ
    attempt_id = env.get("LG_ATTEMPT_ID", "") or attempt_store.new_attempt_id()
    source = env.get("LG_SOURCE_DB", "/opt/language-guard/accounts.db")
    audit_dir = env.get("LG_AUDIT_DIR", "")
    forbidden = env.get("LG_FORBIDDEN_PLAINTEXT_DIR", "/var/lib/language-guard-backup")
    identity = configured_identity(env)
    if identity is None or not attempt_store.safe_id(attempt_id):
        logutil.log_event("refuse", reason="configuration")
        return 1
    expected_uid, expected_gid, expected_unit = identity
    if _accepting(sock):
        logutil.log_event("refuse", reason="listening-socket", unit=expected_unit)
        return 1
    decision = peer_auth.authorize_socket(sock, expected_uid, expected_gid, expected_unit)
    logutil.log_event("peer", decision=decision, unit=expected_unit)
    if decision != "accepted":
        _send_token(sock, framing.REFUSED)
        return 1
    metadata_path = ""
    if audit_dir:
        if os.path.islink(audit_dir) or not os.path.isdir(audit_dir) or _inside(audit_dir, forbidden):
            logutil.log_event("snapshot", status="FAILED", detail="audit-dir")
            _send_token(sock, framing.FAILED)
            return 1
        metadata_path = os.path.join(audit_dir, attempt_id + ".meta.json")
    before = _source_identity(source)
    result = snapshot_copy.snapshot_memory(source, metadata_path or None)
    after = _source_identity(source)
    logutil.log_event(
        "snapshot",
        status=result.status,
        detail=result.detail,
        sha256=result.sha256,
        source_unchanged=str(before == after),
        bytes=len(result.image) if result.status == "SNAPSHOTTED" else 0,
    )
    if result.status != "SNAPSHOTTED":
        _send_token(sock, framing.FAILED)
        return 1
    try:
        framing.send_all(sock, framing.encode_frame(result.image))
    except OSError:
        _write_note(audit_dir, "FAILED", "transfer-incomplete")
        logutil.log_event("transfer", detail="incomplete")
        return 1
    _write_note(audit_dir, "TRANSFERRED", "frame-sent")
    logutil.log_event("transfer", detail="frame-sent", size=len(result.image))
    return 0


def _write_note(directory: str, state: str, detail: str) -> None:
    if not directory:
        return
    try:
        attempt_store.write_state(directory, state, detail)
    except OSError:
        logutil.log_event("note-unwritten", detail=detail)


def _send_token(sock, token: bytes) -> None:
    try:
        framing.send_all(sock, token)
    except OSError:
        logutil.log_event("transfer", detail="incomplete")


def _source_identity(path: str):
    try:
        info = os.lstat(path)
    except OSError:
        return None
    return (int(info.st_dev), int(info.st_ino), int(info.st_size), int(info.st_mtime_ns))


def _same_open_file(left: int, right: int) -> bool:
    try:
        left_info = os.fstat(left)
        right_info = os.fstat(right)
    except OSError:
        return False
    return left_info.st_dev == right_info.st_dev and left_info.st_ino == right_info.st_ino


def _private_socket(source_fd: int) -> socket.socket:
    """Detach the connected socket from stdin, stdout, and a shared stderr.

    systemd socket activation puts the connection on stdin and stdout.
    When StandardError is left unset it inherits that same socket, so a
    status line becomes the first bytes of the snapshot stream. Status
    stays on stderr only when stderr is a different file, which is the
    journal after StandardError=journal.
    """
    protocol_fd = os.dup(source_fd)
    os.set_inheritable(protocol_fd, False)
    null_fd = os.open(os.devnull, os.O_RDWR)
    try:
        for standard_fd in (0, 1, 2):
            if standard_fd != protocol_fd and _same_open_file(standard_fd, protocol_fd):
                os.dup2(null_fd, standard_fd)
    finally:
        os.close(null_fd)
    return socket.socket(fileno=protocol_fd)


def main() -> int:
    fd = int(os.environ.get("LG_SOCKET_FD", "0"))
    sock = _private_socket(fd)
    try:
        return serve(sock)
    finally:
        sock.close()


if __name__ == "__main__":
    sys.exit(main())
