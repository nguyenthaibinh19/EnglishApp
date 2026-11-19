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


def _clone_units(tmp: Path) -> Path:
    for name in UNIT_NAMES:
        (tmp / name).write_text((HETZNER / name).read_text(encoding="utf-8"), encoding="utf-8")
    return tmp


def _trusted_path_meta(packager, *, include_modules: bool = True):
    PathTrustMeta = packager.PathTrustMeta
    empty = frozenset()
    metas = [
        PathTrustMeta("/", "root", "root", 0o755, True, acl_extra_write_principals=empty),
        PathTrustMeta("/opt", "root", "root", 0o755, True, acl_extra_write_principals=empty),
        PathTrustMeta(
            "/opt/language-guard-offbox",
            "root",
            "root",
            0o755,
            True,
            acl_extra_write_principals=empty,
        ),
        PathTrustMeta(
            "/opt/language-guard-offbox/offbox",
            "root",
            "root",
            0o755,
            True,
            acl_extra_write_principals=empty,
        ),
        PathTrustMeta("/usr", "root", "root", 0o755, True, acl_extra_write_principals=empty),
        PathTrustMeta("/usr/bin", "root", "root", 0o755, True, acl_extra_write_principals=empty),
        PathTrustMeta(
            "/usr/bin/python3",
            "root",
            "root",
            0o777,
            False,
            is_symlink=True,
            symlink_target="/usr/bin/python3.14",
            acl_extra_write_principals=empty,
        ),
        PathTrustMeta(
            "/usr/bin/python3.14",
            "root",
            "root",
            0o755,
            False,
            acl_extra_write_principals=empty,
        ),
    ]
    if include_modules:
        for name in ("backup_worker.py", "snapshot_helper.py"):
            metas.append(
                PathTrustMeta(
                    f"/opt/language-guard-offbox/offbox/{name}",
                    "root",
                    "root",
                    0o644,
                    False,
                    acl_extra_write_principals=empty,
                )
            )
    return metas


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
        assert "venv/bin/python" not in text
        assert "PYTHONNOUSERSITE=1" in text


def test_verify_units_rejects_commented_expected_execstart_with_active_override(
    tmp_path: Path,
) -> None:
    packager = _load_packager()
    unit_dir = _clone_units(tmp_path)
    worker = unit_dir / "language-guard-offbox-worker.service"
    text = worker.read_text(encoding="utf-8")
    text = text.replace(
        "ExecStart=/usr/bin/python3 -I /opt/language-guard-offbox/offbox/backup_worker.py",
        (
            "# ExecStart=/usr/bin/python3 -I /opt/language-guard-offbox/offbox/backup_worker.py\n"
            "ExecStart=/tmp/evil-python /tmp/evil_worker.py"
        ),
    )
    worker.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="ExecStart"):
        packager.verify_units(unit_dir)


def test_verify_units_rejects_duplicate_execstart(tmp_path: Path) -> None:
    packager = _load_packager()
    unit_dir = _clone_units(tmp_path)
    worker = unit_dir / "language-guard-offbox-worker.service"
    text = worker.read_text(encoding="utf-8")
    text += (
        "\nExecStart=/usr/bin/python3 -I "
        "/opt/language-guard-offbox/offbox/backup_worker.py\n"
    )
    worker.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate active|exactly one active ExecStart"):
        packager.verify_units(unit_dir)


def test_writable_parent_directory_replacement_is_unsafe() -> None:
    packager = _load_packager()
    PathTrustMeta = packager.PathTrustMeta
    empty = frozenset()
    path_meta = [
        PathTrustMeta("/", "root", "root", 0o755, True, acl_extra_write_principals=empty),
        PathTrustMeta("/opt", "root", "root", 0o755, True, acl_extra_write_principals=empty),
        PathTrustMeta(
            "/opt/language-guard",
            "guard",
            "guard",
            0o755,
            True,
            writable_by=frozenset({"guard"}),
            acl_extra_write_principals=empty,
        ),
        PathTrustMeta(
            "/opt/language-guard/offbox",
            "root",
            "root",
            0o755,
            True,
            acl_extra_write_principals=empty,
        ),
        PathTrustMeta(
            "/opt/language-guard/offbox/backup_worker.py",
            "root",
            "root",
            0o644,
            False,
            acl_extra_write_principals=empty,
        ),
        PathTrustMeta("/usr", "root", "root", 0o755, True, acl_extra_write_principals=empty),
        PathTrustMeta("/usr/bin", "root", "root", 0o755, True, acl_extra_write_principals=empty),
        PathTrustMeta(
            "/usr/bin/python3",
            "root",
            "root",
            0o755,
            False,
            acl_extra_write_principals=empty,
        ),
    ]
    assert (
        packager.classify_execution_path_trust(
            path_meta=path_meta,
            interpreter_exec="/opt/language-guard/venv/bin/python",
            interpreter_resolved="/usr/bin/python3.14",
            module_paths=["/opt/language-guard/offbox/backup_worker.py"],
        )
        == "UNSAFE"
    )


def test_interpreter_symlink_substitution_via_venv_is_unsafe() -> None:
    packager = _load_packager()
    metas = _trusted_path_meta(packager)
    assert (
        packager.classify_execution_path_trust(
            path_meta=metas,
            interpreter_exec="/opt/language-guard/venv/bin/python",
            interpreter_resolved="/usr/bin/python3.14",
            module_paths=["/opt/language-guard-offbox/offbox/backup_worker.py"],
        )
        == "UNSAFE"
    )


def test_interpreter_lookalike_path_is_unsafe() -> None:
    packager = _load_packager()
    metas = _trusted_path_meta(packager)
    assert (
        packager.classify_execution_path_trust(
            path_meta=metas,
            interpreter_exec="/usr/bin/python3-evil",
            interpreter_resolved="/usr/bin/python3-evil",
            module_paths=["/opt/language-guard-offbox/offbox/backup_worker.py"],
        )
        == "UNSAFE"
    )


def test_world_writable_ancestor_without_writable_by_is_unsafe() -> None:
    """False-PASS guard: root-owned 0777 ancestor must not classify PASS."""
    packager = _load_packager()
    PathTrustMeta = packager.PathTrustMeta
    empty = frozenset()
    metas = _trusted_path_meta(packager)
    # Replace /opt with world-writable metadata and an empty writable_by set.
    metas = [
        m
        if m.path != "/opt"
        else PathTrustMeta(
            "/opt",
            "root",
            "root",
            0o777,
            True,
            writable_by=frozenset(),
            acl_extra_write_principals=empty,
        )
        for m in metas
    ]
    assert (
        packager.classify_execution_path_trust(
            path_meta=metas,
            interpreter_exec="/usr/bin/python3",
            interpreter_resolved="/usr/bin/python3.14",
            module_paths=["/opt/language-guard-offbox/offbox/backup_worker.py"],
        )
        == "UNSAFE"
    )


def test_group_writable_executable_leaf_is_unsafe() -> None:
    packager = _load_packager()
    PathTrustMeta = packager.PathTrustMeta
    empty = frozenset()
    metas = []
    for meta in _trusted_path_meta(packager):
        if meta.path.endswith("backup_worker.py"):
            metas.append(
                PathTrustMeta(
                    meta.path,
                    "root",
                    "root",
                    0o664,
                    False,
                    acl_extra_write_principals=empty,
                )
            )
        else:
            metas.append(meta)
    assert (
        packager.classify_execution_path_trust(
            path_meta=metas,
            interpreter_exec="/usr/bin/python3",
            interpreter_resolved="/usr/bin/python3.14",
            module_paths=["/opt/language-guard-offbox/offbox/backup_worker.py"],
        )
        == "UNSAFE"
    )


def test_missing_acl_evidence_is_unknown() -> None:
    packager = _load_packager()
    PathTrustMeta = packager.PathTrustMeta
    metas = []
    for meta in _trusted_path_meta(packager):
        if meta.path == "/opt/language-guard-offbox":
            metas.append(
                PathTrustMeta(
                    meta.path,
                    meta.owner,
                    meta.group,
                    meta.mode,
                    meta.is_dir,
                    acl_extra_write_principals=None,
                )
            )
        else:
            metas.append(meta)
    assert (
        packager.classify_execution_path_trust(
            path_meta=metas,
            interpreter_exec="/usr/bin/python3",
            interpreter_resolved="/usr/bin/python3.14",
            module_paths=["/opt/language-guard-offbox/offbox/backup_worker.py"],
        )
        == "UNKNOWN"
    )


def test_missing_interpreter_resolution_is_unknown() -> None:
    packager = _load_packager()
    assert (
        packager.classify_execution_path_trust(
            path_meta=_trusted_path_meta(packager),
            interpreter_exec="/usr/bin/python3",
            interpreter_resolved=None,
            module_paths=["/opt/language-guard-offbox/offbox/backup_worker.py"],
        )
        == "UNKNOWN"
    )


def test_guard_owned_site_packages_path_rejected_by_unit_markers() -> None:
    packager = _load_packager()
    with tempfile.TemporaryDirectory() as tmp:
        unit_dir = _clone_units(Path(tmp))
        worker = unit_dir / "language-guard-offbox-worker.service"
        text = worker.read_text(encoding="utf-8")
        text = text.replace(
            "/usr/bin/python3 -I /opt/language-guard-offbox/offbox/backup_worker.py",
            "/opt/language-guard/venv/bin/python /opt/language-guard-offbox/offbox/backup_worker.py",
        )
        worker.write_text(text, encoding="utf-8")
        with pytest.raises(ValueError, match="forbidden marker|ExecStart"):
            packager.verify_units(unit_dir)


def test_proposed_execution_tree_metadata_classifies_pass() -> None:
    packager = _load_packager()
    assert (
        packager.classify_execution_path_trust(
            path_meta=_trusted_path_meta(packager),
            interpreter_exec="/usr/bin/python3",
            interpreter_resolved="/usr/bin/python3.14",
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
        packager.install_execution_tree(unsafe, hetzner_dir=HETZNER, production=False)


def test_production_install_requires_exact_execution_root(tmp_path: Path) -> None:
    packager = _load_packager()
    dest = tmp_path / "language-guard-offbox"
    dest.mkdir()
    with pytest.raises(ValueError, match="exactly /opt/language-guard-offbox"):
        packager.install_execution_tree(dest, hetzner_dir=HETZNER, production=True)
    assert list(dest.iterdir()) == []


def test_install_refuses_symlink_destination(tmp_path: Path) -> None:
    packager = _load_packager()
    real = tmp_path / "real-offbox"
    real.mkdir()
    link = tmp_path / "language-guard-offbox"
    try:
        link.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation unavailable on this host")
    with pytest.raises(ValueError, match="symlink"):
        packager.install_execution_tree(link, hetzner_dir=HETZNER, production=False)


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
    assert "production=0" in result.stdout
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
        packager.install_execution_tree(dest, hetzner_dir=fake_root, production=False)
    assert list(dest.rglob("*")) == []


def test_isolated_interpreter_imports_from_execution_tree(tmp_path: Path) -> None:
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
    assert "--production" in text
    assert 'install-app-tree --dest "${APP_DIR}"' not in text
    assert 'chown -R root:root "${OFFBOX_EXEC_DIR}"' in text
