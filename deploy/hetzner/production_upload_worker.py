#!/usr/bin/env python3
"""Production upload orchestration entrypoint (outside frozen offbox modules).

Fail-closed by default. Reuses ``backup_worker.run()`` with validated HTTPS
transport and OAuth refresh exchange only when deliberate activation
credentials are present under the systemd ``LoadCredential`` directory.

Does not modify frozen ``backup_worker.main()``. Secrets are read only from
credential files — never from environment values, argv, or logs.

Inactive encrypt-only completion records attempt state ``ENCRYPTED`` but exits
non-zero so systemd/monitoring never treat it as verified off-box success.
"""

from __future__ import annotations

import errno
import os
import re
import stat
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

# Resolve frozen offbox modules for both repo and installed layouts:
#   <root>/deploy/hetzner/production_upload_worker.py
#   <root>/offbox/*.py
_HERE = Path(__file__).resolve().parent
_OFFBOX_CANDIDATES = (
    _HERE / "offbox",
    _HERE.parent.parent / "offbox",
)
for _candidate in _OFFBOX_CANDIDATES:
    if (_candidate / "backup_worker.py").is_file():
        _offbox = str(_candidate)
        if _offbox not in sys.path:
            sys.path.insert(0, _offbox)
        break
else:
    raise SystemExit("offbox-modules-absent")

import backup_worker  # noqa: E402
import credential  # noqa: E402
import https_transport  # noqa: E402
import logutil  # noqa: E402
import oauth_exchange  # noqa: E402

sys.dont_write_bytecode = True

ACTIVATION_NAME = "upload-activation"
ACTIVATION_VALUE = "authorized"
CLIENT_ID_NAME = "oauth-client-id"
CLIENT_SECRET_NAME = "oauth-client-secret"
FOLDER_ID_NAME = "drive-folder-id"
ACTIVATION_ENTRY_NAMES = (
    ACTIVATION_NAME,
    FOLDER_ID_NAME,
    CLIENT_ID_NAME,
    CLIENT_SECRET_NAME,
)

# Documented LG_RESUME values only (absent/empty or exact "1").
_RESUME_ALLOWED = frozenset({"", "1"})

# Inactive encrypt-only completed: not off-box success (distinct from hard fail=1).
INACTIVE_NOT_OFFBOX_EXIT = 3

# Refuse secret-bearing or live-upload env knobs (credential files only).
_FORBIDDEN_ENV = (
    "LG_DRIVE_FOLDER",
    "LG_UPLOAD_ENABLED",
    "LG_OAUTH_CLIENT_ID",
    "LG_OAUTH_CLIENT_SECRET",
    "LG_OAUTH_REFRESH",
    "LG_REFRESH_TOKEN",
    "LG_CLIENT_ID",
    "LG_CLIENT_SECRET",
)

_FOLDER_ID_RE = re.compile(r"^[A-Za-z0-9_-]{10,128}$")
_CLIENT_ID_RE = re.compile(r"^[A-Za-z0-9._~+/-]+=*$")


@dataclass(frozen=True)
class UploadConfig:
    mode: str  # "inactive" | "upload"
    state_dir: str
    source_db: str
    socket_path: str
    recipient_file: str
    age_bin: str
    attempt_id: str
    resume: bool
    credential_dir: str
    folder_id: str
    client_id: str
    client_secret: str
    object_name: str


class ConfigError(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


def _cred_path(directory: str, name: str) -> str:
    return os.path.join(directory, name)


def _open_nofollow_readonly(path: str, *, detail: str) -> int:
    """Open a regular file without following symlinks when the OS supports it."""
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if nofollow:
        flags |= nofollow
    elif os.path.islink(path):
        raise ConfigError(detail)
    try:
        handle = os.open(path, flags)
    except OSError as exc:
        # ELOOP / EMLINK-style failures when O_NOFOLLOW hits a symlink.
        if getattr(exc, "errno", None) in {
            getattr(errno, "ELOOP", -1),
            getattr(errno, "EMLINK", -2),
            getattr(errno, "EACCES", -3),
        }:
            raise ConfigError(detail) from exc
        raise ConfigError(detail) from exc
    try:
        mode = os.fstat(handle).st_mode
        if not stat.S_ISREG(mode):
            os.close(handle)
            raise ConfigError(detail)
    except Exception:
        try:
            os.close(handle)
        except OSError:
            pass
        raise
    return handle


def probe_activation_entry(directory: str, name: str) -> bool:
    """Return True if a regular credential file exists.

    Symlinks (including dangling), directories and other non-regular entries
    raise ConfigError — never silent inactive fallback.
    """
    if not directory:
        return False
    path = _cred_path(directory, name)
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise ConfigError(f"{name}-rejected") from exc
    if stat.S_ISLNK(st.st_mode):
        raise ConfigError(f"{name}-symlink")
    if not stat.S_ISREG(st.st_mode):
        raise ConfigError(f"{name}-rejected")
    return True


def activation_entries_present(credential_dir: str) -> bool:
    """True if any activation-related entry exists; invalid types fail closed."""
    if not credential_dir:
        return False
    if os.path.islink(credential_dir):
        raise ConfigError("credential-dir-rejected")
    if not os.path.isdir(credential_dir):
        return False
    found = False
    for name in ACTIVATION_ENTRY_NAMES:
        if probe_activation_entry(credential_dir, name):
            found = True
    return found


def read_credential_file(
    directory: str,
    name: str,
    *,
    max_bytes: int,
    required: bool,
) -> str | None:
    """Read a LoadCredential file via no-follow open + fd type check."""
    if not directory or os.path.islink(directory):
        if required:
            raise ConfigError("credential-dir-absent")
        return None
    path = _cred_path(directory, name)
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        if required:
            raise ConfigError(f"{name}-absent")
        return None
    except OSError as exc:
        raise ConfigError(f"{name}-rejected") from exc
    if stat.S_ISLNK(st.st_mode):
        raise ConfigError(f"{name}-symlink")
    if not stat.S_ISREG(st.st_mode):
        raise ConfigError(f"{name}-rejected")
    try:
        handle = _open_nofollow_readonly(path, detail=f"{name}-rejected")
    except ConfigError:
        raise
    try:
        data = os.read(handle, max_bytes + 1)
    finally:
        os.close(handle)
    if len(data) > max_bytes:
        raise ConfigError(f"{name}-rejected")
    try:
        text = data.decode("ascii")
    except UnicodeError as exc:
        raise ConfigError(f"{name}-rejected") from exc
    text = text.strip()
    if not text:
        if required:
            raise ConfigError(f"{name}-absent")
        return None
    if any(char.isspace() for char in text):
        raise ConfigError(f"{name}-rejected")
    return text


def object_name_for(attempt_id: str) -> str:
    if not attempt_id or not backup_worker.attempt_store.safe_id(attempt_id):
        raise ConfigError("attempt-id")
    return f"accounts-{attempt_id}.age"


def parse_resume(env: dict[str, str]) -> bool:
    raw = env.get("LG_RESUME", "")
    if raw not in _RESUME_ALLOWED:
        raise ConfigError("resume-rejected")
    return raw == "1"


def load_config(
    environ: dict[str, str] | None = None,
    *,
    credential_dir: str | None = None,
) -> UploadConfig:
    env = environ if environ is not None else dict(os.environ)
    for key in _FORBIDDEN_ENV:
        if env.get(key):
            raise ConfigError("secret-env-forbidden")

    cred_dir = credential_dir if credential_dir is not None else env.get("CREDENTIALS_DIRECTORY", "")
    if cred_dir and os.path.islink(cred_dir):
        raise ConfigError("credential-dir-rejected")

    state_dir = env.get("LG_STATE_DIR", "/var/lib/language-guard-backup")
    source_db = env.get("LG_SOURCE_DB", "/opt/language-guard/accounts.db")
    socket_path = env.get("LG_SOCKET", "/run/language-guard-offbox/handoff.sock")
    recipient_file = env.get("LG_RECIPIENT_FILE", "/etc/language-guard/age-recipient")
    age_bin = env.get("LG_AGE_BIN", "/usr/local/lib/language-guard-age/age")
    attempt_id = env.get("LG_ATTEMPT_ID", "")
    resume = parse_resume(env)

    for path_value, label in (
        (state_dir, "state-dir"),
        (source_db, "source-db"),
        (socket_path, "socket"),
        (recipient_file, "recipient-file"),
        (age_bin, "age-bin"),
    ):
        if not path_value or "\x00" in path_value:
            raise ConfigError(f"{label}-rejected")
        if os.path.islink(path_value):
            raise ConfigError(f"{label}-symlink")

    # Probe activation entries first so symlinks/bad types never fall through.
    markers = activation_entries_present(cred_dir)
    activation = read_credential_file(
        cred_dir, ACTIVATION_NAME, max_bytes=64, required=False
    )

    if activation is None and not markers:
        # Default inactive: encrypt-only orchestration, no network transport.
        if resume:
            raise ConfigError("resume-requires-activation")
        if attempt_id and not backup_worker.attempt_store.safe_id(attempt_id):
            raise ConfigError("attempt-id")
        return UploadConfig(
            mode="inactive",
            state_dir=state_dir,
            source_db=source_db,
            socket_path=socket_path,
            recipient_file=recipient_file,
            age_bin=age_bin,
            attempt_id=attempt_id,
            resume=False,
            credential_dir=cred_dir or "",
            folder_id="",
            client_id="",
            client_secret="",
            object_name="",
        )

    if activation != ACTIVATION_VALUE:
        raise ConfigError("activation-rejected")

    folder_id = read_credential_file(
        cred_dir, FOLDER_ID_NAME, max_bytes=128, required=True
    )
    client_id = read_credential_file(
        cred_dir, CLIENT_ID_NAME, max_bytes=256, required=True
    )
    client_secret = read_credential_file(
        cred_dir, CLIENT_SECRET_NAME, max_bytes=256, required=False
    ) or ""

    assert folder_id is not None and client_id is not None
    if not _FOLDER_ID_RE.fullmatch(folder_id):
        raise ConfigError("folder-id-rejected")
    if not _CLIENT_ID_RE.fullmatch(client_id) or len(client_id) < 8:
        raise ConfigError("client-id-rejected")
    if client_secret and (
        any(char.isspace() for char in client_secret) or len(client_secret) > 256
    ):
        raise ConfigError("client-secret-rejected")

    # Refresh token must exist before handoff/network (fail closed).
    try:
        credential.read_refresh(cred_dir)
    except credential.TokenError as exc:
        raise ConfigError(exc.detail) from exc

    if resume:
        if not attempt_id or not backup_worker.attempt_store.safe_id(attempt_id):
            raise ConfigError("attempt-id")
        object_name = object_name_for(attempt_id)
    else:
        if attempt_id:
            if not backup_worker.attempt_store.safe_id(attempt_id):
                raise ConfigError("attempt-id")
            object_name = object_name_for(attempt_id)
        else:
            # Deterministic name assigned after attempt id is known inside run().
            object_name = ""

    recipient = backup_worker._recipient_from(recipient_file)
    if not recipient:
        raise ConfigError("recipient-rejected")
    if not os.path.isfile(age_bin) or os.path.islink(age_bin):
        raise ConfigError("age-missing")

    return UploadConfig(
        mode="upload",
        state_dir=state_dir,
        source_db=source_db,
        socket_path=socket_path,
        recipient_file=recipient_file,
        age_bin=age_bin,
        attempt_id=attempt_id,
        resume=resume,
        credential_dir=cred_dir,
        folder_id=folder_id,
        client_id=client_id,
        client_secret=client_secret,
        object_name=object_name,
    )


def exit_status_code(mode: str, status: str) -> int:
    """Truthful process exits for systemd/monitoring.

    Upload mode: only VERIFIED/RECONCILED are success (0).
    Inactive mode: ENCRYPTED remains the attempt state, but the process exits
    ``INACTIVE_NOT_OFFBOX_EXIT`` so encrypt-only is never off-box success.
    """
    if mode == "upload":
        return 0 if status in {"VERIFIED", "RECONCILED"} else 1
    if status == "ENCRYPTED":
        return INACTIVE_NOT_OFFBOX_EXIT
    return 1


def build_transport():
    return https_transport.HttpsTransport()


def build_exchanger(transport, client_id: str, client_secret: str = ""):
    return oauth_exchange.GoogleRefreshExchanger(
        transport, client_id, client_secret=client_secret
    )


def run_orchestrated(
    config: UploadConfig,
    *,
    transport=None,
    token_exchanger=None,
    connected=None,
    free_bytes: int | None = None,
    run_fn: Callable[..., backup_worker.WorkerResult] | None = None,
) -> backup_worker.WorkerResult:
    runner = run_fn or backup_worker.run
    recipient = backup_worker._recipient_from(config.recipient_file)

    if config.mode == "inactive":
        logutil.log_event("upload-mode", status="inactive")
        return runner(
            state_dir=config.state_dir,
            source_db=config.source_db,
            socket_path=config.socket_path,
            connected=connected,
            recipient=recipient,
            age_exe=config.age_bin,
            attempt_id=config.attempt_id,
            credential_dir=config.credential_dir,
            free_bytes=free_bytes,
            transport=None,
            resume=False,
        )

    # Upload mode: construct transport/exchanger unless tests inject fakes.
    active_transport = transport if transport is not None else build_transport()
    active_exchanger = (
        token_exchanger
        if token_exchanger is not None
        else build_exchanger(
            active_transport, config.client_id, config.client_secret
        )
    )

    attempt_id = config.attempt_id
    object_name = config.object_name
    if not config.resume and not attempt_id:
        attempt_id = backup_worker.attempt_store.new_attempt_id()
        object_name = object_name_for(attempt_id)
    elif not object_name:
        object_name = object_name_for(attempt_id)

    logutil.log_event("upload-mode", status="upload", resume="true" if config.resume else "false")
    return runner(
        state_dir=config.state_dir,
        source_db=config.source_db,
        socket_path=config.socket_path,
        connected=connected,
        recipient=recipient,
        age_exe=config.age_bin,
        attempt_id=attempt_id,
        credential_dir=config.credential_dir,
        free_bytes=free_bytes,
        transport=active_transport,
        folder_id=config.folder_id,
        object_name=object_name,
        token_exchanger=active_exchanger,
        resume=config.resume,
    )


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if argv:
        # No CLI secrets or folder ids — configuration is env + LoadCredential only.
        logutil.log_event("worker-exit", status="FAILED", detail="argv-forbidden")
        return 2
    try:
        config = load_config()
    except ConfigError as exc:
        logutil.log_event("worker-exit", status="FAILED", detail=exc.detail)
        return 1
    result = run_orchestrated(config)
    logutil.log_event(
        "worker-exit",
        status=result.status,
        detail=result.detail,
        mode=config.mode,
        exit=exit_status_code(config.mode, result.status),
    )
    return exit_status_code(config.mode, result.status)


if __name__ == "__main__":
    raise SystemExit(main())
