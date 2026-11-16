"""Google Drive upload and independent download verification.

The design follows the accepted offline adapter: reserve one generated file
id, create it once, and reconcile that same id after an ambiguous result.
Multipart is used below the size limit. Larger ciphertext uses a chunked
resumable session. DELETE, PATCH, and metadata update PUT are refused.

VERIFIED is recorded only after the downloaded bytes match the local
ciphertext. A response code by itself is not verification. This module does
not open a live connection; the caller supplies a transport.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.parse
from dataclasses import dataclass
from typing import Mapping

sys.dont_write_bytecode = True

DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"
CREATE_URL = "https://www.googleapis.com/upload/drive/v3/files"
METADATA_URL = "https://www.googleapis.com/drive/v3/files"
GENERATE_URL = METADATA_URL + "/generateIds"
FILE_MIME = "application/octet-stream"
FIELDS = "id,name,mimeType,size,md5Checksum,parents"
MULTIPART_LIMIT = 5 * 1024 * 1024
CHUNK = 256 * 1024
MAX_CIPHERTEXT = 64 * 1024 * 1024
_DETAIL = set("abcdefghijklmnopqrstuvwxyz0123456789-")


class AmbiguousTransportError(Exception):
    def __init__(self, detail: str = "ambiguous") -> None:
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class HttpRequest:
    method: str
    url: str
    headers: Mapping[str, str]
    body: bytes


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    headers: Mapping[str, str]
    body: bytes


@dataclass(frozen=True)
class UploadOutcome:
    status: str
    detail: str
    file_id: str
    sha256: str
    download_verified: bool
    restore_drill: bool
    size: int
    verified_at: str


def session_uri_allowed(location: str) -> bool:
    parsed = urllib.parse.urlsplit(location)
    query = urllib.parse.parse_qs(parsed.query)
    return (
        parsed.scheme == "https"
        and parsed.hostname == "www.googleapis.com"
        and parsed.path == "/upload/drive/v3/files"
        and query.get("uploadType") == ["resumable"]
        and bool(query.get("upload_id"))
    )


def request_is_destructive(method: str, url: str) -> bool:
    lowered = url.lower()
    parsed = urllib.parse.urlsplit(url)
    if method in {"DELETE", "PATCH"}:
        return True
    if any(part in lowered for part in ("files.delete", "files.update", "/copy", "trash", "emptytrash")):
        return True
    if method == "PUT" and parsed.path.startswith("/drive/v3/files/"):
        return True
    if method == "PUT" and not session_uri_allowed(url):
        return True
    return False


def response_class(status_code: int) -> str:
    """A transport status is not a backup result."""
    if status_code == 308:
        return "UPLOADING"
    if status_code in (200, 201):
        return "RESPONSE_SEEN"
    if status_code == 401:
        return "FAILED"
    if status_code == 404:
        return "UNKNOWN"
    if status_code >= 500:
        return "UNKNOWN"
    return "FAILED"


def upload_or_resume(
    transport,
    token: str,
    folder_id: str,
    name: str,
    source_path: str,
    attempt_dir: str,
    *,
    multipart_limit: int = MULTIPART_LIMIT,
    chunk_size: int = CHUNK,
    stop_after_chunks: int | None = None,
) -> UploadOutcome:
    if os.path.islink(attempt_dir) or not os.path.isdir(attempt_dir):
        return _outcome("FAILED", "attempt-dir", "", "", 0)
    inspected = _inspect(source_path)
    if isinstance(inspected, UploadOutcome):
        return inspected
    digest, size = inspected
    try:
        progress_names = _progress_names(attempt_dir)
    except ValueError:
        return _outcome("FAILED", "progress-rejected", "", digest, size)
    if not _plain_name(name) or not _file_id(folder_id) or not token:
        return _outcome("FAILED", "invalid-request", "", digest, size)
    reservation = _read_json(os.path.join(attempt_dir, "drive-reservation.json"))
    if reservation is None and progress_names:
        return _outcome("FAILED", "progress-rejected", "", digest, size)
    if reservation is None:
        generated = _generate(transport, token)
        if generated.status != "SUCCESS" or not generated.file_id:
            return _outcome(generated.status, generated.detail, "", digest, size)
        reservation = {
            "file_id": generated.file_id,
            "folder_id": folder_id,
            "name": name,
            "phase": "reserved",
            "sha256": digest,
            "size": size,
        }
        try:
            _exclusive_json(os.path.join(attempt_dir, "drive-reservation.json"), reservation)
        except FileExistsError:
            return _outcome("FAILED", "reservation-exists", generated.file_id, digest, size)
    else:
        if (
            reservation.get("sha256") != digest
            or reservation.get("size") != size
            or reservation.get("name") != name
            or reservation.get("folder_id") != folder_id
            or not _file_id(str(reservation.get("file_id", "")))
        ):
            return _outcome("FAILED", "reservation-mismatch", str(reservation.get("file_id", "")), digest, size)
    file_id = str(reservation["file_id"])
    if _exists(os.path.join(attempt_dir, "upload-started")) or progress_names:
        return _resume(transport, token, reservation, source_path, attempt_dir, chunk_size, stop_after_chunks)
    _exclusive_write(os.path.join(attempt_dir, "upload-started"), b"started\n")
    if size <= multipart_limit:
        return _multipart(transport, token, reservation, source_path, attempt_dir)
    opened = _open_session(transport, token, reservation)
    if isinstance(opened, UploadOutcome):
        return opened
    try:
        _write_progress(attempt_dir, opened, file_id, 0)
    except ValueError:
        return _outcome("FAILED", "progress-rejected", file_id, digest, size)
    return _send_from(transport, token, reservation, source_path, attempt_dir, opened, 0, chunk_size, stop_after_chunks, 0)


def _resume(transport, token, reservation, source_path, attempt_dir, chunk_size, stop_after) -> UploadOutcome:
    file_id = reservation["file_id"]
    digest = reservation["sha256"]
    size = int(reservation["size"])
    try:
        names = _progress_names(attempt_dir)
    except ValueError:
        return _outcome("FAILED", "progress-rejected", file_id, digest, size)
    if not names:
        return _reconcile(transport, token, reservation, attempt_dir, "UNKNOWN")
    progress = _read_json(os.path.join(attempt_dir, names[-1])) or {}
    location = str(progress.get("session_uri", ""))
    if not session_uri_allowed(location) or progress.get("file_id") != file_id:
        return _outcome("FAILED", "progress-rejected", file_id, digest, size)
    queried = _query(transport, token, location, size)
    if queried == "EXPIRED":
        return _reconcile(transport, token, reservation, attempt_dir, "UNKNOWN")
    if queried == "COMPLETE":
        return _confirm(transport, token, reservation, attempt_dir, "RECONCILED")
    if not isinstance(queried, int):
        return _outcome("UNKNOWN", _safe_detail(queried), file_id, digest, size)
    return _send_from(
        transport, token, reservation, source_path, attempt_dir, location, queried, chunk_size, stop_after, 0
    )


def _multipart(transport, token, reservation, source_path, attempt_dir) -> UploadOutcome:
    payload = _read_file(source_path, int(reservation["size"]))
    meta = _meta(reservation)
    body, content_type = _multipart_body(meta, payload)
    url = CREATE_URL + "?" + urllib.parse.urlencode((("uploadType", "multipart"), ("fields", FIELDS)))
    response = _send(transport, "POST", url, token, body, {"Content-Type": content_type})
    if isinstance(response, UploadOutcome):
        return _stamp(response, reservation)
    return _after_create(transport, token, reservation, attempt_dir, response)


def _open_session(transport, token, reservation):
    body = json.dumps(_meta(reservation), separators=(",", ":")).encode("utf-8")
    url = CREATE_URL + "?" + urllib.parse.urlencode((("uploadType", "resumable"),))
    response = _send(
        transport,
        "POST",
        url,
        token,
        body,
        {
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Length": str(reservation["size"]),
            "X-Upload-Content-Type": FILE_MIME,
        },
    )
    if isinstance(response, UploadOutcome):
        return _stamp(response, reservation)
    location = _header(response, "Location")
    if response.status_code not in (200, 201) or not session_uri_allowed(location):
        return _after_create(transport, token, reservation, "", response)
    return location


def _send_from(transport, token, reservation, source_path, attempt_dir, location, offset, chunk_size, stop_after, sent):
    file_id = reservation["file_id"]
    digest = reservation["sha256"]
    size = int(reservation["size"])
    handle = os.open(source_path, os.O_RDONLY | getattr(os, "O_BINARY", 0))
    try:
        os.lseek(handle, offset, os.SEEK_SET)
        while offset < size:
            if stop_after is not None and sent >= stop_after:
                return _outcome("PAUSED", "stopped", file_id, digest, size)
            if offset % chunk_size != 0:
                return _outcome("UNKNOWN", "ack-rejected", file_id, digest, size)
            piece = os.read(handle, min(chunk_size, size - offset))
            if len(piece) != min(chunk_size, size - offset):
                return _outcome("FAILED", "short-read", file_id, digest, size)
            end = offset + len(piece) - 1
            response = _send(
                transport,
                "PUT",
                location,
                token,
                piece,
                {"Content-Range": "bytes %d-%d/%d" % (offset, end, size)},
            )
            sent += 1
            if isinstance(response, UploadOutcome):
                queried = _query(transport, token, location, size)
                if isinstance(queried, int):
                    offset = queried
                    os.lseek(handle, offset, os.SEEK_SET)
                    continue
                if queried == "COMPLETE":
                    return _confirm(transport, token, reservation, attempt_dir, "RECONCILED")
                return _outcome("UNKNOWN", _safe_detail(queried if isinstance(queried, str) else response.detail), file_id, digest, size)
            if response.status_code == 404:
                return _reconcile(transport, token, reservation, attempt_dir, "UNKNOWN")
            if response.status_code == 308:
                try:
                    offset = _ack_offset(_header(response, "Range"), size)
                except ValueError:
                    return _outcome("UNKNOWN", "ack-rejected", file_id, digest, size)
                try:
                    _write_progress(attempt_dir, location, file_id, offset)
                except ValueError:
                    return _outcome("FAILED", "progress-rejected", file_id, digest, size)
                os.lseek(handle, offset, os.SEEK_SET)
                continue
            if response.status_code in (200, 201) and end + 1 == size:
                return _confirm(transport, token, reservation, attempt_dir, "VERIFIED")
            if response.status_code >= 500:
                return _outcome("UNKNOWN", "http-500", file_id, digest, size)
            if response.status_code in (401, 403, 429):
                return _outcome("FAILED", "http-%d" % response.status_code, file_id, digest, size)
            return _outcome("FAILED", "http-%d" % response.status_code, file_id, digest, size)
    finally:
        os.close(handle)
    return _outcome("UNKNOWN", "incomplete", file_id, digest, size)


def _after_create(transport, token, reservation, attempt_dir, response) -> UploadOutcome:
    code = response.status_code
    if code in (200, 201):
        return _confirm(transport, token, reservation, attempt_dir, "VERIFIED")
    if code in (409, 500, 502, 503, 504) or code == 429:
        found = _confirm(transport, token, reservation, attempt_dir, "RECONCILED")
        if found.download_verified:
            return found
        if code >= 500:
            return _outcome("UNKNOWN", "http-500", reservation["file_id"], reservation["sha256"], int(reservation["size"]))
        if code == 429:
            return _outcome("FAILED", "http-429", reservation["file_id"], reservation["sha256"], int(reservation["size"]))
        if code == 409:
            return _outcome("UNKNOWN", found.detail, reservation["file_id"], reservation["sha256"], int(reservation["size"]))
    if code in (401, 403):
        return _outcome("FAILED", "http-%d" % code, reservation["file_id"], reservation["sha256"], int(reservation["size"]))
    if code >= 500:
        return _outcome("UNKNOWN", "http-500", reservation["file_id"], reservation["sha256"], int(reservation["size"]))
    return _outcome("FAILED", "http-%d" % code, reservation["file_id"], reservation["sha256"], int(reservation["size"]))


def _reconcile(transport, token, reservation, attempt_dir, fallback: str) -> UploadOutcome:
    found = _confirm(transport, token, reservation, attempt_dir, "RECONCILED")
    if found.download_verified:
        return found
    if found.detail == "http-404":
        return _outcome("UNKNOWN", "not-confirmed", reservation["file_id"], reservation["sha256"], int(reservation["size"]))
    if found.status == "FAILED":
        return found
    return _outcome(fallback, found.detail, reservation["file_id"], reservation["sha256"], int(reservation["size"]))


def _confirm(transport, token, reservation, attempt_dir, success: str) -> UploadOutcome:
    file_id = reservation["file_id"]
    digest = reservation["sha256"]
    size = int(reservation["size"])
    url = METADATA_URL + "/" + urllib.parse.quote(file_id) + "?" + urllib.parse.urlencode((("fields", FIELDS),))
    looked = _send(transport, "GET", url, token, b"", {})
    if isinstance(looked, UploadOutcome):
        return _outcome("UNKNOWN", looked.detail, file_id, digest, size)
    if looked.status_code == 404:
        return _outcome("UNKNOWN", "http-404", file_id, digest, size)
    if looked.status_code != 200:
        detail = "http-500" if looked.status_code >= 500 else "http-%d" % looked.status_code
        status = "UNKNOWN" if looked.status_code >= 500 or looked.status_code == 429 else "FAILED"
        return _outcome(status, detail, file_id, digest, size)
    try:
        meta = json.loads(looked.body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return _outcome("UNKNOWN", "unreadable-response", file_id, digest, size)
    mismatch = _metadata_problem(meta, reservation)
    if mismatch:
        return _outcome("FAILED", mismatch, file_id, digest, size)
    media = METADATA_URL + "/" + urllib.parse.quote(file_id) + "?alt=media"
    downloaded = _send(transport, "GET", media, token, b"", {})
    if isinstance(downloaded, UploadOutcome):
        return _outcome("UNKNOWN", "download-interrupted", file_id, digest, size)
    if downloaded.status_code != 200:
        detail = "download-interrupted" if downloaded.status_code >= 500 else "http-%d" % downloaded.status_code
        return _outcome("UNKNOWN" if downloaded.status_code >= 500 else "FAILED", detail, file_id, digest, size)
    if hashlib.sha256(downloaded.body).hexdigest() != digest or len(downloaded.body) != size:
        return _outcome("FAILED", "sha256-mismatch", file_id, digest, size)
    if attempt_dir:
        dest = os.path.join(attempt_dir, "download.age")
        if not os.path.lexists(dest):
            try:
                _exclusive_write(dest, downloaded.body)
            except OSError:
                return _outcome("UNKNOWN", "local-write", file_id, digest, size)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return UploadOutcome(success, "downloaded-sha256", file_id, digest, True, False, size, stamp)


def _generate(transport, token) -> UploadOutcome:
    url = GENERATE_URL + "?" + urllib.parse.urlencode(
        (("count", "1"), ("space", "drive"), ("type", "files"), ("fields", "ids,space,kind"))
    )
    response = _send(transport, "GET", url, token, b"", {})
    if isinstance(response, UploadOutcome):
        return response
    if response.status_code in (401, 403, 429):
        return _outcome("FAILED", "http-%d" % response.status_code, "", "", 0)
    if response.status_code != 200:
        status = "UNKNOWN" if response.status_code >= 500 else "FAILED"
        return _outcome(status, "http-%d" % response.status_code, "", "", 0)
    try:
        parsed = json.loads(response.body.decode("utf-8"))
        file_id = parsed["ids"][0]
    except (UnicodeError, json.JSONDecodeError, KeyError, IndexError, TypeError):
        return _outcome("UNKNOWN", "unreadable-response", "", "", 0)
    if not _file_id(file_id):
        return _outcome("FAILED", "invalid-file-id", "", "", 0)
    return _outcome("SUCCESS", "generated", file_id, "", 0)


def _query(transport, token, location, total):
    response = _send(
        transport,
        "PUT",
        location,
        token,
        b"",
        {"Content-Range": "bytes */%d" % total},
    )
    if isinstance(response, UploadOutcome):
        return response.detail
    if response.status_code == 404:
        return "EXPIRED"
    if response.status_code in (200, 201):
        return "COMPLETE"
    if response.status_code == 308:
        header = _header(response, "Range")
        if not header:
            return 0
        try:
            return _ack_offset(header, total)
        except ValueError:
            return "ack-rejected"
    if response.status_code >= 500:
        return "http-500"
    return "http-%d" % response.status_code


def _send(transport, method, url, token, body, extra):
    if request_is_destructive(method, url):
        return _outcome("FAILED", "prohibited-request", "", "", 0)
    headers = {"Authorization": "Bearer " + token, "Content-Length": str(len(body))}
    headers.update(extra)
    request = HttpRequest(method, url, headers, body)
    try:
        response = transport.send(request)
    except AmbiguousTransportError as exc:
        return _outcome("UNKNOWN", _safe_detail(exc.detail), "", "", 0)
    except Exception as exc:
        detail = getattr(exc, "detail", "transport-error")
        return _outcome("UNKNOWN", _safe_detail(detail), "", "", 0)
    return response


def _metadata_problem(meta: dict, reservation: dict) -> str:
    if meta.get("id") != reservation["file_id"]:
        return "metadata-mismatch"
    if meta.get("name") != reservation["name"]:
        return "metadata-mismatch"
    if meta.get("mimeType") != FILE_MIME:
        return "metadata-mismatch"
    if str(meta.get("size")) != str(reservation["size"]):
        return "metadata-mismatch"
    parents = meta.get("parents")
    if parents != [reservation["folder_id"]]:
        return "metadata-mismatch"
    return ""


def _meta(reservation: dict) -> dict:
    return {
        "id": reservation["file_id"],
        "mimeType": FILE_MIME,
        "name": reservation["name"],
        "parents": [reservation["folder_id"]],
    }


def _multipart_body(meta: dict, payload: bytes) -> tuple[str, str]:
    encoded = json.dumps(meta, separators=(",", ":")).encode("utf-8")
    boundary = "lgdrive" + hashlib.sha256(encoded + payload).hexdigest()
    while boundary.encode("ascii") in payload:
        boundary = "x" + boundary
    token = boundary.encode("ascii")
    parts = [
        b"--" + token,
        b"Content-Type: application/json; charset=UTF-8",
        b"",
        encoded,
        b"--" + token,
        b"Content-Type: application/octet-stream",
        b"",
        payload,
        b"--" + token + b"--",
        b"",
    ]
    return b"\r\n".join(parts), "multipart/related; boundary=" + boundary


def _inspect(path: str):
    try:
        handle = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0))
    except OSError:
        return _outcome("FAILED", "unreadable-ciphertext", "", "", 0)
    digest = hashlib.sha256()
    size = 0
    prefix = b""
    try:
        while True:
            piece = os.read(handle, CHUNK)
            if not piece:
                break
            if not prefix:
                prefix = piece[:32]
            size += len(piece)
            if size > MAX_CIPHERTEXT:
                return _outcome("FAILED", "too-large", "", "", 0)
            digest.update(piece)
    finally:
        os.close(handle)
    if prefix.startswith(b"SQLite format 3"):
        return _outcome("FAILED", "plaintext-refused", "", "", size)
    if not prefix.startswith(b"age-encryption.org/"):
        return _outcome("FAILED", "bad-header", "", "", size)
    return digest.hexdigest(), size


def _ack_offset(range_header: str, total: int) -> int:
    if not range_header.startswith("bytes=0-"):
        raise ValueError("range")
    last = int(range_header.removeprefix("bytes=0-"))
    if last < 0 or last >= total:
        raise ValueError("range")
    return last + 1


def _header(response, name: str) -> str:
    for key, value in (response.headers or {}).items():
        if key.lower() == name.lower():
            return value
    return ""


def _checkpoint_index(name: str) -> int | None:
    prefix = "progress-"
    suffix = ".json"
    if not name.startswith(prefix) or not name.endswith(suffix):
        return None
    digits = name[len(prefix):-len(suffix)]
    if len(digits) < 2 or not digits.isdigit():
        return None
    index = int(digits)
    if index < 1 or digits != "%02d" % index:
        return None
    return index


def _write_progress(attempt_dir: str, location: str, file_id: str, acked: int) -> None:
    names = _progress_names(attempt_dir)
    index = 1 if not names else (_checkpoint_index(names[-1]) or 0) + 1
    filename = "progress-%02d.json" % index
    if _checkpoint_index(filename) != index:
        raise ValueError("progress-rejected")
    path = os.path.join(attempt_dir, filename)
    if os.path.basename(path) != filename:
        raise ValueError("progress-rejected")
    _exclusive_json(path, {"acked": acked, "file_id": file_id, "session_uri": location})


def _progress_names(attempt_dir: str) -> list[str]:
    try:
        found = os.listdir(attempt_dir)
    except OSError:
        return []
    chosen = []
    for name in found:
        if "/" in name or "\\" in name or name in {".", ".."}:
            continue
        if not (name.startswith("progress-") and name.endswith(".json")):
            continue
        index = _checkpoint_index(name)
        if index is None or os.path.islink(os.path.join(attempt_dir, name)):
            raise ValueError("progress-rejected")
        chosen.append((index, name))
    chosen.sort()
    return [name for _index, name in chosen]


def _stamp(outcome: UploadOutcome, reservation: dict) -> UploadOutcome:
    return _outcome(outcome.status, outcome.detail, reservation["file_id"], reservation["sha256"], int(reservation["size"]))


def _outcome(status: str, detail: str, file_id: str, digest: str, size: int) -> UploadOutcome:
    verified = status in {"VERIFIED", "RECONCILED"} and detail == "downloaded-sha256"
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) if verified else ""
    return UploadOutcome(status, detail, file_id, digest, verified, False, size, stamp)


def _safe_detail(detail: str) -> str:
    text = str(detail or "ambiguous")
    if 1 <= len(text) <= 40 and set(text) <= _DETAIL:
        return text
    return "ambiguous"


def _file_id(value: str) -> bool:
    if not 10 <= len(value) <= 128:
        return False
    return all(char.isalnum() or char in "_-" for char in value)


def _plain_name(name: str) -> bool:
    if not name or name in {".", ".."} or "/" in name or "\\" in name:
        return False
    return len(name) <= 200


def _read_json(path: str):
    if os.path.islink(path) or not os.path.isfile(path):
        return None
    try:
        return json.loads(_read_file(path, 65536).decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None


def _read_file(path: str, limit: int) -> bytes:
    handle = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0))
    try:
        return os.read(handle, limit + 1)
    finally:
        os.close(handle)


def _exclusive_json(path: str, payload: dict) -> None:
    _exclusive_write(path, json.dumps(payload, sort_keys=True).encode("utf-8") + b"\n")


def _exclusive_write(path: str, payload: bytes) -> None:
    if os.path.islink(path) or os.path.islink(os.path.dirname(path)):
        raise FileExistsError(path)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    handle = os.open(path, flags, 0o600)
    try:
        try:
            os.fchmod(handle, 0o600)
        except OSError:
            pass
        os.write(handle, payload)
    finally:
        os.close(handle)


def _exists(path: str) -> bool:
    if os.path.islink(path):
        return True
    return os.path.isfile(path)
