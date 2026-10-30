"""Isolated staging guard and synthetic drill. No VPS, production data, or real provider."""

from __future__ import annotations

import json
import os
import socket
import stat
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

HETZNER = Path(__file__).resolve().parents[1] / "deploy" / "hetzner"
sys.path.insert(0, str(HETZNER))

import staging_drill
import staging_guard

UNIT = HETZNER / "language-guard-staging.service"
SETUP = HETZNER / "setup.sh"


def _layout(tmp_path: Path, **changes) -> staging_guard.StagingLayout:
    port = changes.pop("port", staging_drill._choose_port())
    layout = staging_drill._layout(tmp_path / "drill", port, "0")
    if changes:
        layout = replace(layout, **changes)
    return layout


def _names(path: Path) -> list:
    if not path.exists():
        return []
    return sorted(item.name for item in path.iterdir())


def test_guard_rejects_public_bind_and_production_port(tmp_path):
    before = _names(tmp_path)
    public = _layout(tmp_path, bind="0.0.0.0")
    with pytest.raises(staging_guard.StagingGuardError) as public_error:
        staging_guard.validate(public)
    assert public_error.value.code == "bind"

    production_port = _layout(tmp_path, port=8765)
    with pytest.raises(staging_guard.StagingGuardError) as port_error:
        staging_guard.validate(production_port)
    assert port_error.value.code == "port"
    assert _names(tmp_path) == before


def test_guard_rejects_an_occupied_port_without_creating_files(tmp_path):
    layout = _layout(tmp_path)
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind((staging_guard.REQUIRED_BIND, layout.port))
    listener.listen(1)
    before = _names(tmp_path)
    try:
        with pytest.raises(staging_guard.StagingGuardError) as caught:
            staging_guard.validate(layout)
        assert caught.value.code == "occupied"
        assert _names(tmp_path) == before
    finally:
        listener.close()


def test_guard_rejects_protected_trees_and_overlap(tmp_path, monkeypatch):
    protected = tmp_path / "protected-app"
    backups = tmp_path / "protected-backups"
    protected.mkdir()
    backups.mkdir()
    marker = protected / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    if os.name == "posix":
        os.chmod(protected, 0o755)
    before_mode = stat.S_IMODE(os.stat(protected).st_mode)
    monkeypatch.setattr(staging_guard, "PRODUCTION_APP_ROOT", str(protected))
    monkeypatch.setattr(staging_guard, "PRODUCTION_BACKUP_ROOT", str(backups))

    inside = _layout(
        tmp_path,
        package_dir=str(protected / "package"),
        account_db=str(protected / "package" / "accounts.db"),
        env_file=str(protected / "package" / ".env"),
    )
    with pytest.raises(staging_guard.StagingGuardError) as app_error:
        staging_guard.validate(inside)
    assert app_error.value.code == "protected"
    assert marker.read_text(encoding="utf-8") == "keep"
    assert stat.S_IMODE(os.stat(protected).st_mode) == before_mode
    assert not (protected / "package").exists()

    backup_hit = _layout(tmp_path, backup_dir=str(backups / "study-sync"))
    with pytest.raises(staging_guard.StagingGuardError) as backup_error:
        staging_guard.validate(backup_hit)
    assert backup_error.value.code == "protected"
    assert _names(backups) == []

    same = tmp_path / "drill" / "language-guard-staging" / "accounts.db"
    overlap = _layout(tmp_path, sync_db=str(same), sync_dir=str(same.parent))
    with pytest.raises(staging_guard.StagingGuardError) as overlap_error:
        staging_guard.validate(overlap)
    assert overlap_error.value.code == "overlap"
    assert not (tmp_path / "drill").exists()


def test_guard_rejects_symlink_into_a_protected_tree(tmp_path, monkeypatch):
    protected = tmp_path / "protected-app"
    protected.mkdir()
    marker = protected / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    before_mode = stat.S_IMODE(os.stat(protected).st_mode)
    monkeypatch.setattr(staging_guard, "PRODUCTION_APP_ROOT", str(protected))
    alias = tmp_path / "alias"
    try:
        os.symlink(protected, alias, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks are not available")
    nested = alias / "language-guard-staging"
    layout = _layout(
        tmp_path,
        package_dir=str(nested),
        account_db=str(nested / "accounts.db"),
        env_file=str(nested / ".env"),
    )
    with pytest.raises(staging_guard.StagingGuardError) as caught:
        staging_guard.validate(layout)
    assert caught.value.code in {"symlink", "protected"}
    assert marker.read_text(encoding="utf-8") == "keep"
    assert not nested.exists()
    assert stat.S_IMODE(os.stat(protected).st_mode) == before_mode


def test_guard_rejects_production_like_secrets_without_writing(tmp_path):
    before = _names(tmp_path)
    cases = (
        {"api_key": "sk-production-secret-value-xxxx"},
        {"account_token": "prod-session-token"},
        {"openai_base_url": "https://api.openai.com/v1"},
        {"sync_enabled": "true"},
    )
    for changes in cases:
        layout = _layout(tmp_path, **changes)
        with pytest.raises(staging_guard.StagingGuardError) as caught:
            staging_guard.validate(layout)
        assert caught.value.code in {"secret", "isolated"}
    safe = _layout(tmp_path)
    staging_guard.validate(safe)
    assert _names(tmp_path) == before


def test_child_environment_does_not_inherit_a_real_key(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-real-looking-production-key")
    monkeypatch.setenv("ACCOUNT_TOKEN", "prod-session-token")
    layout = _layout(tmp_path)
    env = staging_drill.child_environment(layout, proof=str(tmp_path / "effective.json"))
    assert env["OPENAI_API_KEY"] == staging_guard.STAGING_FAKE_API_KEY
    assert env["ACCOUNT_BIND"] == "127.0.0.1"
    assert "ACCOUNT_TOKEN" not in env
    assert all(not str(value).startswith("sk-") for value in env.values())


def test_service_template_is_localhost_and_not_installed():
    text = UNIT.read_text(encoding="utf-8")
    setup = SETUP.read_text(encoding="utf-8")
    assert "ACCOUNT_BIND=127.0.0.1" in text
    assert "ACCOUNT_PORT=8876" in text
    assert "8765" not in text
    assert "WorkingDirectory=/opt/language-guard-staging" in text
    assert "ExecStartPre=" in text and "staging_guard.py" in text
    assert "STAGING_PROOF_DIR=/var/lib/language-guard-staging/proof" in text
    assert "STAGING_PROOF_FILE" not in text
    assert "0.0.0.0" not in text
    assert "/opt/language-guard/" not in text
    assert "/var/backups/language-guard/" not in text
    assert staging_guard.STAGING_FAKE_API_KEY in text
    assert "sk-" not in text
    assert "language-guard-staging" not in setup
    assert "systemctl enable" in setup


def test_guard_cli_rejects_without_creating_a_tree(tmp_path):
    layout = _layout(tmp_path, bind="0.0.0.0")
    env = staging_drill.child_environment(layout, proof=str(tmp_path / "effective.json"))
    env["PATH"] = os.environ.get("PATH", "")
    before = _names(tmp_path)
    result = subprocess.run(
        [sys.executable, str(HETZNER / "staging_guard.py")],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    assert result.returncode == 1
    assert "staging guard rejected" in result.stderr
    assert "bind" in result.stderr
    assert staging_guard.STAGING_FAKE_API_KEY not in result.stderr
    assert _names(tmp_path) == before


def test_synthetic_drill_covers_sync_backup_and_restart(tmp_path):
    report = staging_drill.run_synthetic_drill(tmp_path / "drill")
    assert report["bind"] == "127.0.0.1"
    assert report["port"] != 8765
    assert report["off_sync_status"] == 404
    assert report["off_db_exists"] is False
    assert report["off_mocks"] == ["grade", "reading", "listening", "enrich"]
    assert report["missing_bearer"] == 401
    assert report["invalid_bearer"] == 401
    assert report["create_revision"] == 1
    assert report["update_revision"] == 2
    assert report["replay_revision"] == 2
    assert report["reuse_status"] == 409
    assert report["stale_status"] == 409
    assert report["delete_revision"] == 3
    assert report["delete_tombstone"] is True
    assert report["pages"] >= 4
    assert report["cursors_ordered"] is True
    assert report["other_account_hidden"] is True
    assert report["spoofed_user_hidden"] is True
    assert report["verify_status"] == "VERIFIED"
    assert report["schema_version"] == 2
    assert report["integrity"] == "ok"
    assert report["source_unchanged"] is True
    assert report["backup_unchanged"] is True
    assert report["overwrite_refused"] is True
    assert report["disabled_sync_status"] == 404
    assert report["disabled_db_exists"] is True
    assert report["disabled_login"] == 200
    assert report["disabled_mocks"] == ["grade", "reading", "listening", "enrich"]
    assert report["port_released"] is True
    assert report["trap_absent"] is True
    assert report["repo_unchanged"] is True
    assert report["production_tree_absent"] is True
    package_env = (tmp_path / "drill" / "language-guard-staging" / ".env").read_text(encoding="utf-8")
    assert "sk-" not in package_env
    assert staging_guard.STAGING_FAKE_API_KEY in package_env


def test_staging_process_stops_after_a_failure(tmp_path):
    root = tmp_path / "drill"
    layout = staging_drill._layout(root, staging_drill._choose_port(), "0")
    staging_guard.validate(layout)
    staging_drill._materialize(layout)
    server = staging_drill.start_server(layout)
    try:
        with server:
            raise RuntimeError("boom")
    except RuntimeError as error:
        assert str(error) == "boom"
    assert server.process.poll() is not None
    assert not staging_guard._port_is_occupied(layout.port)


def _unchanged(path: Path, before: bytes) -> None:
    if path.read_bytes() != before:
        raise AssertionError("file bytes changed")


def _env_text(layout: staging_guard.StagingLayout) -> str:
    return "\n".join(
        (
            "OPENAI_API_KEY=" + layout.api_key,
            "OPENAI_BASE_URL=" + layout.openai_base_url,
            "ACCOUNT_BIND=" + layout.bind,
            "ACCOUNT_PORT=" + str(layout.port),
            "STUDY_SYNC_DIR=" + layout.sync_dir,
            "STUDY_SYNC_ENABLED=" + layout.sync_enabled,
            "",
        )
    )


def test_invalid_proof_path_leaves_database_and_marker_unchanged(tmp_path):
    layout = _layout(tmp_path)
    os.makedirs(layout.proof_dir)
    os.makedirs(layout.package_dir)
    database = Path(layout.account_db)
    database_bytes = b"SQLite format 3\x00keep"
    database.write_bytes(database_bytes)
    marker = tmp_path / "marker.txt"
    marker_bytes = b"keep-marker"
    marker.write_bytes(marker_bytes)
    with pytest.raises(staging_guard.StagingGuardError) as caught:
        staging_guard.write_proof(layout, str(database), sync_enabled=False)
    assert caught.value.code == "proof"
    _unchanged(database, database_bytes)
    _unchanged(marker, marker_bytes)
    with pytest.raises(staging_guard.StagingGuardError):
        staging_guard.write_proof(layout, str(marker), sync_enabled=False)
    _unchanged(database, database_bytes)
    _unchanged(marker, marker_bytes)


def test_proof_partial_symlink_does_not_change_the_marker(tmp_path):
    layout = _layout(tmp_path)
    os.makedirs(layout.proof_dir)
    marker = tmp_path / "marker.txt"
    marker_bytes = b"keep-marker"
    marker.write_bytes(marker_bytes)
    proof = staging_guard.allocate_proof_path(layout)
    try:
        os.symlink(marker, proof + ".partial")
    except OSError:
        pytest.skip("symlinks are not available")
    with pytest.raises(staging_guard.StagingGuardError) as caught:
        staging_guard.write_proof(layout, proof, sync_enabled=False)
    assert caught.value.code in {"symlink", "proof"}
    _unchanged(marker, marker_bytes)
    assert not Path(proof).exists()


def test_valid_proof_is_a_new_status_file(tmp_path):
    layout = _layout(tmp_path)
    os.makedirs(layout.proof_dir)
    marker = Path(layout.proof_dir) / "marker.txt"
    marker_bytes = b"keep-marker"
    marker.write_bytes(marker_bytes)
    proof = staging_guard.allocate_proof_path(layout)
    staging_guard.write_proof(layout, proof, sync_enabled=False)
    _unchanged(marker, marker_bytes)
    body = json.loads(Path(proof).read_text(encoding="utf-8"))
    text = Path(proof).read_text(encoding="utf-8")
    if "sk-" in text or staging_guard.STAGING_FAKE_API_KEY in text:
        raise AssertionError("proof contained a secret")
    assert set(body) == {"base_url", "bind", "key_is_staging_fake", "port", "sync_enabled"}
    assert body["bind"] == "127.0.0.1"
    assert body["key_is_staging_fake"] is True


def test_existing_env_file_is_allowlisted(tmp_path):
    layout = _layout(tmp_path)
    os.makedirs(layout.package_dir)
    env_path = Path(layout.env_file)
    env_path.write_text(_env_text(layout), encoding="utf-8")
    staging_guard.validate(layout, require_env_file=True)

    production_key = "sk-" + "prod-looking-value"
    env_path.write_text(
        _env_text(layout).replace(layout.api_key, production_key, 1),
        encoding="utf-8",
    )
    before = env_path.read_bytes()
    marker = tmp_path / "marker.txt"
    marker.write_bytes(b"keep-marker")
    with pytest.raises(staging_guard.StagingGuardError) as key_error:
        staging_guard.validate(layout)
    assert key_error.value.code == "secret"
    _unchanged(env_path, before)
    _unchanged(marker, b"keep-marker")

    env_path.write_text(_env_text(layout) + "ACCOUNT_TOKEN=unexpected-token-value\n", encoding="utf-8")
    before = env_path.read_bytes()
    with pytest.raises(staging_guard.StagingGuardError) as token_error:
        staging_guard.validate(layout)
    assert token_error.value.code == "secret"
    _unchanged(env_path, before)


def test_missing_or_malformed_env_is_rejected_before_listen(tmp_path):
    missing = _layout(tmp_path)
    legacy = Path(missing.package_dir).parent / "effective.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(b"keep-marker")
    with pytest.raises(staging_guard.StagingGuardError) as missing_error:
        staging_drill.start_server(missing)
    assert missing_error.value.code == "env"
    assert not staging_guard._port_is_occupied(missing.port)
    _unchanged(legacy, b"keep-marker")

    malformed = _layout(tmp_path / "other")
    os.makedirs(malformed.package_dir)
    Path(malformed.env_file).write_text("not-a-staging-env\n", encoding="utf-8")
    with pytest.raises(staging_guard.StagingGuardError) as malformed_error:
        staging_drill.start_server(malformed)
    assert malformed_error.value.code == "env"
    assert not staging_guard._port_is_occupied(malformed.port)


def test_parent_trap_stays_out_of_the_child_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", staging_drill.TRAP_KEY)
    (tmp_path / ".env").write_text("OPENAI_API_KEY=" + staging_drill.TRAP_KEY + "\n", encoding="utf-8")
    layout = _layout(tmp_path / "child")
    os.makedirs(layout.package_dir)
    staging_drill._write_env(layout)
    env = staging_drill.child_environment(layout, proof="")
    blob = "\n".join(str(value) for value in env.values())
    if staging_drill.TRAP_KEY in blob or staging_drill.TRAP_KEY in Path(layout.env_file).read_text(encoding="utf-8"):
        raise AssertionError("forbidden credential appeared")
