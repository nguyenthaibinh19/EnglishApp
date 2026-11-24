"""Local emergency credential for offline Emergency Exit.

The secret is generated on this machine and protected with Windows DPAPI for
the current user. It lives under the validated data root, outside account
settings, and is never synced. Tests inject a protection double. Production
does not implement its own cipher.
"""

from __future__ import annotations

import base64
import hmac
import json
import os
import sys
from dataclasses import dataclass

import config

VERSION = 1
MAIN_NAME = "emergency_credential.json"
PENDING_NAME = "emergency_credential.pending.json"
DPAPI_NAME = "dpapi-current-user"
# CRYPTPROTECT_UI_FORBIDDEN. CRYPTPROTECT_LOCAL_MACHINE (0x04) is intentionally absent.
DPAPI_FLAGS = 0x01


class EmergencyCredentialError(RuntimeError):
    """The local emergency credential cannot be used."""


class CredentialEstablished(EmergencyCredentialError):
    """An acknowledged credential already exists and must not be replaced."""


class CredentialUnreadable(EmergencyCredentialError):
    """The stored credential is missing, corrupt, or cannot be unprotected."""


class CredentialUnavailable(EmergencyCredentialError):
    """This process has no current-user protection available."""


class RecoveryRefused(EmergencyCredentialError):
    """Recovery was requested while screen lock is active."""


@dataclass(frozen=True)
class _Record:
    protection: str
    blob: bytes
    acknowledged: bool


_test_protection = None


def set_protection_for_tests(protection) -> None:
    """Install a protection double. Production code never calls this."""
    global _test_protection
    _test_protection = protection


def active_protection():
    if _test_protection is not None:
        return _test_protection
    if os.name == "nt":
        return WindowsCurrentUserDpapi()
    raise CredentialUnavailable(
        "Emergency credential protection requires Windows DPAPI for the current user."
    )


class WindowsCurrentUserDpapi:
    """CryptProtectData for the current Windows user. Not machine-wide."""

    name = DPAPI_NAME
    FLAGS = DPAPI_FLAGS

    def protect(self, plaintext: bytes) -> bytes:
        return _dpapi(plaintext, protect=True)

    def unprotect(self, protected: bytes) -> bytes:
        return _dpapi(protected, protect=False)


def _dpapi(payload: bytes, *, protect: bool) -> bytes:
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_char)),
        ]

    if not payload:
        raise CredentialUnreadable("DPAPI received an empty buffer.")
    source = ctypes.create_string_buffer(payload)
    blob_in = DATA_BLOB(len(payload), ctypes.cast(source, ctypes.POINTER(ctypes.c_char)))
    blob_out = DATA_BLOB()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    signature = [
        ctypes.POINTER(DATA_BLOB),
        wintypes.LPCWSTR,
        ctypes.POINTER(DATA_BLOB),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(DATA_BLOB),
    ]
    function = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    function.argtypes = signature
    function.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    ok = function(
        ctypes.byref(blob_in),
        None,
        None,
        None,
        None,
        DPAPI_FLAGS,
        ctypes.byref(blob_out),
    )
    if not ok:
        raise CredentialUnreadable("DPAPI could not process the emergency credential.")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        kernel32.LocalFree(blob_out.pbData)


def credential_path() -> str:
    return os.path.join(config.data_dir(), MAIN_NAME)


def _pending_path() -> str:
    return os.path.join(config.data_dir(), PENDING_NAME)


def status() -> str:
    """missing, unacknowledged, acknowledged, or unreadable."""
    record = _load(credential_path())
    if record is None:
        return "missing"
    try:
        _secret_from(record)
    except EmergencyCredentialError:
        return "unreadable"
    return "acknowledged" if record.acknowledged else "unacknowledged"


def lock_allowed() -> bool:
    """True only when an acknowledged credential decrypts on this machine."""
    if status() != "acknowledged":
        return False
    try:
        secret = _secret_from(_load(credential_path()))
    except EmergencyCredentialError:
        return False
    return bool(secret)


def screen_lock_enabled(argv=None) -> bool:
    """Screen lock follows --lock only after the local credential is usable."""
    args = list(sys.argv if argv is None else argv)
    return "--lock" in args and lock_allowed()


def begin_or_resume() -> str:
    """Return the secret to show. Create one only when no credential file exists."""
    state = status()
    if state == "acknowledged":
        raise CredentialEstablished("An emergency credential is already enrolled.")
    if state == "unacknowledged":
        return _secret_from(_load(credential_path()))
    if state == "unreadable":
        raise CredentialUnreadable("The stored emergency credential cannot be read.")
    return _create(credential_path(), acknowledged=False)


def acknowledge_current(typed: str) -> bool:
    """Mark the current credential acknowledged after a successful local check."""
    if status() != "unacknowledged":
        return False
    record = _load(credential_path())
    if record is None or not _matches(typed, _secret_from(record)):
        return False
    _write(credential_path(), record.blob, acknowledged=True, protection=record.protection)
    return lock_allowed()


def cancel_enrollment() -> None:
    """Drop an interrupted enrollment. An acknowledged credential stays."""
    if status() == "unacknowledged":
        _remove(credential_path())


def validate_offline(typed: str) -> bool:
    """Compare a typed code with the enrolled secret. No network access."""
    if not lock_allowed():
        return False
    record = _load(credential_path())
    if record is None:
        return False
    try:
        secret = _secret_from(record)
    except EmergencyCredentialError:
        return False
    return _matches(typed, secret)


def reveal_outside_lock(*, lock_active: bool) -> str:
    """Show the enrolled secret again. Refused while screen lock is active."""
    if lock_active:
        raise RecoveryRefused("Recovery is unavailable while screen lock is active.")
    if not lock_allowed():
        raise CredentialUnreadable("No usable emergency credential is enrolled.")
    return _secret_from(_load(credential_path()))


def start_reenrollment(*, lock_active: bool, replace_existing: bool) -> str:
    """Write a pending credential. The current file stays until it is committed."""
    if lock_active:
        raise RecoveryRefused("Re-enrollment is unavailable while screen lock is active.")
    if lock_allowed() and not replace_existing:
        raise CredentialEstablished("An emergency credential is already enrolled.")
    return _create(_pending_path(), acknowledged=False)


def commit_reenrollment(typed: str) -> bool:
    """Replace the current credential only after the pending one is verified."""
    pending = _load(_pending_path())
    if pending is None:
        return False
    try:
        secret = _secret_from(pending)
    except EmergencyCredentialError:
        return False
    if not _matches(typed, secret):
        return False
    _write(_pending_path(), pending.blob, acknowledged=True, protection=pending.protection)
    os.replace(_pending_path(), credential_path())
    return lock_allowed()


def cancel_reenrollment() -> None:
    """Delete only the pending file. The current credential stays."""
    _remove(_pending_path())


def _create(path: str, *, acknowledged: bool) -> str:
    import secrets

    protector = active_protection()
    secret = secrets.token_urlsafe(18)
    blob = protector.protect(secret.encode("utf-8"))
    if not _matches(protector.unprotect(blob).decode("utf-8"), secret):
        raise CredentialUnreadable("The emergency credential could not be verified.")
    _write(path, blob, acknowledged=acknowledged, protection=protector.name)
    stored = _secret_from(_load(path))
    if not _matches(stored, secret):
        _remove(path)
        raise CredentialUnreadable("The emergency credential could not be verified.")
    return secret


def _matches(typed: str, secret: str) -> bool:
    if not isinstance(typed, str) or not isinstance(secret, str):
        return False
    left = typed.strip().encode("utf-8")
    right = secret.encode("utf-8")
    if not left or not right or len(left) != len(right):
        return False
    return hmac.compare_digest(left, right)


def _secret_from(record: _Record | None) -> str:
    if record is None:
        raise CredentialUnreadable("The emergency credential is missing.")
    protector = active_protection()
    if record.protection != protector.name:
        raise CredentialUnreadable("The emergency credential uses unavailable protection.")
    try:
        raw = protector.unprotect(record.blob)
        secret = raw.decode("utf-8")
    except EmergencyCredentialError:
        raise
    except Exception as error:
        raise CredentialUnreadable("The emergency credential cannot be read.") from error
    if not secret.strip():
        raise CredentialUnreadable("The emergency credential is empty.")
    return secret


def _load(path: str) -> _Record | None:
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError, UnicodeError):
        return _unreadable()
    if not isinstance(payload, dict) or payload.get("version") != VERSION:
        return _unreadable()
    if not isinstance(payload.get("acknowledged"), bool):
        return _unreadable()
    protection = payload.get("protection")
    blob_text = payload.get("blob")
    if not isinstance(protection, str) or not isinstance(blob_text, str):
        return _unreadable()
    try:
        blob = base64.b64decode(blob_text.encode("ascii"), validate=True)
    except (ValueError, UnicodeError):
        return _unreadable()
    if not blob:
        return _unreadable()
    return _Record(protection=protection, blob=blob, acknowledged=payload["acknowledged"])


def _unreadable() -> _Record:
    return _Record(protection="", blob=b"\x00", acknowledged=False)


def _write(path: str, blob: bytes, *, acknowledged: bool, protection: str) -> None:
    folder = os.path.dirname(path)
    os.makedirs(folder or config.data_dir(), exist_ok=True)
    payload = {
        "version": VERSION,
        "protection": protection,
        "blob": base64.b64encode(blob).decode("ascii"),
        "acknowledged": bool(acknowledged),
    }
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass
