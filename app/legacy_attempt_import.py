"""Read-only import of guest AttemptHistory into one account ledger.

The guest JSONL file is never opened for writing. Consent is per account and
per Windows file identity. Vocabulary consent does not authorize this import.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Callable, Dict, List, Optional, Tuple

from account_local_store import (
    LEGACY_DISP_CONFLICT,
    LEGACY_DISP_IMPORTED,
    LEGACY_DISP_OVERLAP,
    LEGACY_DISP_SKIPPED,
    LEGACY_DISP_SKIPPED_OVERLAP,
    LEGACY_DISP_UNREADABLE,
    AccountLocalError,
    AccountLocalStore,
)
from vocab_identity import is_vocab_id

# Guest history is small. A larger file is refused rather than guessed.
_MAX_SOURCE_BYTES = 32 * 1024 * 1024

IdentityReader = Callable[[str], str]


class LegacySourceIdentityError(AccountLocalError):
    """The attempt file has no safe, stable Windows identity."""


def read_windows_file_identity(path: str) -> str:
    """Volume serial plus file index. Path and content hash are not identity."""
    identity, _data = read_windows_attempt_source(path)
    return identity


def read_windows_attempt_source(path: str) -> Tuple[str, bytes]:
    """Open one real file, reject reparse points, and return identity plus bytes."""
    if os.name != "nt":
        raise LegacySourceIdentityError("Windows file identity is unavailable.")
    if os.path.islink(path):
        raise LegacySourceIdentityError("Refusing a reparse-point attempt source.")
    try:
        import ctypes
        from ctypes import wintypes
    except Exception as exc:
        raise LegacySourceIdentityError("Windows file identity is unavailable.") from exc

    kernel = ctypes.windll.kernel32
    _assert_no_reparse_component(kernel, path)
    reparse = 0x400

    generic_read = 0x80000000
    share_all = 0x1 | 0x2 | 0x4
    open_existing = 3
    open_reparse = 0x00200000
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    handle = kernel.CreateFileW(
        str(path),
        generic_read,
        share_all,
        None,
        open_existing,
        open_reparse,
        None,
    )
    invalid_handle = wintypes.HANDLE(-1).value
    if handle is None or handle == invalid_handle:
        raise LegacySourceIdentityError("Windows file identity is unavailable.")
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]

    class _FileTime(ctypes.Structure):
        _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]

    class _ByHandle(ctypes.Structure):
        _fields_ = [
            ("dwFileAttributes", wintypes.DWORD),
            ("ftCreationTime", _FileTime),
            ("ftLastAccessTime", _FileTime),
            ("ftLastWriteTime", _FileTime),
            ("dwVolumeSerialNumber", wintypes.DWORD),
            ("nFileSizeHigh", wintypes.DWORD),
            ("nFileSizeLow", wintypes.DWORD),
            ("nNumberOfLinks", wintypes.DWORD),
            ("nFileIndexHigh", wintypes.DWORD),
            ("nFileIndexLow", wintypes.DWORD),
        ]

    try:
        info = _ByHandle()
        kernel.GetFileInformationByHandle.restype = wintypes.BOOL
        kernel.GetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
        kernel.ReadFile.restype = wintypes.BOOL
        kernel.ReadFile.argtypes = [
            wintypes.HANDLE,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.c_void_p,
        ]
        kernel.CloseHandle.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        if not kernel.GetFileInformationByHandle(handle, ctypes.byref(info)):
            raise LegacySourceIdentityError("Windows file identity is unavailable.")
        if info.dwFileAttributes & reparse:
            raise LegacySourceIdentityError("Refusing a reparse-point attempt source.")
        serial = int(info.dwVolumeSerialNumber)
        index = (int(info.nFileIndexHigh) << 32) | int(info.nFileIndexLow)
        if serial == 0 and index == 0:
            raise LegacySourceIdentityError("Windows file identity is unavailable.")
        size = (int(info.nFileSizeHigh) << 32) | int(info.nFileSizeLow)
        if size > _MAX_SOURCE_BYTES:
            raise LegacySourceIdentityError("Attempt source is too large to import safely.")
        if size:
            buffer = ctypes.create_string_buffer(size)
            read = wintypes.DWORD()
            ok = kernel.ReadFile(handle, buffer, size, ctypes.byref(read), None)
            if not ok:
                raise LegacySourceIdentityError("Windows file identity is unavailable.")
            data = buffer.raw[: int(read.value)]
        else:
            data = b""
        identity = f"win:{serial:08x}:{index:016x}"
        return identity, data
    finally:
        kernel.CloseHandle(handle)


def import_guest_attempts(
    store: AccountLocalStore,
    *,
    language_code: str,
    path: str,
    identity_reader: Optional[IdentityReader] = None,
    resolutions: Optional[Dict[int, str]] = None,
) -> dict:
    """Import complete lines from one guest attempts file into ``store``.

    ``identity_reader`` is a test seam. Production uses the Windows volume
    serial and file index. A failure imports nothing.
    """
    language_code = str(language_code or "").strip().lower()
    source_path = os.path.abspath(path)
    try:
        if identity_reader is None:
            identity, data = read_windows_attempt_source(source_path)
        else:
            identity = str(identity_reader(source_path) or "").strip()
            if not identity:
                raise LegacySourceIdentityError("Windows file identity is unavailable.")
            with open(source_path, "rb") as handle:
                data = handle.read(_MAX_SOURCE_BYTES + 1)
            if len(data) > _MAX_SOURCE_BYTES:
                raise LegacySourceIdentityError("Attempt source is too large to import safely.")
    except (OSError, LegacySourceIdentityError):
        store.note_legacy_attempt_conflict(f"identity_unavailable {language_code}")
        return _result("identity_unavailable", identity="", imported=0)
    return import_attempt_bytes(
        store,
        language_code=language_code,
        canonical_path=source_path,
        file_identity=identity,
        data=data,
        resolutions=resolutions or {},
    )


def import_attempt_bytes(
    store: AccountLocalStore,
    *,
    language_code: str,
    canonical_path: str,
    file_identity: str,
    data: bytes,
    resolutions: Optional[Dict[int, str]] = None,
) -> dict:
    language_code = language_code.strip().lower()
    identity = str(file_identity)
    resolutions = resolutions or {}
    if not store.has_attempt_import_consent(language_code, identity):
        known = {
            str(row["file_identity"])
            for row in store.legacy_attempt_sources(language_code)
        }
        if known and identity not in known:
            store.note_legacy_attempt_conflict(f"replacement {language_code}")
            return _result("replacement_consent_required", identity=identity, imported=0)
        return _result("consent_required", identity=identity, imported=0)

    rows = store.legacy_attempt_ledger(identity)
    high = store.legacy_attempt_high_water(language_code, identity)
    if high > len(data) or any(int(row["offset"]) >= len(data) for row in rows):
        store.note_legacy_attempt_conflict(f"truncation {language_code}")
        return _result("conflict", identity=identity, imported=0, reason="truncation")

    for row in rows:
        digest = _line_digest(data, int(row["offset"]))
        if digest is None or digest != str(row["line_sha256"]):
            store.commit_legacy_attempt_line(
                language_code=language_code,
                canonical_path=canonical_path,
                file_identity=identity,
                offset=int(row["offset"]),
                line_sha256=digest or "",
                next_high_water=high,
                disposition=LEGACY_DISP_CONFLICT,
                move_high_water=False,
            )
            return _result(
                "conflict", identity=identity, imported=0, reason="source_conflict"
            )

    store.resolve_legacy_attempt_conflict(f"truncation {language_code}")
    store.resolve_legacy_attempt_conflict(f"source_conflict {language_code}")
    store.resolve_legacy_attempt_conflict(f"identity_unavailable {language_code}")
    parsed = _parse_new_lines(data, high, language_code, identity, store)
    unresolved = [
        item["offset"]
        for item in parsed
        if item["overlap"] and resolutions.get(item["offset"]) not in {"skip", "distinct"}
        and item["disposition"] == LEGACY_DISP_OVERLAP
    ]
    imported = 0
    if unresolved:
        for item in parsed:
            if not item["overlap"] or item["existing"]:
                continue
            store.commit_legacy_attempt_line(
                language_code=language_code,
                canonical_path=canonical_path,
                file_identity=identity,
                offset=item["offset"],
                line_sha256=item["digest"],
                next_high_water=high,
                disposition=LEGACY_DISP_OVERLAP,
                move_high_water=False,
            )
        store.note_legacy_attempt_conflict(f"overlap {language_code}")
        return _result(
            "overlap",
            identity=identity,
            imported=0,
            overlap_offsets=unresolved,
            reason="overlap",
        )

    water = high
    for item in parsed:
        if item["offset"] != water:
            break
        choice = resolutions.get(item["offset"])
        if item["overlap"] and item["disposition"] == LEGACY_DISP_OVERLAP:
            if item["existing"]:
                event_id = store.reconcile_legacy_overlap_line(
                    language_code=language_code,
                    file_identity=identity,
                    offset=item["offset"],
                    line_sha256=item["digest"],
                    choice=choice or "skip",
                    event=item["event"],
                    next_high_water=item["end"],
                )
            elif choice == "distinct" and item["event"] is not None:
                event_id = store.commit_legacy_attempt_line(
                    language_code=language_code,
                    canonical_path=canonical_path,
                    file_identity=identity,
                    offset=item["offset"],
                    line_sha256=item["digest"],
                    next_high_water=item["end"],
                    disposition=LEGACY_DISP_IMPORTED,
                    event=item["event"],
                    move_high_water=True,
                )
            else:
                event_id = store.commit_legacy_attempt_line(
                    language_code=language_code,
                    canonical_path=canonical_path,
                    file_identity=identity,
                    offset=item["offset"],
                    line_sha256=item["digest"],
                    next_high_water=item["end"],
                    disposition=LEGACY_DISP_SKIPPED_OVERLAP,
                    move_high_water=True,
                )
            if choice == "distinct" and event_id:
                imported += 1
        elif item["existing"]:
            pass
        else:
            event_id = store.commit_legacy_attempt_line(
                language_code=language_code,
                canonical_path=canonical_path,
                file_identity=identity,
                offset=item["offset"],
                line_sha256=item["digest"],
                next_high_water=item["end"],
                disposition=item["disposition"],
                event=item["event"],
                move_high_water=True,
            )
            if item["disposition"] == LEGACY_DISP_IMPORTED and event_id:
                imported += 1
        water = item["end"]
    if not unresolved:
        store.resolve_legacy_attempt_conflict(f"overlap {language_code}")
    return _result("ok", identity=identity, imported=imported)


def _parse_new_lines(
    data: bytes,
    high: int,
    language_code: str,
    identity: str,
    store: AccountLocalStore,
) -> List[dict]:
    rows = {
        int(row["offset"]): row for row in store.legacy_attempt_ledger(identity)
    }
    parsed: List[dict] = []
    for offset, raw, end in _complete_lines(data, high):
        digest = hashlib.sha256(raw).hexdigest()
        existing = rows.get(offset)
        if existing is not None:
            disposition = str(existing["disposition"])
            overlap = disposition == LEGACY_DISP_OVERLAP
            parsed.append(
                {
                    "offset": offset,
                    "end": end,
                    "digest": digest,
                    "existing": True,
                    "overlap": overlap,
                    "disposition": disposition,
                    "event": _event_from_line(raw, language_code) if overlap else None,
                }
            )
            continue
        action, event = _classify_line(raw, language_code)
        overlap = bool(event) and store.legacy_hash_on_other_identity(digest, identity)
        if overlap:
            action = LEGACY_DISP_OVERLAP
        parsed.append(
            {
                "offset": offset,
                "end": end,
                "digest": digest,
                "existing": False,
                "overlap": overlap,
                "disposition": action,
                "event": event,
            }
        )
    return parsed


def _event_from_line(raw: bytes, language_code: str) -> Optional[dict]:
    _action, event = _classify_line(raw, language_code)
    return event


def _assert_no_reparse_component(kernel, path: str) -> None:
    """Reject a reparse point on the file or any ancestor.

    Checking only the final file follows a directory junction and reports the
    target. The guest path is ``.../attempts.jsonl``, so each existing
    component has to be a real directory or the real file.
    """
    from ctypes import wintypes

    invalid_attributes = 0xFFFFFFFF
    reparse = 0x400
    kernel.GetFileAttributesW.restype = wintypes.DWORD
    kernel.GetFileAttributesW.argtypes = [wintypes.LPCWSTR]
    current = os.path.abspath(path)
    seen = set()
    while current and current not in seen:
        seen.add(current)
        if os.path.islink(current):
            raise LegacySourceIdentityError("Refusing a reparse-point attempt source.")
        attributes = kernel.GetFileAttributesW(current)
        if attributes == invalid_attributes or attributes & reparse:
            raise LegacySourceIdentityError("Refusing a reparse-point attempt source.")
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent


def _flag_bit(value) -> Optional[int]:
    """Guest JSON uses booleans. The server stores 0 or 1 and rejects other types."""
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, int) and value in (0, 1):
        return value
    return None


def _classify_line(raw: bytes, language_code: str) -> Tuple[str, Optional[dict]]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return LEGACY_DISP_UNREADABLE, None
    if text.endswith("\n"):
        text = text[:-1]
    if text.endswith("\r"):
        text = text[:-1]
    try:
        body = json.loads(text)
    except json.JSONDecodeError:
        return LEGACY_DISP_UNREADABLE, None
    if not isinstance(body, dict):
        return LEGACY_DISP_UNREADABLE, None
    from sync_store import (
        SyncValidationError,
        _reject_forbidden_keys,
        _require_event_id,
        _require_language,
        _validate_progress_event,
    )

    try:
        _reject_forbidden_keys(body, path="event")
    except SyncValidationError:
        return LEGACY_DISP_UNREADABLE, None
    verdict_raw = body.get("verdict")
    if not isinstance(verdict_raw, str):
        return LEGACY_DISP_UNREADABLE, None
    verdict = verdict_raw.strip().lower()
    if verdict not in {"exact", "near", "wrong"}:
        return LEGACY_DISP_UNREADABLE, None
    if "hint_used" in body:
        hint_used = _flag_bit(body.get("hint_used"))
        if hint_used is None:
            return LEGACY_DISP_UNREADABLE, None
    else:
        hint_used = 0
    mastered = 1 if verdict == "exact" and hint_used == 0 else 0
    if "correct" not in body:
        return LEGACY_DISP_UNREADABLE, None
    correct = _flag_bit(body.get("correct"))
    if correct is None or correct != mastered:
        return LEGACY_DISP_UNREADABLE, None
    if "algorithm_id" in body:
        algorithm = body.get("algorithm_id")
    elif "algorithm_version" in body:
        algorithm = body.get("algorithm_version")
    else:
        algorithm = "ladder-v2"
    if algorithm in (None, ""):
        algorithm = "ladder-v2"
    if not isinstance(algorithm, str) or algorithm != "ladder-v2":
        return LEGACY_DISP_UNREADABLE, None
    if "timestamp" in body:
        raw_time = body.get("timestamp")
    else:
        raw_time = body.get("occurred_at")
    if not isinstance(raw_time, str):
        return LEGACY_DISP_UNREADABLE, None
    try:
        line_language = _require_language(body.get("language_code") or language_code)
    except SyncValidationError:
        return LEGACY_DISP_UNREADABLE, None
    if line_language != str(language_code or "").strip().lower():
        return LEGACY_DISP_UNREADABLE, None
    texts = _guest_text_fields(body)
    if texts is None:
        return LEGACY_DISP_UNREADABLE, None
    supplied_device = body.get("device_id", "")
    if supplied_device in (None, ""):
        device_for_check = "legacy-import-device"
        stored_device = ""
    else:
        try:
            stored_device = _require_event_id(supplied_device, name="device_id")
        except SyncValidationError:
            return LEGACY_DISP_UNREADABLE, None
        device_for_check = stored_device
    vocab_raw = body.get("vocab_id", "")
    vocab_id = vocab_raw.strip() if isinstance(vocab_raw, str) else ""
    if not is_vocab_id(vocab_id):
        return LEGACY_DISP_SKIPPED, None
    try:
        prepared = _validate_progress_event(
            {
                "event_id": "00000000-0000-4000-8000-000000000001",
                "device_id": device_for_check,
                "language_code": line_language,
                "vocab_id": vocab_id,
                "verdict": verdict,
                "mastered": mastered,
                "hint_used": hint_used,
                "occurred_at": raw_time,
                "algorithm_id": algorithm,
                "word_snapshot": texts["word_snapshot"],
                "user_answer": texts["user_answer"],
                "expected_answer": texts["expected_answer"],
                "prompt": texts["prompt"],
            }
        )
    except SyncValidationError:
        return LEGACY_DISP_UNREADABLE, None
    return LEGACY_DISP_IMPORTED, {
        "vocab_id": prepared["vocab_id"],
        "language_code": prepared["language_code"],
        "verdict": prepared["verdict"],
        "hint_used": bool(prepared["hint_used"]),
        "occurred_at": prepared["occurred_at"],
        "word_snapshot": prepared["word_snapshot"],
        "user_answer": prepared["user_answer"],
        "expected_answer": prepared["expected_answer"],
        "prompt": prepared["prompt"],
        "device_id": stored_device,
    }


def _guest_text_fields(body: dict) -> Optional[dict]:
    """Map guest keys onto the server text fields. Non-strings are unreadable."""
    if "word" in body:
        word = body.get("word")
    else:
        word = body.get("word_snapshot", "")
    values = {
        "word_snapshot": word,
        "user_answer": body.get("user_answer", "") if "user_answer" in body else "",
        "expected_answer": body.get("expected_answer", "") if "expected_answer" in body else "",
        "prompt": body.get("prompt", "") if "prompt" in body else "",
    }
    if "word" in body and not isinstance(body.get("word"), str):
        return None
    if "word" not in body and "word_snapshot" in body and not isinstance(body.get("word_snapshot"), str):
        return None
    for key in ("user_answer", "expected_answer", "prompt"):
        if key in body and not isinstance(body.get(key), str):
            return None
    if not all(isinstance(value, str) for value in values.values()):
        return None
    return values


def _complete_lines(data: bytes, start: int) -> List[Tuple[int, bytes, int]]:
    lines: List[Tuple[int, bytes, int]] = []
    offset = max(0, int(start))
    while offset < len(data):
        newline = data.find(b"\n", offset)
        if newline < 0:
            break
        end = newline + 1
        lines.append((offset, data[offset:end], end))
        offset = end
    return lines


def _line_digest(data: bytes, offset: int) -> Optional[str]:
    if offset < 0 or offset >= len(data):
        return None
    newline = data.find(b"\n", offset)
    if newline < 0:
        return None
    return hashlib.sha256(data[offset : newline + 1]).hexdigest()


def _result(
    status: str,
    *,
    identity: str,
    imported: int,
    overlap_offsets: Optional[List[int]] = None,
    reason: str = "",
) -> dict:
    return {
        "status": status,
        "file_identity": identity,
        "imported": imported,
        "overlap_offsets": list(overlap_offsets or []),
        "reason": reason or status,
    }
