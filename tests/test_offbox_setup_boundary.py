"""Test group E — setup.sh deployment boundary (static, no execution)."""

from __future__ import annotations

import re
from pathlib import Path

from offbox_support import EXPECTED_MODULES, ROOT

SETUP = ROOT / "deploy" / "hetzner" / "setup.sh"


def _files_list(text: str) -> list[str]:
    match = re.search(r"FILES=\((.*?)\)", text, re.S)
    assert match, "setup.sh FILES list missing"
    return re.findall(r"[A-Za-z0-9_./-]+", match.group(1))


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
    assert '[[ "${LG_INSTALL_OFFBOX:-0}" == "1" ]]' in text
    # Default production behavior stays free of unconditional offbox install paths.
    before_gate, gate, after_gate = text.partition('[[ "${LG_INSTALL_OFFBOX:-0}" == "1" ]]')
    assert gate, "missing LG_INSTALL_OFFBOX opt-in gate"
    assert "deploy/hetzner/offbox/" not in before_gate
    assert "language-guard-offbox" not in before_gate
    assert "snapshot_helper" not in before_gate
    assert "backup_worker" not in before_gate
    assert "deploy/hetzner/offbox/" in after_gate
    assert "language-guard-offbox-handoff.socket" in after_gate


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
