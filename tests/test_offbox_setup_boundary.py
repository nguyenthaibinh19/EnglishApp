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


def test_setup_sh_has_no_offbox_copy_or_install() -> None:
    text = SETUP.read_text(encoding="utf-8")
    lowered = text.lower()
    assert "offbox" not in lowered
    # No systemd unit install for offbox helpers/workers
    assert "language-guard-offbox" not in text
    assert "handoff@.service" not in text
    assert "snapshot_helper" not in text
    assert "backup_worker" not in text


def test_setup_sh_does_not_enable_offbox_units() -> None:
    text = SETUP.read_text(encoding="utf-8")
    # Enable lines must not activate offbox / handoff helper units.
    for line in text.splitlines():
        if "systemctl" in line and "enable" in line:
            lowered = line.lower()
            assert "offbox" not in lowered
            assert "handoff" not in lowered
            assert "snapshot_helper" not in lowered
            assert "backup_worker" not in lowered
            assert "language-guard-offbox" not in lowered
