"""Fail-closed checks for an isolated staging account server.

Repository source only. This module does not create directories, change
permissions, open databases, or listen. A future staging unit may run it
before start. It is not installed by this phase.
"""

from __future__ import annotations

import json
import os
import re
import socket
import uuid
from dataclasses import dataclass

PRODUCTION_APP_ROOT = os.path.normcase(os.path.abspath("/opt/language-guard"))
PRODUCTION_BACKUP_ROOT = os.path.normcase(
    os.path.abspath("/var/backups/language-guard")
)
PRODUCTION_PORT = 8765
REQUIRED_BIND = "127.0.0.1"
STAGING_FAKE_API_KEY = "staging-fake-not-a-provider-key"
STAGING_FAKE_BASE_URL = "http://127.0.0.1:9"
_ALLOWED_SYNC_FLAGS = frozenset({"", "0", "1"})
_ENV_KEYS = (
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "ACCOUNT_BIND",
    "ACCOUNT_PORT",
    "STUDY_SYNC_DIR",
    "STUDY_SYNC_ENABLED",
)
_PROOF_NAME = re.compile(r"^effective-[0-9a-f]{32}\.json$")
_PROOF_FIELDS = ("base_url", "bind", "key_is_staging_fake", "port", "sync_enabled")


class StagingGuardError(Exception):
    """Staging configuration is not proven isolated."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class StagingLayout:
    """Paths and credentials the staging process intends to use."""

    bind: str
    port: int
    package_dir: str
    account_db: str
    sync_dir: str
    sync_db: str
    backup_dir: str
    verify_root: str
    env_file: str
    api_key: str
    proof_dir: str
    sync_enabled: str = "0"
    account_token: str = ""
    openai_base_url: str = STAGING_FAKE_BASE_URL


def validate(layout: StagingLayout, *, require_env_file: bool = False) -> None:
    """Reject an unsafe layout. Does not create or modify anything.

    An existing staging ``.env`` is always inspected. The file is required
    only when ``require_env_file`` is true, which is the server-start check.
    """
    if not isinstance(layout, StagingLayout):
        raise StagingGuardError("isolated")
    if layout.bind != REQUIRED_BIND:
        raise StagingGuardError("bind")
    _reject_port(layout.port)
    _reject_secrets(layout)
    paths = (
        layout.package_dir,
        layout.account_db,
        layout.sync_dir,
        layout.sync_db,
        layout.backup_dir,
        layout.verify_root,
        layout.env_file,
        layout.proof_dir,
    )
    if not all(paths):
        raise StagingGuardError("isolated")
    for path in paths:
        _reject_symlink_components(path)
        _reject_protected(path)
    _reject_overlap(layout)
    if os.path.lexists(layout.env_file):
        _validate_env_file(layout)
    elif require_env_file:
        raise StagingGuardError("env")
    if _port_is_occupied(layout.port):
        raise StagingGuardError("occupied")


def layout_from_environ(environ: dict | None = None) -> StagingLayout:
    """Build a layout from an explicit environment mapping."""
    env = os.environ if environ is None else environ
    package = (env.get("STAGING_PACKAGE_DIR") or "").strip()
    sync_dir = (env.get("STUDY_SYNC_DIR") or "").strip()
    try:
        port = int((env.get("ACCOUNT_PORT") or "").strip())
    except ValueError as error:
        raise StagingGuardError("port") from error
    return StagingLayout(
        bind=(env.get("ACCOUNT_BIND") or "").strip(),
        port=port,
        package_dir=package,
        account_db=os.path.join(package, "accounts.db") if package else "",
        sync_dir=sync_dir,
        sync_db=os.path.join(sync_dir, "study_sync.db") if sync_dir else "",
        backup_dir=(env.get("STUDY_SYNC_BACKUP_DIR") or "").strip(),
        verify_root=(env.get("STUDY_SYNC_VERIFY_DIR") or "").strip(),
        env_file=(env.get("STAGING_ENV_FILE") or "").strip(),
        proof_dir=(env.get("STAGING_PROOF_DIR") or "").strip(),
        api_key=(env.get("OPENAI_API_KEY") or "").strip(),
        sync_enabled=(env.get("STUDY_SYNC_ENABLED") or "").strip(),
        account_token=(env.get("ACCOUNT_TOKEN") or "").strip(),
        openai_base_url=(env.get("OPENAI_BASE_URL") or "").strip(),
    )


def validate_proof_path(layout: StagingLayout, proof_path: str) -> None:
    """Reject a proof path outside the layout's proof directory. No writes."""
    _assert_proof_location(layout, proof_path, partial=False)
    _assert_proof_location(layout, proof_path + ".partial", partial=True)


def allocate_proof_path(layout: StagingLayout) -> str:
    """Pick a new proof name. Does not create or delete a file."""
    if not layout.proof_dir or os.path.islink(layout.proof_dir) or not os.path.isdir(layout.proof_dir):
        raise StagingGuardError("proof")
    _reject_symlink_components(layout.proof_dir)
    for _ in range(5):
        candidate = os.path.join(layout.proof_dir, "effective-" + uuid.uuid4().hex + ".json")
        try:
            validate_proof_path(layout, candidate)
        except StagingGuardError:
            continue
        return candidate
    raise StagingGuardError("proof")


def write_proof(layout: StagingLayout, proof_path: str, *, sync_enabled: bool) -> None:
    """Create one proof file without following symlinks or replacing another file."""
    validate_proof_path(layout, proof_path)
    if layout.bind != REQUIRED_BIND:
        raise StagingGuardError("proof")
    body = {
        "base_url": STAGING_FAKE_BASE_URL,
        "bind": REQUIRED_BIND,
        "key_is_staging_fake": True,
        "port": layout.port,
        "sync_enabled": bool(sync_enabled),
    }
    if tuple(body) != _PROOF_FIELDS:
        raise StagingGuardError("proof")
    payload = json.dumps(body, sort_keys=True).encode("utf-8")
    if b"sk-" in payload or STAGING_FAKE_API_KEY.encode("utf-8") in payload:
        raise StagingGuardError("proof")
    temporary = proof_path + ".partial"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if nofollow:
        flags |= nofollow
    try:
        descriptor = os.open(temporary, flags, 0o600)
    except OSError:
        raise StagingGuardError("proof") from None
    try:
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    try:
        os.link(temporary, proof_path)
    except OSError:
        _discard_regular_temp(temporary)
        raise StagingGuardError("proof") from None
    _discard_regular_temp(temporary)


def main() -> int:
    """Pre-start check. Exit 1 without printing secrets or paths."""
    try:
        validate(layout_from_environ())
    except StagingGuardError as error:
        import sys

        sys.stderr.write("staging guard rejected\n")
        sys.stderr.write(error.code + "\n")
        return 1
    return 0


def _reject_port(port: object) -> None:
    if isinstance(port, bool) or not isinstance(port, int):
        raise StagingGuardError("port")
    if port == PRODUCTION_PORT or port < 1 or port > 65535:
        raise StagingGuardError("port")


def _reject_secrets(layout: StagingLayout) -> None:
    if layout.api_key != STAGING_FAKE_API_KEY or layout.api_key.startswith("sk-"):
        raise StagingGuardError("secret")
    if layout.account_token:
        raise StagingGuardError("secret")
    if layout.openai_base_url != STAGING_FAKE_BASE_URL:
        raise StagingGuardError("secret")
    if layout.sync_enabled not in _ALLOWED_SYNC_FLAGS:
        raise StagingGuardError("isolated")
    for value in (
        layout.api_key,
        layout.account_token,
        layout.openai_base_url,
        layout.sync_enabled,
    ):
        if "api.openai.com" in value.lower():
            raise StagingGuardError("secret")


def _reject_overlap(layout: StagingLayout) -> None:
    package = _canonical(layout.package_dir)
    account = _canonical(layout.account_db)
    sync_dir = _canonical(layout.sync_dir)
    sync_db = _canonical(layout.sync_db)
    backup = _canonical(layout.backup_dir)
    verify = _canonical(layout.verify_root)
    env_file = _canonical(layout.env_file)
    if account == sync_db or os.path.basename(account) != "accounts.db":
        raise StagingGuardError("overlap")
    if os.path.basename(sync_db) != "study_sync.db":
        raise StagingGuardError("overlap")
    if os.path.dirname(account) != package:
        raise StagingGuardError("overlap")
    if os.path.dirname(sync_db) != sync_dir:
        raise StagingGuardError("overlap")
    if os.path.basename(env_file) != ".env" or os.path.dirname(env_file) != package:
        raise StagingGuardError("overlap")
    proof = _canonical(layout.proof_dir)
    roots = (package, sync_dir, backup, verify, proof)
    for index, left in enumerate(roots):
        for right in roots[index + 1 :]:
            if left == right or _is_inside(left, right) or _is_inside(right, left):
                raise StagingGuardError("overlap")


def _reject_protected(path: str) -> None:
    real = _canonical(path)
    lexical = os.path.normcase(os.path.abspath(path))
    for root in (_app_root(), _backup_root()):
        if real == root or lexical == root or _is_inside(real, root) or _is_inside(lexical, root):
            raise StagingGuardError("protected")


def _reject_symlink_components(path: str) -> None:
    if _symlink_component(path):
        raise StagingGuardError("symlink")


def _symlink_component(path: str) -> bool:
    current = os.path.abspath(path)
    chain = []
    while True:
        parent = os.path.dirname(current)
        if parent == current:
            break
        chain.append(current)
        current = parent
    for candidate in reversed(chain):
        if os.path.islink(candidate):
            return True
        if not os.path.lexists(candidate):
            return False
    return False


def _app_root() -> str:
    return os.path.normcase(os.path.abspath(PRODUCTION_APP_ROOT))


def _backup_root() -> str:
    return os.path.normcase(os.path.abspath(PRODUCTION_BACKUP_ROOT))


def _canonical(path: str) -> str:
    return os.path.normcase(os.path.realpath(path))


def _is_inside(path: str, parent: str) -> bool:
    try:
        return os.path.commonpath([path, parent]) == parent and path != parent
    except ValueError:
        return False


def _validate_env_file(layout: StagingLayout) -> None:
    path = layout.env_file
    _reject_symlink_components(path)
    if os.path.islink(path) or not os.path.isfile(path):
        raise StagingGuardError("env")
    try:
        size = os.path.getsize(path)
    except OSError:
        raise StagingGuardError("env") from None
    if size <= 0 or size > 4096:
        raise StagingGuardError("env")
    flags = os.O_RDONLY
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if nofollow:
        flags |= nofollow
    try:
        descriptor = os.open(path, flags)
    except OSError:
        raise StagingGuardError("env") from None
    try:
        raw = os.read(descriptor, 4097)
    finally:
        os.close(descriptor)
    if len(raw) > 4096 or b"\x00" in raw:
        raise StagingGuardError("env")
    try:
        text = raw.decode("utf-8")
    except UnicodeError:
        raise StagingGuardError("env") from None
    found = {}
    for line in text.splitlines():
        if not line or line.startswith("#") or line.startswith("export ") or "=" not in line:
            raise StagingGuardError("env")
        key, value = line.split("=", 1)
        if key in found or key not in _ENV_KEYS:
            if "TOKEN" in key or "SECRET" in key or "PASSWORD" in key or key.endswith("_KEY"):
                raise StagingGuardError("secret")
            raise StagingGuardError("env")
        if any(item in value for item in ("\n", "\r", "\x00")) or "api.openai.com" in value.lower():
            raise StagingGuardError("secret" if "api.openai.com" in value.lower() else "env")
        found[key] = value
    if tuple(found) != _ENV_KEYS and set(found) != set(_ENV_KEYS):
        raise StagingGuardError("env")
    if found["OPENAI_API_KEY"] != STAGING_FAKE_API_KEY or found["OPENAI_API_KEY"].startswith("sk-"):
        raise StagingGuardError("secret")
    if found["OPENAI_BASE_URL"] != STAGING_FAKE_BASE_URL:
        raise StagingGuardError("secret")
    if found["ACCOUNT_BIND"] != REQUIRED_BIND:
        raise StagingGuardError("env")
    if found["ACCOUNT_PORT"] != str(layout.port) or not found["ACCOUNT_PORT"].isdigit():
        raise StagingGuardError("env")
    if found["STUDY_SYNC_ENABLED"] != layout.sync_enabled or found["STUDY_SYNC_ENABLED"] not in {"0", "1"}:
        raise StagingGuardError("env")
    if _canonical(found["STUDY_SYNC_DIR"]) != _canonical(layout.sync_dir):
        raise StagingGuardError("env")
    _reject_symlink_components(found["STUDY_SYNC_DIR"])


def _assert_proof_location(layout: StagingLayout, path: str, *, partial: bool) -> None:
    if not path or not layout.proof_dir:
        raise StagingGuardError("proof")
    _reject_symlink_components(layout.proof_dir)
    _reject_symlink_components(path)
    _reject_protected(path)
    if os.path.islink(path):
        raise StagingGuardError("symlink")
    if os.path.lexists(path):
        raise StagingGuardError("proof")
    if _canonical(os.path.dirname(path)) != _canonical(layout.proof_dir):
        raise StagingGuardError("proof")
    name = os.path.basename(path)
    if partial:
        if not name.endswith(".json.partial"):
            raise StagingGuardError("proof")
        name = name[: -len(".partial")]
    if _PROOF_NAME.match(name) is None:
        raise StagingGuardError("proof")
    real = _canonical(path)
    if real == _canonical(layout.proof_dir):
        raise StagingGuardError("proof")
    blocked = (
        layout.account_db,
        layout.sync_db,
        layout.env_file,
        layout.package_dir,
        layout.sync_dir,
        layout.backup_dir,
        layout.verify_root,
    )
    for item in blocked:
        other = _canonical(item)
        if real == other or _is_inside(real, other):
            raise StagingGuardError("proof")


def _discard_regular_temp(path: str) -> None:
    if os.path.islink(path) or not os.path.isfile(path):
        return
    try:
        os.unlink(path)
    except OSError:
        raise StagingGuardError("proof") from None


def _port_is_occupied(port: int) -> bool:
    """True when something accepts a loopback connection. Does not bind."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.settimeout(0.2)
    try:
        return probe.connect_ex((REQUIRED_BIND, port)) == 0
    finally:
        probe.close()


if __name__ == "__main__":
    raise SystemExit(main())
