"""Test group D — import smoke without production deps or network."""

from __future__ import annotations

import importlib
import sys

import pytest

from offbox_support import EXPECTED_MODULES, ensure_offbox_on_path


def test_python_version_at_least_3_10() -> None:
    """Offbox modules use PEP 604 unions; document runtime assumption."""
    assert sys.version_info >= (3, 10), (
        "offbox modules require Python >= 3.10 (uses X | Y annotations)"
    )


@pytest.mark.parametrize("module_name", [name[:-3] for name in EXPECTED_MODULES])
def test_offbox_module_imports_without_network_or_credentials(module_name: str) -> None:
    ensure_offbox_on_path()
    # Drop any prior import so this exercises the candidate tree.
    for key in list(sys.modules):
        if key == module_name or key.startswith(module_name + "."):
            del sys.modules[key]
    mod = importlib.import_module(module_name)
    assert mod is not None
