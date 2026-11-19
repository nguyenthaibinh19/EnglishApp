"""Offline tests for production upload orchestration entrypoint (18B.9 R1).

Uses fake transports, synthetic credentials, temporary directories only.
No Google OAuth, Drive, VPS, or production network activity.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from offbox_support import ACCEPTED_D5A2D0_P1_SHA256, ROOT

HETZNER = ROOT / "deploy" / "hetzner"
PRODUCTION_UPLOAD_NAME = "production_upload_worker.py"
ENTRYPOINT = HETZNER / PRODUCTION_UPLOAD_NAME
PACKAGER = HETZNER / "install_offbox_packaging.py"
OFFBOX = HETZNER / "offbox"
PY = sys.executable

# Synthetic age recipient: matches backup_worker._recipient_from shape only.
FAKE_RECIPIENT = "age1pq1" + ("a" * 1500)
FAKE_REFRESH = "synthetic-refresh-token-not-real-xyz"
FAKE_CLIENT_ID = "123456789012-abcdefghijklmnopqrstuvwxyz.apps.googleusercontent.com"
FAKE_FOLDER = "0BxxxxxxxxDriveFolderId"
FAKE_SECRET = "GOCSPX-not-a-real-client-secret"


def _load_entrypoint():
    # Ensure offbox modules resolve the same way the entrypoint does.
    offbox = str(OFFBOX)
    if offbox not in sys.path:
        sys.path.insert(0, offbox)
    spec = importlib.util.spec_from_file_location(
        "production_upload_worker_under_test", ENTRYPOINT
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_packager():
    spec = importlib.util.spec_from_file_location(
        "install_offbox_packaging_puw", PACKAGER
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="ascii", newline="\n")


def _cred_dir(tmp_path: Path, **files: str) -> Path:
    directory = tmp_path / "creds"
    directory.mkdir(parents=True, exist_ok=True)
    for name, value in files.items():
        _write(directory / name, value)
    return directory


def _base_env(tmp_path: Path, *, creds: Path | None = None, **extra: str) -> dict[str, str]:
    state = tmp_path / "state"
    state.mkdir(exist_ok=True)
    recipient = tmp_path / "recipient"
    _write(recipient, FAKE_RECIPIENT)
    age_bin = tmp_path / "age"
    _write(age_bin, "#!/bin/sh\nexit 1\n")
    source = tmp_path / "accounts.db"
    # Unreadable to the worker probe is preferred; create and leave readable —
    # orchestration tests inject run_fn, so source readability is irrelevant.
    source.write_bytes(b"SQLite format 3\x00fake")
    socket_path = tmp_path / "handoff.sock"
    env = {
        "LG_STATE_DIR": str(state),
        "LG_SOURCE_DB": str(source),
        "LG_SOCKET": str(socket_path),
        "LG_RECIPIENT_FILE": str(recipient),
        "LG_AGE_BIN": str(age_bin),
        "CREDENTIALS_DIRECTORY": str(creds) if creds is not None else "",
    }
    env.update(extra)
    return env


@pytest.fixture
def puw():
    return _load_entrypoint()


def test_entrypoint_exists_outside_frozen_modules() -> None:
    assert ENTRYPOINT.is_file()
    assert ENTRYPOINT.parent == HETZNER
    assert not (OFFBOX / "production_upload_worker.py").exists()


def test_frozen_modules_remain_byte_identical() -> None:
    for name, expected in ACCEPTED_D5A2D0_P1_SHA256.items():
        got = hashlib.sha256((OFFBOX / name).read_bytes()).hexdigest()
        assert got == expected, name


def test_inactive_default_constructs_without_transport(puw, tmp_path: Path) -> None:
    creds = _cred_dir(tmp_path, **{"oauth-refresh": FAKE_REFRESH})
    env = _base_env(tmp_path, creds=creds)
    config = puw.load_config(env)
    assert config.mode == "inactive"
    assert config.folder_id == ""
    calls: list[dict] = []

    def fake_run(**kwargs):
        calls.append(kwargs)
        return puw.backup_worker.WorkerResult("ENCRYPTED", "offline-test")

    result = puw.run_orchestrated(config, run_fn=fake_run)
    assert result.status == "ENCRYPTED"
    assert len(calls) == 1
    assert calls[0]["transport"] is None
    assert calls[0].get("folder_id") in (None, "") or "folder_id" not in calls[0]
    # F2: ENCRYPTED attempt state preserved, but process exit is non-success.
    assert result.status == "ENCRYPTED"
    assert puw.exit_status_code(config.mode, result.status) == puw.INACTIVE_NOT_OFFBOX_EXIT
    assert puw.exit_status_code(config.mode, result.status) != 0


def test_default_disabled_never_builds_live_transport(puw, tmp_path: Path, monkeypatch) -> None:
    creds = _cred_dir(tmp_path, **{"oauth-refresh": FAKE_REFRESH})
    env = _base_env(tmp_path, creds=creds)
    config = puw.load_config(env)
    assert config.mode == "inactive"
    built = {"transport": 0, "exchanger": 0}

    def boom_transport():
        built["transport"] += 1
        raise AssertionError("transport must not be built in inactive mode")

    def boom_exchanger(*_a, **_k):
        built["exchanger"] += 1
        raise AssertionError("exchanger must not be built in inactive mode")

    monkeypatch.setattr(puw, "build_transport", boom_transport)
    monkeypatch.setattr(puw, "build_exchanger", boom_exchanger)

    def fake_run(**kwargs):
        assert kwargs.get("transport") is None
        return puw.backup_worker.WorkerResult("ENCRYPTED", "inactive")

    puw.run_orchestrated(config, run_fn=fake_run)
    assert built == {"transport": 0, "exchanger": 0}


def test_valid_upload_config_invokes_transport_and_exchanger(puw, tmp_path: Path) -> None:
    creds = _cred_dir(
        tmp_path,
        **{
            "upload-activation": "authorized",
            "drive-folder-id": FAKE_FOLDER,
            "oauth-client-id": FAKE_CLIENT_ID,
            "oauth-client-secret": FAKE_SECRET,
            "oauth-refresh": FAKE_REFRESH,
        },
    )
    env = _base_env(tmp_path, creds=creds, LG_ATTEMPT_ID="20261119T000000Z-1-deadbeef")
    config = puw.load_config(env)
    assert config.mode == "upload"
    assert config.folder_id == FAKE_FOLDER
    assert config.object_name == "accounts-20261119T000000Z-1-deadbeef.age"
    assert config.client_id == FAKE_CLIENT_ID
    assert config.client_secret == FAKE_SECRET

    class FakeTransport:
        scheme = "https"

    class FakeExchanger:
        def __init__(self, transport, client_id, client_secret=""):
            self.transport = transport
            self.client_id = client_id
            self.client_secret = client_secret

        def exchange(self, refresh_token: str) -> str:
            raise AssertionError("exchange must not run; run_fn is injected")

    captured: dict = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return puw.backup_worker.WorkerResult("VERIFIED", "download-match")

    transport = FakeTransport()
    exchanger = FakeExchanger(transport, config.client_id, config.client_secret)
    result = puw.run_orchestrated(
        config, transport=transport, token_exchanger=exchanger, run_fn=fake_run
    )
    assert result.status == "VERIFIED"
    assert captured["transport"] is transport
    assert captured["token_exchanger"] is exchanger
    assert captured["folder_id"] == FAKE_FOLDER
    assert captured["object_name"] == config.object_name
    assert captured["resume"] is False
    assert puw.exit_status_code("upload", "VERIFIED") == 0
    assert puw.exit_status_code("upload", "RECONCILED") == 0
    assert puw.exit_status_code("upload", "ENCRYPTED") == 1
    assert puw.exit_status_code("upload", "UPLOADING") == 1
    assert puw.exit_status_code("upload", "UNKNOWN") == 1


def test_missing_activation_with_partial_markers_fails_closed(puw, tmp_path: Path) -> None:
    creds = _cred_dir(
        tmp_path,
        **{
            "drive-folder-id": FAKE_FOLDER,
            "oauth-client-id": FAKE_CLIENT_ID,
            "oauth-refresh": FAKE_REFRESH,
        },
    )
    env = _base_env(tmp_path, creds=creds)
    with pytest.raises(puw.ConfigError, match="activation-rejected"):
        puw.load_config(env)


def test_malformed_folder_id_fails_closed(puw, tmp_path: Path) -> None:
    creds = _cred_dir(
        tmp_path,
        **{
            "upload-activation": "authorized",
            "drive-folder-id": "../evil",
            "oauth-client-id": FAKE_CLIENT_ID,
            "oauth-refresh": FAKE_REFRESH,
        },
    )
    env = _base_env(tmp_path, creds=creds)
    with pytest.raises(puw.ConfigError, match="folder-id-rejected"):
        puw.load_config(env)


def test_missing_refresh_fails_before_run(puw, tmp_path: Path) -> None:
    creds = _cred_dir(
        tmp_path,
        **{
            "upload-activation": "authorized",
            "drive-folder-id": FAKE_FOLDER,
            "oauth-client-id": FAKE_CLIENT_ID,
        },
    )
    env = _base_env(tmp_path, creds=creds)
    with pytest.raises(puw.ConfigError, match="credential-absent"):
        puw.load_config(env)


def test_forbidden_secret_env_fails_closed(puw, tmp_path: Path) -> None:
    creds = _cred_dir(tmp_path, **{"oauth-refresh": FAKE_REFRESH})
    for key in ("LG_DRIVE_FOLDER", "LG_UPLOAD_ENABLED", "LG_OAUTH_CLIENT_SECRET"):
        env = _base_env(tmp_path, creds=creds, **{key: "x"})
        with pytest.raises(puw.ConfigError, match="secret-env-forbidden"):
            puw.load_config(env)


def test_argv_forbidden(puw) -> None:
    code = puw.main(["--folder", "x"])
    assert code == 2


def test_secrets_never_logged(puw, tmp_path: Path, monkeypatch) -> None:
    import logutil

    logutil.CAPTURE.clear()
    creds = _cred_dir(
        tmp_path,
        **{
            "upload-activation": "authorized",
            "drive-folder-id": FAKE_FOLDER,
            "oauth-client-id": FAKE_CLIENT_ID,
            "oauth-client-secret": FAKE_SECRET,
            "oauth-refresh": FAKE_REFRESH,
        },
    )
    env = _base_env(tmp_path, creds=creds, LG_ATTEMPT_ID="20261119T120000Z-9-aabbccdd")
    config = puw.load_config(env)

    def fake_run(**_kwargs):
        return puw.backup_worker.WorkerResult("UNKNOWN", "http-only")

    buf = io.StringIO()
    monkeypatch.setattr(sys, "stderr", buf)
    puw.run_orchestrated(config, transport=object(), token_exchanger=object(), run_fn=fake_run)
    joined = "\n".join(logutil.CAPTURE) + "\n" + buf.getvalue()
    for secret in (FAKE_REFRESH, FAKE_SECRET, FAKE_CLIENT_ID, "https://"):
        assert secret not in joined
    assert "GOCSPX-" not in joined or "redacted" in joined


def test_http_success_alone_is_not_verified_exit(puw) -> None:
    assert puw.exit_status_code("upload", "UNKNOWN") == 1
    assert puw.exit_status_code("upload", "UPLOADING") == 1
    assert puw.exit_status_code("upload", "ENCRYPTED") == 1
    assert puw.exit_status_code("upload", "VERIFIED") == 0
    assert puw.exit_status_code("inactive", "ENCRYPTED") == puw.INACTIVE_NOT_OFFBOX_EXIT
    assert puw.exit_status_code("inactive", "FAILED") == 1


def test_resume_preserves_object_name_and_flags(puw, tmp_path: Path) -> None:
    attempt = "20261119T010203Z-42-cafebabe"
    creds = _cred_dir(
        tmp_path,
        **{
            "upload-activation": "authorized",
            "drive-folder-id": FAKE_FOLDER,
            "oauth-client-id": FAKE_CLIENT_ID,
            "oauth-refresh": FAKE_REFRESH,
        },
    )
    env = _base_env(tmp_path, creds=creds, LG_ATTEMPT_ID=attempt, LG_RESUME="1")
    config = puw.load_config(env)
    assert config.resume is True
    assert config.object_name == f"accounts-{attempt}.age"
    captured: dict = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return puw.backup_worker.WorkerResult("RECONCILED", "same-file-id")

    result = puw.run_orchestrated(
        config, transport=object(), token_exchanger=object(), run_fn=fake_run
    )
    assert result.status == "RECONCILED"
    assert captured["resume"] is True
    assert captured["attempt_id"] == attempt
    assert captured["object_name"] == config.object_name
    assert captured["folder_id"] == FAKE_FOLDER


def test_invalid_attempt_id_rejected(puw, tmp_path: Path) -> None:
    creds = _cred_dir(
        tmp_path,
        **{
            "upload-activation": "authorized",
            "drive-folder-id": FAKE_FOLDER,
            "oauth-client-id": FAKE_CLIENT_ID,
            "oauth-refresh": FAKE_REFRESH,
        },
    )
    env = _base_env(tmp_path, creds=creds, LG_ATTEMPT_ID="../escape")
    with pytest.raises(puw.ConfigError, match="attempt-id"):
        puw.load_config(env)


def test_symlink_credential_rejected(puw, tmp_path: Path) -> None:
    creds = _cred_dir(
        tmp_path,
        **{
            "upload-activation": "authorized",
            "drive-folder-id": FAKE_FOLDER,
            "oauth-client-id": FAKE_CLIENT_ID,
            "oauth-refresh": FAKE_REFRESH,
        },
    )
    real = tmp_path / "real-refresh"
    _write(real, FAKE_REFRESH)
    link = creds / "oauth-refresh"
    link.unlink()
    try:
        link.symlink_to(real)
    except OSError:
        pytest.skip("symlink creation unavailable on this host")
    env = _base_env(tmp_path, creds=creds)
    with pytest.raises(puw.ConfigError, match="credential-absent|oauth-refresh-rejected"):
        puw.load_config(env)


def test_symlink_state_dir_rejected(puw, tmp_path: Path) -> None:
    creds = _cred_dir(tmp_path, **{"oauth-refresh": FAKE_REFRESH})
    real_state = tmp_path / "real-state"
    real_state.mkdir()
    link_state = tmp_path / "state-link"
    try:
        link_state.symlink_to(real_state)
    except OSError:
        pytest.skip("symlink creation unavailable on this host")
    env = _base_env(tmp_path, creds=creds)
    env["LG_STATE_DIR"] = str(link_state)
    with pytest.raises(puw.ConfigError, match="state-dir-symlink"):
        puw.load_config(env)


def test_resume_without_activation_fails_closed(puw, tmp_path: Path) -> None:
    creds = _cred_dir(tmp_path, **{"oauth-refresh": FAKE_REFRESH})
    env = _base_env(
        tmp_path,
        creds=creds,
        LG_RESUME="1",
        LG_ATTEMPT_ID="20261119T000000Z-1-deadbeef",
    )
    with pytest.raises(puw.ConfigError, match="resume-requires-activation"):
        puw.load_config(env)


def test_build_transport_and_exchanger_types(puw) -> None:
    transport = puw.build_transport()
    assert transport.__class__.__name__ == "HttpsTransport"
    exchanger = puw.build_exchanger(transport, FAKE_CLIENT_ID, client_secret="")
    assert exchanger.__class__.__name__ == "GoogleRefreshExchanger"
    assert exchanger.client_id == FAKE_CLIENT_ID


def test_packaging_includes_entrypoint_and_worker_execstart(tmp_path: Path) -> None:
    packager = _load_packager()
    assert "production_upload_worker.py" in packager.APP_TREE_HELPERS
    assert packager.WORKER_EXEC_START.endswith(
        "/opt/language-guard-offbox/deploy/hetzner/production_upload_worker.py"
    )
    dest = tmp_path / "language-guard-offbox"
    written = packager.install_execution_tree(dest, hetzner_dir=HETZNER, production=False)
    assert any(path.endswith("production_upload_worker.py") for path in written)
    staged = dest / "deploy" / "hetzner" / "production_upload_worker.py"
    assert staged.is_file()
    assert staged.read_bytes() == ENTRYPOINT.read_bytes()
    worker_unit = (dest / "deploy" / "hetzner" / "language-guard-offbox-worker.service").read_text(
        encoding="utf-8"
    )
    assert (
        "ExecStart=/usr/bin/python3 -I "
        "/opt/language-guard-offbox/deploy/hetzner/production_upload_worker.py"
        in worker_unit
    )
    assert "LG_DRIVE_FOLDER=" not in worker_unit
    assert "LG_UPLOAD_ENABLED=" not in worker_unit
    # Default unit stays inert: only oauth-refresh LoadCredential.
    assert worker_unit.count("LoadCredential=") == 1
    assert "LoadCredential=oauth-refresh:" in worker_unit
    packager.verify_units(dest / "deploy" / "hetzner")
    for name, expected in ACCEPTED_D5A2D0_P1_SHA256.items():
        got = hashlib.sha256((dest / "offbox" / name).read_bytes()).hexdigest()
        assert got == expected, name


def test_packaging_rejects_tampered_entrypoint_unit(tmp_path: Path) -> None:
    packager = _load_packager()
    unit_dir = tmp_path / "units"
    unit_dir.mkdir()
    for name in packager.UNIT_NAMES:
        (unit_dir / name).write_text(
            (HETZNER / name).read_text(encoding="utf-8"), encoding="utf-8"
        )
    worker = unit_dir / "language-guard-offbox-worker.service"
    text = worker.read_text(encoding="utf-8")
    text = text.replace(
        "ExecStart=/usr/bin/python3 -I /opt/language-guard-offbox/deploy/hetzner/production_upload_worker.py",
        "ExecStart=/usr/bin/python3 -I /tmp/evil_upload.py",
    )
    worker.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="contract mismatch|ExecStart"):
        packager.verify_units(unit_dir)


def test_backup_worker_main_still_refuses_live_env(tmp_path: Path) -> None:
    """Frozen main() behavior preserved: env live-upload knobs fail closed."""
    env = os.environ.copy()
    env["LG_DRIVE_FOLDER"] = "should-fail"
    env["LG_STATE_DIR"] = str(tmp_path)
    result = subprocess.run(
        [PY, str(OFFBOX / "backup_worker.py")],
        cwd=str(OFFBOX),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode == 1
    assert "live-transport-disabled" in result.stderr


def test_malformed_resume_rejected_not_new_attempt(puw, tmp_path: Path) -> None:
    creds = _cred_dir(tmp_path, **{"oauth-refresh": FAKE_REFRESH})
    for bad in ("0", "true", "yes", "2", "resume"):
        env = _base_env(tmp_path, creds=creds, LG_RESUME=bad)
        with pytest.raises(puw.ConfigError, match="resume-rejected"):
            puw.load_config(env)


def test_activation_symlink_marker_fails_closed_not_inactive(puw, tmp_path: Path) -> None:
    creds = _cred_dir(tmp_path, **{"oauth-refresh": FAKE_REFRESH})
    real = tmp_path / "real-activation"
    _write(real, "authorized")
    link = creds / "upload-activation"
    try:
        link.symlink_to(real)
    except OSError:
        pytest.skip("symlink creation unavailable on this host")
    env = _base_env(tmp_path, creds=creds)
    with pytest.raises(puw.ConfigError, match="upload-activation-symlink"):
        puw.load_config(env)


def test_dangling_activation_symlink_fails_closed(puw, tmp_path: Path) -> None:
    creds = _cred_dir(tmp_path, **{"oauth-refresh": FAKE_REFRESH})
    link = creds / "drive-folder-id"
    try:
        link.symlink_to(tmp_path / "missing-target")
    except OSError:
        pytest.skip("symlink creation unavailable on this host")
    env = _base_env(tmp_path, creds=creds)
    with pytest.raises(puw.ConfigError, match="drive-folder-id-symlink"):
        puw.load_config(env)


def test_activation_directory_entry_fails_closed(puw, tmp_path: Path) -> None:
    creds = _cred_dir(tmp_path, **{"oauth-refresh": FAKE_REFRESH})
    (creds / "oauth-client-id").mkdir()
    env = _base_env(tmp_path, creds=creds)
    with pytest.raises(puw.ConfigError, match="oauth-client-id-rejected"):
        puw.load_config(env)


def test_partial_marker_has_no_side_effects(puw, tmp_path: Path) -> None:
    """Config failure must occur before run_orchestrated / fake_run."""
    creds = _cred_dir(
        tmp_path,
        **{
            "drive-folder-id": FAKE_FOLDER,
            "oauth-refresh": FAKE_REFRESH,
        },
    )
    env = _base_env(tmp_path, creds=creds)
    state = Path(env["LG_STATE_DIR"])
    before = list(state.iterdir())
    with pytest.raises(puw.ConfigError, match="activation-rejected"):
        puw.load_config(env)
    assert list(state.iterdir()) == before


def test_wrapper_packaging_pin_independent_of_frozen_inventory() -> None:
    packager = _load_packager()
    digest = packager.verify_production_upload_worker(HETZNER, offbox=OFFBOX)
    assert digest == packager.ACCEPTED_PRODUCTION_UPLOAD_WORKER_SHA256
    assert PRODUCTION_UPLOAD_NAME not in packager.ACCEPTED_D5A2D0_P1_SHA256
    assert digest == hashlib.sha256(ENTRYPOINT.read_bytes()).hexdigest()


def test_wrapper_line_ending_pin_is_lf_portable() -> None:
    """Packaging pin must track canonical LF bytes, not Windows CRLF working trees.

    Regression: a CRLF pin passes on Windows but fails Linux checkout packaging.
    """
    attrs = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "deploy/hetzner/production_upload_worker.py text eol=lf" in attrs
    raw = ENTRYPOINT.read_bytes()
    assert b"\r" not in raw, "wrapper working-tree bytes must be LF-only"
    lf_digest = hashlib.sha256(raw).hexdigest()
    packager = _load_packager()
    assert lf_digest == packager.ACCEPTED_PRODUCTION_UPLOAD_WORKER_SHA256
    # CRLF re-encoding must not silently match the accepted pin.
    crlf = raw.replace(b"\n", b"\r\n")
    assert b"\r\n" in crlf
    crlf_digest = hashlib.sha256(crlf).hexdigest()
    assert crlf_digest != packager.ACCEPTED_PRODUCTION_UPLOAD_WORKER_SHA256
    assert crlf_digest == (
        "4f6b7bfa7b37c7ada99731459b927291a5744938548a115f9d393858760e9656"
    )


def test_verify_rejects_modified_wrapper(tmp_path: Path) -> None:
    packager = _load_packager()
    fake = tmp_path / "hetzner"
    fake.mkdir()
    for name in packager.UNIT_NAMES + packager.APP_TREE_HELPERS:
        src = HETZNER / name
        if src.is_file():
            (fake / name).write_bytes(src.read_bytes())
    # Point offbox via sibling layout expected by resolve/verify.
    offbox = fake / "offbox"
    offbox.mkdir()
    for path in OFFBOX.iterdir():
        if path.is_file():
            (offbox / path.name).write_bytes(path.read_bytes())
    wrapper = fake / PRODUCTION_UPLOAD_NAME
    wrapper.write_bytes(wrapper.read_bytes() + b"\n# tampered\n")
    with pytest.raises(ValueError, match="production wrapper hash mismatch"):
        packager.verify_production_upload_worker(fake, offbox=offbox)


def test_verify_rejects_missing_wrapper(tmp_path: Path) -> None:
    packager = _load_packager()
    fake = tmp_path / "hetzner"
    fake.mkdir()
    offbox = fake / "offbox"
    offbox.mkdir()
    for path in OFFBOX.iterdir():
        if path.is_file():
            (offbox / path.name).write_bytes(path.read_bytes())
    with pytest.raises(FileNotFoundError, match="production_upload_worker"):
        packager.verify_production_upload_worker(fake, offbox=offbox)


def test_verify_rejects_symlinked_wrapper(tmp_path: Path) -> None:
    packager = _load_packager()
    fake = tmp_path / "hetzner"
    fake.mkdir()
    offbox = fake / "offbox"
    offbox.mkdir()
    for path in OFFBOX.iterdir():
        if path.is_file():
            (offbox / path.name).write_bytes(path.read_bytes())
    real = tmp_path / "real-wrapper.py"
    real.write_bytes(ENTRYPOINT.read_bytes())
    link = fake / PRODUCTION_UPLOAD_NAME
    try:
        link.symlink_to(real)
    except OSError:
        pytest.skip("symlink creation unavailable on this host")
    with pytest.raises(ValueError, match="must not be a symlink"):
        packager.verify_production_upload_worker(fake, offbox=offbox)


def test_installed_layout_wrapper_isolated_smoke(tmp_path: Path) -> None:
    packager = _load_packager()
    dest = tmp_path / "language-guard-offbox"
    packager.install_execution_tree(dest, hetzner_dir=HETZNER, production=False)
    wrapper = dest / "deploy" / "hetzner" / PRODUCTION_UPLOAD_NAME
    assert hashlib.sha256(wrapper.read_bytes()).hexdigest() == (
        packager.ACCEPTED_PRODUCTION_UPLOAD_WORKER_SHA256
    )
    packager.verify_production_upload_worker(
        dest / "deploy" / "hetzner", offbox=dest / "offbox"
    )
    script = (
        "import importlib.util, sys\n"
        f"spec = importlib.util.spec_from_file_location('puw_smoke', {str(wrapper)!r})\n"
        "mod = importlib.util.module_from_spec(spec)\n"
        "sys.modules[spec.name] = mod\n"
        "spec.loader.exec_module(mod)\n"
        "assert mod.exit_status_code('inactive', 'ENCRYPTED') == mod.INACTIVE_NOT_OFFBOX_EXIT\n"
        "assert mod.exit_status_code('upload', 'VERIFIED') == 0\n"
        "print('WRAPPER_SMOKE_OK')\n"
    )
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env["PYTHONNOUSERSITE"] = "1"
    result = subprocess.run(
        [PY, "-I", "-c", script],
        cwd=str(dest / "deploy" / "hetzner"),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    assert "WRAPPER_SMOKE_OK" in result.stdout


def test_stage_layout_revalidates_wrapper(tmp_path: Path) -> None:
    packager = _load_packager()
    dest = tmp_path / "stage"
    written = packager.stage(dest, hetzner_dir=HETZNER, include_units=True)
    assert f"deploy/hetzner/{PRODUCTION_UPLOAD_NAME}" in written
    staged = dest / "deploy" / "hetzner" / PRODUCTION_UPLOAD_NAME
    assert staged.is_file()
    packager.verify_production_upload_worker(
        dest / "deploy" / "hetzner", offbox=dest / "offbox"
    )
