"""Test group E — setup.sh deployment boundary (static, no execution)."""

from __future__ import annotations

import re
from pathlib import Path

from offbox_support import EXPECTED_MODULES, ROOT

SETUP = ROOT / "deploy" / "hetzner" / "setup.sh"
OPT_IN_GATE = '[[ "${LG_INSTALL_OFFBOX:-0}" == "1" ]]'
INSTALL_EXEC_TREE = "install-execution-tree --dest"


def _files_list(text: str) -> list[str]:
    match = re.search(r"FILES=\((.*?)\)", text, re.S)
    assert match, "setup.sh FILES list missing"
    return re.findall(r"[A-Za-z0-9_./-]+", match.group(1))


def _opt_in_block(text: str) -> str:
    assert OPT_IN_GATE in text
    _, gate, after = text.partition(OPT_IN_GATE)
    assert gate
    # First `fi` closes the opt-in block.
    block, _sep, _rest = after.partition("\nfi")
    return block


def test_setup_sh_exists() -> None:
    assert SETUP.is_file()


def test_files_list_excludes_all_offbox_modules() -> None:
    text = SETUP.read_text(encoding="utf-8")
    names = _files_list(text)
    for module in EXPECTED_MODULES:
        assert module not in names
        assert f"offbox/{module}" not in names
        assert f"deploy/hetzner/offbox/{module}" not in names


def test_setup_sh_default_path_does_not_copy_offbox_unconditionally() -> None:
    text = SETUP.read_text(encoding="utf-8")
    before_gate, gate, after_gate = text.partition(OPT_IN_GATE)
    assert gate, "missing LG_INSTALL_OFFBOX opt-in gate"
    assert "deploy/hetzner/offbox/" not in before_gate
    assert "snapshot_helper" not in before_gate
    assert "backup_worker" not in before_gate
    assert "install-execution-tree" not in before_gate
    assert "install-execution-tree" in after_gate
    assert 'OFFBOX_EXEC_DIR="/opt/language-guard-offbox"' in text


def test_setup_opt_in_requires_packager_before_any_offbox_copy() -> None:
    text = SETUP.read_text(encoding="utf-8")
    block = _opt_in_block(text)
    assert INSTALL_EXEC_TREE in block or "install-execution-tree" in block
    assert "install_offbox_packaging.py" in block
    assert "OFFBOX_EXEC_DIR" in block
    assert 'install-app-tree --dest "${APP_DIR}"' not in text
    # No raw module copy loop remains inside the opt-in path.
    assert "done <" not in block
    for line in block.splitlines():
        stripped = line.strip()
        if stripped.startswith("cp ") and "offbox/" in stripped:
            raise AssertionError(f"raw offbox cp before/without packager: {stripped}")


def test_setup_sh_never_installs_offbox_units_into_systemd() -> None:
    text = SETUP.read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "/etc/systemd/system/" in stripped and "cp " in stripped:
            lowered = stripped.lower()
            assert "offbox" not in lowered
            assert "handoff" not in lowered


def test_setup_sh_does_not_enable_offbox_units() -> None:
    text = SETUP.read_text(encoding="utf-8")
    for line in text.splitlines():
        if "systemctl" in line and "enable" in line:
            lowered = line.lower()
            assert "offbox" not in lowered
            assert "handoff" not in lowered
            assert "snapshot_helper" not in lowered
            assert "backup_worker" not in lowered
            assert "language-guard-offbox" not in lowered
