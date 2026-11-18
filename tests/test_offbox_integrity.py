"""Test group A — frozen offbox source integrity."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from offbox_support import (
    ACCEPTED_D5A2D0_P1_SHA256,
    EXPECTED_ALLOWLIST,
    EXPECTED_MODULES,
    IGNORED_OFFBOX_DIR_NAMES,
    OFFBOX,
)

ROOT = Path(__file__).resolve().parents[1]


def _parse_sha256sums(path: Path) -> dict[str, str]:
    listed: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        assert len(parts) == 2, f"malformed SHA256SUMS line: {line!r}"
        digest, name = parts
        assert len(digest) == 64 and all(c in "0123456789abcdef" for c in digest), digest
        assert name not in listed, f"duplicate SHA256SUMS entry: {name}"
        listed[name] = digest
    return listed


def test_offbox_directory_exists() -> None:
    assert OFFBOX.is_dir()


def test_exact_allowlist_inventory() -> None:
    names = sorted(p.name for p in OFFBOX.iterdir() if p.is_file())
    assert names == sorted(EXPECTED_ALLOWLIST)


def test_no_unexpected_executables_or_extra_sources() -> None:
    for path in OFFBOX.iterdir():
        if path.is_symlink():
            raise AssertionError(f"symlink not allowed in frozen offbox: {path}")
        if path.is_dir():
            assert path.name in IGNORED_OFFBOX_DIR_NAMES, (
                f"unexpected directory in frozen offbox: {path.name}"
            )
            continue
        assert path.is_file(), f"unexpected non-file: {path}"
        assert path.name in EXPECTED_ALLOWLIST
        assert not path.name.endswith((".exe", ".so", ".dll", ".bin"))
        assert path.name not in {
            "fake_drive.py",
            "loopback_drive.py",
            "live_synthetic_once.py",
        }


def test_sha256sums_matches_each_module() -> None:
    listed = _parse_sha256sums(OFFBOX / "SHA256SUMS")
    assert set(listed) == set(EXPECTED_MODULES)
    for name in EXPECTED_MODULES:
        got = hashlib.sha256((OFFBOX / name).read_bytes()).hexdigest()
        assert got == listed[name], name


def test_modules_match_accepted_d5a2d0_p1_pinned_hashes() -> None:
    """Pin against the accepted D5A2D0-P1 inventory, not only the local manifest."""
    assert set(ACCEPTED_D5A2D0_P1_SHA256) == set(EXPECTED_MODULES)
    listed = _parse_sha256sums(OFFBOX / "SHA256SUMS")
    assert listed == ACCEPTED_D5A2D0_P1_SHA256
    for name, expected in ACCEPTED_D5A2D0_P1_SHA256.items():
        got = hashlib.sha256((OFFBOX / name).read_bytes()).hexdigest()
        assert got == expected, name


def test_python_runtime_assumption_documented() -> None:
    # Offbox uses PEP604 unions (X | Y); runtime requires Python >= 3.10.
    assert sys.version_info >= (3, 10)
    assert (OFFBOX / "SOURCE_AUTHORITY.md").is_file()
