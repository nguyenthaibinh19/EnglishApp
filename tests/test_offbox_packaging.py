"""Packaging, unit-template, and staging regression tests (offline)."""

from __future__ import annotations

import hashlib
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

from offbox_support import ACCEPTED_D5A2D0_P1_SHA256, EXPECTED_MODULES, ROOT

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
    spec = importlib.util.spec_from_file_location("install_offbox_packaging", PACKAGER)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_packager_verify_cli_ok() -> None:
    result = subprocess.run(
        [PY, str(PACKAGER), "verify"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "VERIFY_OK" in result.stdout
    assert "modules=15" in result.stdout


def test_resolve_offbox_dir_repo_layout() -> None:
    packager = _load_packager()
    resolved = packager.resolve_offbox_dir(HETZNER)
    assert resolved == HETZNER / "offbox"
    assert (resolved / "SHA256SUMS").is_file()


def test_resolve_offbox_dir_and_verify_from_production_layout(tmp_path: Path) -> None:
    """Installed tree: <root>/offbox + <root>/deploy/hetzner/packager."""
    packager = _load_packager()
    dest = tmp_path / "language-guard-offbox"
    written = packager.install_execution_tree(dest, hetzner_dir=HETZNER, production=False)
    assert written
    installed_packager = dest / "deploy" / "hetzner" / "install_offbox_packaging.py"
    assert installed_packager.is_file()
    assert not (dest / "deploy" / "hetzner" / "offbox").exists()

    # Load the *installed* copy so HERE resolves under deploy/hetzner.
    spec = importlib.util.spec_from_file_location(
        "install_offbox_packaging_installed", installed_packager
    )
    assert spec and spec.loader
    installed = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = installed
    spec.loader.exec_module(installed)

    resolved = installed.resolve_offbox_dir()
    assert resolved.resolve() == (dest / "offbox").resolve()
    listed = installed.verify_modules(resolved)
    assert len(listed) == 15
    installed.verify_units(dest / "deploy" / "hetzner")
    installed.verify_dependency_closure(resolved)

    cli = subprocess.run(
        [PY, str(installed_packager), "verify"],
        cwd=str(dest / "deploy" / "hetzner"),
        capture_output=True,
        text=True,
        check=False,
    )
    assert cli.returncode == 0, cli.stderr
    assert "VERIFY_OK" in cli.stdout
    assert "modules=15" in cli.stdout
    deps = subprocess.run(
        [PY, str(installed_packager), "verify-deps"],
        cwd=str(dest / "deploy" / "hetzner"),
        capture_output=True,
        text=True,
        check=False,
    )
    assert deps.returncode == 0, deps.stderr
    assert "DEPS_OK" in deps.stdout


def test_stage_is_idempotent_and_hash_faithful(tmp_path: Path) -> None:
    dest = tmp_path / "stage"
    first = subprocess.run(
        [PY, str(PACKAGER), "stage", "--dest", str(dest)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert first.returncode == 0, first.stderr
    second = subprocess.run(
        [PY, str(PACKAGER), "stage", "--dest", str(dest)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert second.returncode == 0, second.stderr
    for name, expected in ACCEPTED_D5A2D0_P1_SHA256.items():
        staged = dest / "offbox" / name
        assert staged.is_file()
        assert hashlib.sha256(staged.read_bytes()).hexdigest() == expected


def test_stage_refuses_content_conflict(tmp_path: Path) -> None:
    dest = tmp_path / "stage"
    assert (
        subprocess.run(
            [PY, str(PACKAGER), "stage", "--dest", str(dest)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        ).returncode
        == 0
    )
    victim = dest / "offbox" / "framing.py"
    victim.write_bytes(b"tampered-not-canonical\n")
    conflict = subprocess.run(
        [PY, str(PACKAGER), "stage", "--dest", str(dest)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert conflict.returncode == 1
    assert "FAIL" in conflict.stderr


def _clone_hetzner_tree(tmp_path: Path) -> Path:
    fake_root = tmp_path / "hetzner"
    fake_offbox = fake_root / "offbox"
    fake_offbox.mkdir(parents=True)
    for path in (HETZNER / "offbox").iterdir():
        if path.is_file():
            (fake_offbox / path.name).write_bytes(path.read_bytes())
    for name in UNIT_NAMES + ("install_offbox_packaging.py", "offbox_report_lines.py"):
        (fake_root / name).write_bytes((HETZNER / name).read_bytes())
    return fake_root


def test_verify_fails_on_module_hash_mismatch(tmp_path: Path) -> None:
    packager = _load_packager()
    fake_root = _clone_hetzner_tree(tmp_path)
    target = fake_root / "offbox" / "logutil.py"
    target.write_bytes(target.read_bytes() + b"\n# tamper\n")
    with pytest.raises(ValueError, match="hash mismatch"):
        packager.verify_modules(fake_root / "offbox")


def test_verify_rejects_tampered_module_even_if_manifest_rewritten(tmp_path: Path) -> None:
    """Local SHA256SUMS alone cannot authorize packaging."""
    packager = _load_packager()
    fake_root = _clone_hetzner_tree(tmp_path)
    offbox = fake_root / "offbox"
    target = offbox / "framing.py"
    target.write_bytes(b"tampered-source-bytes\n")
    # Rewrite the mutable manifest to match the tampered bytes.
    lines = []
    for name, digest in packager.ACCEPTED_D5A2D0_P1_SHA256.items():
        if name == "framing.py":
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
        lines.append(f"{digest}  {name}")
    (offbox / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="D5A2D0-P1|hash mismatch"):
        packager.verify_modules(offbox)


def test_install_execution_tree_refuses_tampered_source_and_writes_nothing(tmp_path: Path) -> None:
    packager = _load_packager()
    fake_root = _clone_hetzner_tree(tmp_path)
    (fake_root / "offbox" / "age_encrypt.py").write_bytes(b"not-canonical\n")
    dest = tmp_path / "language-guard-offbox"
    dest.mkdir()
    with pytest.raises(ValueError, match="hash mismatch|D5A2D0-P1"):
        packager.install_execution_tree(dest, hetzner_dir=fake_root)
    assert list(dest.rglob("*")) == []


def test_install_execution_tree_ok_against_pinned_inventory(tmp_path: Path) -> None:
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
    assert "inventory=D5A2D0-P1" in result.stdout
    for name, expected in ACCEPTED_D5A2D0_P1_SHA256.items():
        staged = dest / "offbox" / name
        assert hashlib.sha256(staged.read_bytes()).hexdigest() == expected
    assert (dest / "deploy" / "hetzner" / "language-guard-offbox-worker.service").is_file()


def test_legacy_install_app_tree_alias_refuses_language_guard_dest(tmp_path: Path) -> None:
    dest = tmp_path / "language-guard"
    dest.mkdir()
    result = subprocess.run(
        [PY, str(PACKAGER), "install-app-tree", "--dest", str(dest)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "FAIL" in result.stderr
    assert "guard-owned app path" in result.stderr


def test_unit_templates_have_isolation_markers() -> None:
    packager = _load_packager()
    packager.verify_units(HETZNER)
    helper = (HETZNER / "language-guard-offbox-handoff@.service").read_text(encoding="utf-8")
    worker = (HETZNER / "language-guard-offbox-worker.service").read_text(encoding="utf-8")
    assert "StandardError=journal" in helper
    assert "StandardOutput=socket" in helper
    worker_active = [
        line.strip()
        for line in worker.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert not any(line.startswith("StateDirectory=") for line in worker_active)
    assert not any(line.startswith("LG_DRIVE_FOLDER=") for line in worker_active)
    assert not any(line.startswith("LG_UPLOAD_ENABLED=") for line in worker_active)
    assert "/mnt/d/Tools/" not in helper
    assert "/mnt/d/Tools/" not in worker
    for name in UNIT_NAMES:
        assert (HETZNER / name).is_file()


def test_incorrect_unit_config_is_rejected(tmp_path: Path) -> None:
    packager = _load_packager()
    bad = tmp_path / "units"
    bad.mkdir()
    for name in UNIT_NAMES:
        text = (HETZNER / name).read_text(encoding="utf-8")
        if name.endswith("worker.service"):
            text += "\nStateDirectory=language-guard-backup\n"
        (bad / name).write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="StateDirectory|forbidden"):
        packager.verify_units(bad)


def test_packager_does_not_invoke_remote_or_enable_actions() -> None:
    text = PACKAGER.read_text(encoding="utf-8")
    assert "import subprocess" not in text
    assert "os.system" not in text
    assert "paramiko" not in text.lower()
    # Guard strings used only when validating unit templates are fine;
    # the packager itself must not shell out to enable/start.
    assert "os.system(" not in text
    assert "Popen(" not in text
    assert "ssh " not in text.lower()
