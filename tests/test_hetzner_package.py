"""Local check that the Hetzner file list can import the account server.

Does not run setup.sh, contact the VPS, or enable sync.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import sync_store

ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "deploy" / "hetzner" / "setup.sh"
REQUIRED = (
    "sync_http.py",
    "sync_store.py",
    "vocab_identity.py",
    "vocabulary_model.py",
)


def _packaged_python_files() -> list[str]:
    text = SETUP.read_text(encoding="utf-8")
    match = re.search(r"FILES=\((.*?)\)", text, re.S)
    assert match, "setup.sh FILES list missing"
    return re.findall(r"[A-Za-z0-9_./-]+\.py", match.group(1))


def test_packaged_account_server_imports_without_opening_sync_db(tmp_path):
    names = _packaged_python_files()
    for required in REQUIRED:
        assert required in names

    package = tmp_path / "language-guard"
    package.mkdir()
    for name in names:
        source = ROOT / "app" / name
        assert source.is_file(), name
        destination = package / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)

    app_sync = Path(sync_store.db_path())
    app_existed = app_sync.exists()
    env = os.environ.copy()
    env.pop("STUDY_SYNC_ENABLED", None)
    env.pop("STUDY_SYNC_DIR", None)
    env["PYTHONPATH"] = str(package)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    script = (
        "import os, pathlib\n"
        "os.environ.pop('STUDY_SYNC_ENABLED', None)\n"
        "os.environ.pop('STUDY_SYNC_DIR', None)\n"
        "import account_server\n"
        "assert account_server.sync_http.sync_enabled() is False\n"
        "assert list(pathlib.Path('.').rglob('study_sync.db')) == []\n"
        "print('import-ok')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(package),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "import-ok" in result.stdout
    assert list(package.rglob("study_sync.db")) == []
    assert list(tmp_path.rglob("study_sync.db")) == []
    assert app_sync.exists() == app_existed
