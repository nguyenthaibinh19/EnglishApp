"""Security regressions for the offbox executable-path trust boundary."""

from __future__ import annotations

import hashlib
import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from offbox_support import ACCEPTED_D5A2D0_P1_SHA256, ROOT

HETZNER = ROOT / "deploy" / "hetzner"
PACKAGER = HETZNER / "install_offbox_packaging.py"
PY = sys.executable
UNIT_NAMES = (
    "language-guard-offbox-handoff.socket",
    "language-guard-offbox-handoff@.service",
    "language-guard-offbox-worker.service",
    "language-guard-offbox.timer",
)


def _load_packager():
    spec = importlib.util.spec_from_file_location("install_offbox_packaging_trust", PACKAGER)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_frozen_module_bytes_unchanged() -> None:
    for name, expected in ACCEPTED_D5A2D0_P1_SHA256.items():
        path = HETZNER / "offbox" / name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected


def test_dependency_closure_stdlib_and_local_only() -> None:
    packager = _load_packager()
    per_file = packager.verify_dependency_closure(HETZNER / "offbox")
    assert set(per_file) == set(ACCEPTED_D5A2D0_P1_SHA256)


def test_verify_deps_cli_ok() -> None:
    result = subprocess.run(
        [PY, str(PACKAGER), "verify-deps"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "DEPS_OK" in result.stdout


def test_units_use_trusted_interpreter_and_execution_tree() -> None:
    packager = _load_packager()
    packager.verify_units(HETZNER)
    helper = (HETZNER / "language-guard-offbox-handoff@.service").read_text(encoding="utf-8")
    worker = (HETZNER / "language-guard-offbox-worker.service").read_text(encoding="utf-8")
    for text in (helper, worker):
        assert "/usr/bin/python3 -I /opt/language-guard-offbox/offbox/" in text
        assert "/opt/language-guard/venv/" not in text
        assert "/opt/language-guard/offbox/" not in text
        assert "venv/bin/python" not in text
        assert "PYTHONNOUSERSITE=1" in text
    assert "WorkingDirectory=/opt/language-guard-offbox/offbox" in helper
    assert "User=guard" in helper
    assert "User=lg-backup" in worker
    assert "LG_SOURCE_DB=/opt/language-guard/accounts.db" in helper
    assert "LG_SOURCE_DB=/opt/language-guard/accounts.db" in worker


def test_writable_parent_directory_replacement_is_unsafe() -> None:
    """Model the accepted UNSAFE audit: guard-writable /opt/language-guard."""
    packager = _load_packager()
    PathTrustMeta = packager.PathTrustMeta
    ancestors = [
        PathTrustMeta("/", "root", "root", 0o755, True, writable_by=frozenset()),
        PathTrustMeta("/opt", "root", "root", 0o755, True, writable_by=frozenset()),
        PathTrustMeta(
            "/opt/language-guard",
            "guard",
            "guard",
            0o755,
            True,
            writable_by=frozenset({"guard"}),
        ),
        PathTrustMeta(
            "/opt/language-guard/offbox",
            "root",
            "root",
            0o755,
            True,
            writable_by=frozenset(),
        ),
    ]
    result = packager.classify_execution_path_trust(
        ancestors=ancestors,
        interpreter_exec="/opt/language-guard/venv/bin/python",
        module_paths=["/opt/language-guard/offbox/backup_worker.py"],
    )
    assert result == "UNSAFE"


def test_interpreter_symlink_substitution_via_venv_is_unsafe() -> None:
    packager = _load_packager()
    PathTrustMeta = packager.PathTrustMeta
    ancestors = [
        PathTrustMeta("/", "root", "root", 0o755, True),
        PathTrustMeta("/opt", "root", "root", 0o755, True),
        PathTrustMeta("/opt/language-guard-offbox", "root", "root", 0o755, True),
        PathTrustMeta("/opt/language-guard-offbox/offbox", "root", "root", 0o755, True),
    ]
    assert (
        packager.classify_execution_path_trust(
            ancestors=ancestors,
            interpreter_exec="/opt/language-guard/venv/bin/python",
            module_paths=["/opt/language-guard-offbox/offbox/backup_worker.py"],
        )
        == "UNSAFE"
    )


def test_guard_owned_site_packages_path_rejected_by_unit_markers() -> None:
    """Units must not point at the guard-owned app venv / site-packages chain."""
    packager = _load_packager()
    with tempfile.TemporaryDirectory() as tmp:
        unit_dir = Path(tmp)
        for name in UNIT_NAMES:
            text = (HETZNER / name).read_text(encoding="utf-8")
            if name.endswith("worker.service"):
                text = text.replace(
                    "/usr/bin/python3 -I /opt/language-guard-offbox/offbox/backup_worker.py",
                    "/opt/language-guard/venv/bin/python /opt/language-guard-offbox/offbox/backup_worker.py",
                )
            (unit_dir / name).write_text(text, encoding="utf-8")
        with pytest.raises(ValueError, match="forbidden marker|/opt/language-guard/venv"):
            packager.verify_units(unit_dir)


def test_proposed_execution_tree_metadata_classifies_pass() -> None:
    packager = _load_packager()
    PathTrustMeta = packager.PathTrustMeta
    ancestors = [
        PathTrustMeta("/", "root", "root", 0o755, True, writable_by=frozenset()),
        PathTrustMeta("/opt", "root", "root", 0o755, True, writable_by=frozenset()),
        PathTrustMeta(
            "/opt/language-guard-offbox",
            "root",
            "root",
            0o755,
            True,
            writable_by=frozenset(),
        ),
        PathTrustMeta(
            "/opt/language-guard-offbox/offbox",
            "root",
            "root",
            0o755,
            True,
            writable_by=frozenset(),
        ),
    ]
    assert (
        packager.classify_execution_path_trust(
            ancestors=ancestors,
            interpreter_exec="/usr/bin/python3",
            module_paths=[
                "/opt/language-guard-offbox/offbox/backup_worker.py",
                "/opt/language-guard-offbox/offbox/snapshot_helper.py",
            ],
        )
        == "PASS"
    )


def test_ownership_permission_drift_expectations() -> None:
    packager = _load_packager()
    assert packager.EXPECTED_EXEC_OWNER == "root"
    assert packager.EXPECTED_EXEC_GROUP == "root"
    assert packager.EXPECTED_EXEC_DIR_MODE == 0o755
    assert packager.EXPECTED_EXEC_FILE_MODE == 0o644
    dest = Path("/opt/language-guard-offbox")
    expected = dict(packager.expected_execution_tree_modes(dest))
    assert expected[str(dest)] == 0o755
    assert expected[str(dest / "offbox" / "backup_worker.py")] == 0o644


def test_install_execution_tree_refuses_app_tree_destination(tmp_path: Path) -> None:
    packager = _load_packager()
    unsafe = tmp_path / "language-guard"
    unsafe.mkdir()
    with pytest.raises(ValueError, match="guard-owned app path"):
        packager.install_execution_tree(unsafe, hetzner_dir=HETZNER)


def test_install_execution_tree_ok_and_hash_faithful(tmp_path: Path) -> None:
    dest = tmp_path / "language-guard-offbox"
    result = subprocess.run(
        [PY, str(PACKAGER), "install-execution-tree", "--dest", str(dest)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "INSTALL_EXEC_OK" in result.stdout
    for name, expected in ACCEPTED_D5A2D0_P1_SHA256.items():
        staged = dest / "offbox" / name
        assert hashlib.sha256(staged.read_bytes()).hexdigest() == expected
    assert (dest / "deploy" / "hetzner" / "language-guard-offbox-worker.service").is_file()


def test_hash_mismatch_fail_closed_writes_nothing(tmp_path: Path) -> None:
    packager = _load_packager()
    fake_root = tmp_path / "hetzner"
    fake_offbox = fake_root / "offbox"
    fake_offbox.mkdir(parents=True)
    for path in (HETZNER / "offbox").iterdir():
        if path.is_file():
            (fake_offbox / path.name).write_bytes(path.read_bytes())
    for name in UNIT_NAMES + ("install_offbox_packaging.py", "offbox_report_lines.py"):
        (fake_root / name).write_bytes((HETZNER / name).read_bytes())
    (fake_offbox / "framing.py").write_bytes(b"tampered\n")
    dest = tmp_path / "language-guard-offbox"
    dest.mkdir()
    with pytest.raises(ValueError, match="hash mismatch|D5A2D0-P1"):
        packager.install_execution_tree(dest, hetzner_dir=fake_root)
    assert list(dest.rglob("*")) == []


def test_isolated_interpreter_imports_from_execution_tree(tmp_path: Path) -> None:
    """Offline: python -I imports frozen modules without user site / PYTHONPATH."""
    dest = tmp_path / "language-guard-offbox"
    assert (
        subprocess.run(
            [PY, str(PACKAGER), "install-execution-tree", "--dest", str(dest)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        ).returncode
        == 0
    )
    modules = dest / "offbox"
    script = (
        "import sys\n"
        f"sys.path.insert(0, {str(modules)!r})\n"
        "import framing, backup_worker, snapshot_helper\n"
        "print('IMPORT_OK', framing.__name__, backup_worker.__name__, snapshot_helper.__name__)\n"
    )
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env["PYTHONNOUSERSITE"] = "1"
    result = subprocess.run(
        [PY, "-I", "-c", script],
        cwd=str(modules),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    assert "IMPORT_OK" in result.stdout


def test_setup_sh_installs_execution_tree_not_app_offbox() -> None:
    text = (HETZNER / "setup.sh").read_text(encoding="utf-8")
    assert 'OFFBOX_EXEC_DIR="/opt/language-guard-offbox"' in text
    assert "install-execution-tree --dest" in text
    assert 'install-app-tree --dest "${APP_DIR}"' not in text
    assert 'chown -R root:root "${OFFBOX_EXEC_DIR}"' in text
    # APP_DIR chown must not be described as owning offbox modules.
    assert "Ownership for copied offbox tree is applied with the later chown of APP_DIR" not in text
