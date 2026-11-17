"""Backup worker. Connects to the helper, checks the frame, encrypts.

The worker does not keep a plaintext snapshot. Ciphertext is the only
database image written under the state directory. A failed age invocation
leaves its exclusive output file in place.

States produced here:
- PENDING, RECEIVED, ENCRYPTED, UPLOADING, UNKNOWN, VERIFIED, RECONCILED, FAILED
ENCRYPTED is not off-box backup success.
VERIFIED requires an independent download whose SHA-256 matches the ciphertext.
An HTTP status alone cannot become VERIFIED.
The restore drill is a separate record and is not set here.
"""

from __future__ import annotations

import errno
import os
import socket
import sys

sys.dont_write_bytecode = True

if __package__ in {None, ""}:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import age_encrypt
import attempt_store
import credential
import drive_upload
import framing
import logutil
import snapshot_copy


class WorkerResult:
    def __init__(self, status: str, detail: str, attempt_dir: str = "") -> None:
        self.status = status
        self.detail = detail
        self.attempt_dir = attempt_dir


def classify_backup(
    *,
    transfer_ok: bool,
    encrypted_ok: bool,
    http_status: int | None,
    download_matches: bool,
    drill_passed: bool,
) -> str:
    """Return the backup state. HTTP 200 alone cannot return VERIFIED.

    drill_passed is accepted and ignored. A restore drill does not make a
    backup VERIFIED, and a download match does not mean the drill passed.
    """
    del drill_passed
    if download_matches and transfer_ok and encrypted_ok:
        return "VERIFIED"
    if http_status is not None and not download_matches:
        return "UNKNOWN"
    if not transfer_ok or not encrypted_ok:
        return "FAILED"
    return "ENCRYPTED"


def probe_source(path: str) -> str:
    if os.path.islink(path):
        return "redirect"
    try:
        handle = os.open(path, os.O_RDONLY)
    except FileNotFoundError:
        return "absent"
    except PermissionError:
        return "unreadable"
    except OSError as exc:
        if exc.errno in {errno.EACCES, errno.EPERM, errno.ENOENT}:
            return "unreadable" if exc.errno != errno.ENOENT else "absent"
        return "unreadable"
    else:
        os.close(handle)
        return "readable"


def credential_state(directory: str) -> str:
    if not directory or os.path.islink(directory):
        return "absent"
    path = os.path.join(directory, "oauth-refresh")
    if os.path.islink(path):
        return "absent"
    try:
        handle = os.open(path, os.O_RDONLY)
    except OSError:
        return "absent"
    try:
        os.read(handle, 1)
    finally:
        os.close(handle)
    return "present"


def run(
    *,
    state_dir: str,
    source_db: str,
    socket_path: str = "",
    connected=None,
    recipient: str = "",
    age_exe: str = "",
    attempt_id: str = "",
    credential_dir: str = "",
    free_bytes: int | None = None,
    transport=None,
    folder_id: str = "",
    object_name: str = "",
    token_exchanger=None,
    multipart_limit: int = drive_upload.MULTIPART_LIMIT,
    chunk_size: int = drive_upload.CHUNK,
    resume: bool = False,
) -> WorkerResult:
    if resume:
        return continue_upload(
            state_dir=state_dir,
            attempt_id=attempt_id,
            credential_dir=credential_dir,
            transport=transport,
            folder_id=folder_id,
            object_name=object_name,
            token_exchanger=token_exchanger,
            multipart_limit=multipart_limit,
            chunk_size=chunk_size,
        )
    if os.path.islink(state_dir) or not os.path.isdir(state_dir):
        logutil.log_event("attempt", status="FAILED", detail="state-dir-absent")
        return WorkerResult("FAILED", "state-dir-absent")
    attempt_id = attempt_id or attempt_store.new_attempt_id()
    if not attempt_store.safe_id(attempt_id):
        logutil.log_event("attempt", status="FAILED", detail="attempt-id")
        return WorkerResult("FAILED", "attempt-id")
    try:
        attempt_dir = attempt_store.reserve(state_dir, attempt_id)
    except FileExistsError:
        logutil.log_event("attempt", status="FAILED", detail="duplicate")
        return WorkerResult("FAILED", "duplicate", os.path.join(state_dir, attempt_id))
    attempt_store.write_state(attempt_dir, "PENDING", "reserved")
    source_state = probe_source(source_db)
    logutil.log_event("source-boundary", result=source_state)
    if source_state != "unreadable":
        detail = "source-readable" if source_state == "readable" else "source-" + source_state
        _fail(attempt_dir, detail)
        return WorkerResult("FAILED", detail, attempt_dir)
    cred = credential_state(credential_dir)
    logutil.log_event("credential", status=cred, name="oauth-refresh")
    if cred != "present":
        _fail(attempt_dir, "credential-absent")
        return WorkerResult("FAILED", "credential-absent", attempt_dir)
    if free_bytes is None:
        try:
            free_bytes = snapshot_copy.available_bytes(state_dir)
        except OSError:
            _fail(attempt_dir, "disk-check-unavailable")
            return WorkerResult("FAILED", "disk-check-unavailable", attempt_dir)
    if snapshot_copy.disk_decision(free_bytes) != "ok":
        _fail(attempt_dir, "disk-space")
        return WorkerResult("FAILED", "disk-space", attempt_dir)
    age_path = age_encrypt.find_age(age_exe)
    if age_encrypt.recipient_rejected(recipient) or not os.path.isfile(age_path):
        detail = "recipient-rejected" if age_encrypt.recipient_rejected(recipient) else "age-missing"
        _fail(attempt_dir, detail)
        return WorkerResult("FAILED", detail, attempt_dir)
    sock = connected
    try:
        if sock is None:
            sock = _connect(socket_path)
        status, payload = framing.receive(sock)
    except OSError:
        _fail(attempt_dir, "truncated")
        return WorkerResult("FAILED", "truncated", attempt_dir)
    finally:
        if connected is None and sock is not None:
            try:
                sock.close()
            except OSError:
                pass
    logutil.log_event(
        "transfer",
        status=status,
        size=len(payload),
        frame_verified="true" if status == "verified" else "false",
        download_verified="false",
    )
    if status != "verified":
        _fail(attempt_dir, status)
        return WorkerResult("FAILED", status, attempt_dir)
    attempt_store.write_state(
        attempt_dir,
        "RECEIVED",
        "frame-verified",
        {"download_verified": False, "restore_drill": False, "bytes": len(payload)},
    )
    encrypted = _encrypt(attempt_dir, payload, recipient, age_path)
    if encrypted.status != "ENCRYPTED" or transport is None:
        return encrypted
    return _publish(
        attempt_dir,
        credential_dir,
        transport,
        folder_id,
        object_name,
        token_exchanger,
        multipart_limit,
        chunk_size,
    )


def _encrypt(attempt_dir: str, payload: bytes, recipient: str, age_exe: str) -> WorkerResult:
    dest = os.path.join(attempt_dir, "snapshot.age")
    encrypted = age_encrypt.encrypt_bytes(payload, dest, recipient, age_exe)
    if encrypted.status != "ENCRYPTED":
        _fail(attempt_dir, encrypted.detail)
        return WorkerResult("FAILED", encrypted.detail, attempt_dir)
    record_state = classify_backup(
        transfer_ok=True,
        encrypted_ok=True,
        http_status=None,
        download_matches=False,
        drill_passed=False,
    )
    if record_state == "VERIFIED":
        _fail(attempt_dir, "verified-refused")
        return WorkerResult("FAILED", "verified-refused", attempt_dir)
    attempt_store.write_state(
        attempt_dir,
        record_state,
        encrypted.detail,
        {
            "ciphertext_sha256": encrypted.sha256,
            "download_verified": False,
            "restore_drill": False,
            "http_status": None,
        },
    )
    logutil.log_event(
        "encrypted",
        state=record_state,
        sha256=encrypted.sha256,
        frame_verified="true",
        download_verified="false",
    )
    return WorkerResult(record_state, encrypted.detail, attempt_dir)


def continue_upload(
    *,
    state_dir: str,
    attempt_id: str,
    credential_dir: str,
    transport,
    folder_id: str,
    object_name: str,
    token_exchanger,
    multipart_limit: int,
    chunk_size: int,
) -> WorkerResult:
    attempt_dir = os.path.join(state_dir, attempt_id)
    if not attempt_store.safe_id(attempt_id) or not os.path.isdir(attempt_dir):
        return WorkerResult("FAILED", "attempt-absent", attempt_dir)
    return _publish(
        attempt_dir,
        credential_dir,
        transport,
        folder_id,
        object_name,
        token_exchanger,
        multipart_limit,
        chunk_size,
    )


def _publish(
    attempt_dir: str,
    credential_dir: str,
    transport,
    folder_id: str,
    object_name: str,
    token_exchanger,
    multipart_limit: int,
    chunk_size: int,
) -> WorkerResult:
    if transport is None or token_exchanger is None or not folder_id or not object_name:
        _fail(attempt_dir, "upload-unconfigured")
        return WorkerResult("FAILED", "upload-unconfigured", attempt_dir)
    try:
        token = credential.access_token(credential_dir, token_exchanger)
    except credential.TokenError as exc:
        _fail(attempt_dir, exc.detail)
        return WorkerResult("FAILED", exc.detail, attempt_dir)
    label = _transport_name(transport)
    attempt_store.write_state(
        attempt_dir,
        "UPLOADING",
        "started",
        {"download_verified": False, "restore_drill": False, "transport": label},
    )
    outcome = drive_upload.upload_or_resume(
        transport,
        token,
        folder_id,
        object_name,
        os.path.join(attempt_dir, "snapshot.age"),
        attempt_dir,
        multipart_limit=multipart_limit,
        chunk_size=chunk_size,
    )
    extra = {
        "bytes": outcome.size,
        "ciphertext_sha256": outcome.sha256,
        "download_verified": outcome.download_verified,
        "drive_file_id": outcome.file_id,
        "restore_drill": False,
        "transport": label,
    }
    if outcome.verified_at:
        extra["verified_at"] = outcome.verified_at
    attempt_store.write_state(attempt_dir, outcome.status, outcome.detail, extra)
    logutil.log_event(
        "upload",
        status=outcome.status,
        detail=outcome.detail,
        download_verified="true" if outcome.download_verified else "false",
        restore_drill="false",
        frame_verified="true",
        transport=label,
    )
    return WorkerResult(outcome.status, outcome.detail, attempt_dir)


def _transport_name(transport) -> str:
    if getattr(transport, "scheme", "") != "https":
        return "fake"
    if getattr(transport, "loopback", None):
        return "localhost"
    return "https"


def _fail(attempt_dir: str, detail: str) -> None:
    attempt_store.write_state(
        attempt_dir,
        "FAILED",
        detail,
        {"download_verified": False, "restore_drill": False},
    )
    logutil.log_event("attempt", status="FAILED", detail=detail)


def _connect(path: str):
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(30)
    sock.connect(path)
    return sock


def _recipient_from(path: str) -> str:
    if not path or os.path.islink(path):
        return ""
    try:
        handle = os.open(path, os.O_RDONLY)
    except OSError:
        return ""
    try:
        data = os.read(handle, 8193)
    finally:
        os.close(handle)
    if len(data) > 8192:
        return ""
    text = data.decode("utf-8", errors="replace").strip()
    if "\n" in text or " " in text or "AGE-SECRET" in text:
        return ""
    if not text.startswith("age1pq1") or len(text) < 1500:
        return ""
    return text


def main() -> int:
    if os.environ.get("LG_DRIVE_FOLDER") or os.environ.get("LG_UPLOAD_ENABLED"):
        logutil.log_event("worker-exit", status="FAILED", detail="live-transport-disabled")
        return 1
    result = run(
        state_dir=os.environ.get("LG_STATE_DIR", "/var/lib/language-guard-backup"),
        source_db=os.environ.get("LG_SOURCE_DB", "/opt/language-guard/accounts.db"),
        socket_path=os.environ.get("LG_SOCKET", "/run/lg-backup/handoff.sock"),
        recipient=_recipient_from(os.environ.get("LG_RECIPIENT_FILE", "")),
        age_exe=os.environ.get("LG_AGE_BIN", ""),
        attempt_id=os.environ.get("LG_ATTEMPT_ID", ""),
        credential_dir=os.environ.get("CREDENTIALS_DIRECTORY", ""),
    )
    logutil.log_event("worker-exit", status=result.status, detail=result.detail)
    return 0 if result.status == "ENCRYPTED" else 1


if __name__ == "__main__":
    sys.exit(main())
