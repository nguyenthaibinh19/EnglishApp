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


def test_verify_fails_on_module_hash_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    packager = _load_packager()
    # Copy tree then mutate one module via a temporary offbox path.
    fake_root = tmp_path / "hetzner"
    fake_offbox = fake_root / "offbox"
    fake_offbox.mkdir(parents=True)
    src_offbox = HETZNER / "offbox"
    for path in src_offbox.iterdir():
        if path.is_file():
            (fake_offbox / path.name).write_bytes(path.read_bytes())
    target = fake_offbox / "logutil.py"
    target.write_bytes(target.read_bytes() + b"\n# tamper\n")
    with pytest.raises(ValueError, match="hash mismatch"):
        packager.verify_modules(fake_offbox)


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
