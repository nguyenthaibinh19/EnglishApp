"""Installation safety. Temporary paths and mocks only; no real executable launch."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import install
import updater


class _Record:
    def __init__(self) -> None:
        self.seeds = 0
        self.notices = 0
        self.startup_stops = 0
        self.startup: list[str] = []
        self.launches: list[tuple[list[str], str | None]] = []


def _bind(monkeypatch, tmp_path: Path, *, frozen: bool, executable: Path, installed: Path) -> _Record:
    record = _Record()
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData"))
    monkeypatch.setattr(install.config, "is_frozen", lambda: frozen)
    monkeypatch.setattr(install.config, "installed_exe", lambda: str(installed))
    monkeypatch.setattr(sys, "executable", str(executable), raising=False)

    def seed() -> None:
        record.seeds += 1

    def notify() -> None:
        record.notices += 1

    def notify_startup() -> None:
        record.startup_stops += 1

    def register(path: str) -> None:
        record.startup.append(path)

    def popen(args, cwd=None, close_fds=False):
        record.launches.append((list(args), cwd))
        return object()

    monkeypatch.setattr(install, "seed_vocab", seed)
    monkeypatch.setattr(install, "_notify_existing_installation", notify)
    monkeypatch.setattr(install, "_notify_existing_startup", notify_startup)
    monkeypatch.setattr(install, "register_startup", register)
    monkeypatch.setattr(install.subprocess, "Popen", popen)
    return record


def _write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


@pytest.mark.parametrize("argv", [["langstudyguard.exe"], ["langstudyguard.exe", "--lock"]])
def test_installed_launch_does_not_rewrite_startup(tmp_path, monkeypatch, argv):
    installed = tmp_path / "Local" / "langstudyguard" / "langstudyguard.exe"
    _write(installed, b"installed-build")
    record = _bind(monkeypatch, tmp_path, frozen=True, executable=installed, installed=installed)
    monkeypatch.setattr(sys, "argv", argv)

    assert install.prepare() is True

    assert installed.read_bytes() == b"installed-build"
    assert record.seeds == 1
    assert record.startup == []
    assert record.launches == []
    assert record.notices == 0
    assert not (tmp_path / "AppData").exists()


def test_external_executable_cannot_overwrite_installed_executable(tmp_path, monkeypatch):
    installed = tmp_path / "Local" / "langstudyguard" / "langstudyguard.exe"
    external = tmp_path / "dist" / "langstudyguard.exe"
    _write(installed, b"newer-installed")
    _write(external, b"old-external")
    record = _bind(monkeypatch, tmp_path, frozen=True, executable=external, installed=installed)

    assert install.prepare() is False

    assert installed.read_bytes() == b"newer-installed"
    assert external.read_bytes() == b"old-external"
    assert record.notices == 1
    assert record.startup == []
    assert record.launches == []
    assert record.seeds == 0


def test_external_executable_does_not_launch_installed_application(tmp_path, monkeypatch):
    installed = tmp_path / "installed.exe"
    external = tmp_path / "other.exe"
    _write(installed, b"kept")
    _write(external, b"other")
    record = _bind(monkeypatch, tmp_path, frozen=True, executable=external, installed=installed)

    assert install.prepare() is False

    assert record.launches == []
    assert installed.read_bytes() == b"kept"


def test_first_installation_copies_registers_startup_and_launches(tmp_path, monkeypatch):
    installed = tmp_path / "Local" / "langstudyguard" / "langstudyguard.exe"
    external = tmp_path / "first" / "langstudyguard.exe"
    payload = b"first-install-bytes"
    _write(external, payload)
    record = _bind(monkeypatch, tmp_path, frozen=True, executable=external, installed=installed)

    assert install.prepare() is False

    assert installed.read_bytes() == payload
    assert record.startup == [str(installed)]
    assert record.launches == [([str(installed)], str(installed.parent))]
    assert record.notices == 0
    assert record.seeds == 0


def test_startup_shortcut_is_part_of_first_install_only():
    import inspect

    startup = inspect.getsource(install.register_startup)
    prepare_source = inspect.getsource(install.prepare)
    installed_body, remainder = prepare_source.split("if _same_path(current, dest):", 1)[1].split(
        "if os.path.lexists(dest):", 1
    )
    assert "$sc.Arguments = '--lock';" in startup
    assert "Dutch Guard.lnk" not in startup
    assert "seed_vocab()" in installed_body
    assert "register_startup" not in installed_body
    assert "register_startup(dest)" in remainder


def test_incomplete_copy_leaves_no_installed_file(tmp_path, monkeypatch):
    installed = tmp_path / "Local" / "langstudyguard" / "langstudyguard.exe"
    external = tmp_path / "partial.exe"
    _write(external, b"complete-source")
    record = _bind(monkeypatch, tmp_path, frozen=True, executable=external, installed=installed)

    def fail_mid_copy(_source, target) -> None:
        target.write(b"partial")
        raise OSError("disk full")

    monkeypatch.setattr(install.shutil, "copyfileobj", fail_mid_copy)

    with pytest.raises(OSError, match="disk full"):
        install.prepare()

    assert not installed.exists()
    assert record.startup == []
    assert record.launches == []


def _startup_folder(tmp_path: Path) -> Path:
    folder = tmp_path / "AppData" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def test_failed_startup_registration_rolls_back_new_install(tmp_path, monkeypatch):
    installed = tmp_path / "Local" / "langstudyguard" / "langstudyguard.exe"
    external = tmp_path / "first.exe"
    _write(external, b"first")
    real_register = install.register_startup
    record = _bind(monkeypatch, tmp_path, frozen=True, executable=external, installed=installed)
    monkeypatch.setattr(install, "register_startup", real_register)
    legacy = _startup_folder(tmp_path) / "Dutch Guard.lnk"
    unrelated = legacy.with_name("unrelated.lnk")
    legacy.write_bytes(b"legacy-bytes")
    unrelated.write_bytes(b"unrelated-bytes")

    def fail_run(args, check=False, creationflags=0):
        raise OSError("startup failed")

    monkeypatch.setattr(install.subprocess, "run", fail_run)

    with pytest.raises(OSError, match="startup failed"):
        install.prepare()

    assert not installed.exists()
    assert not (legacy.parent / "langstudyguard.lnk").exists()
    assert legacy.read_bytes() == b"legacy-bytes"
    assert unrelated.read_bytes() == b"unrelated-bytes"
    assert record.launches == []


def test_existing_startup_shortcut_stops_before_install(tmp_path, monkeypatch):
    installed = tmp_path / "Local" / "langstudyguard" / "langstudyguard.exe"
    external = tmp_path / "first.exe"
    _write(external, b"first")
    record = _bind(monkeypatch, tmp_path, frozen=True, executable=external, installed=installed)
    shortcut = tmp_path / "AppData" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    shortcut.mkdir(parents=True)
    existing = shortcut / "langstudyguard.lnk"
    existing.write_text("keep", encoding="utf-8")
    unrelated = shortcut / "unrelated.lnk"
    unrelated.write_text("leave", encoding="utf-8")

    def fail_register(_path: str) -> None:
        raise AssertionError("must not rewrite an existing Startup shortcut")

    monkeypatch.setattr(install, "register_startup", fail_register)

    assert install.prepare() is False

    assert not installed.exists()
    assert external.read_bytes() == b"first"
    assert existing.read_text(encoding="utf-8") == "keep"
    assert unrelated.read_text(encoding="utf-8") == "leave"
    assert record.startup_stops == 1
    assert record.launches == []


def test_shortcut_appearing_during_copy_is_left_unchanged(tmp_path, monkeypatch):
    installed = tmp_path / "Local" / "langstudyguard" / "langstudyguard.exe"
    external = tmp_path / "first.exe"
    _write(external, b"first")
    record = _bind(monkeypatch, tmp_path, frozen=True, executable=external, installed=installed)
    shortcut = tmp_path / "AppData" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    shortcut.mkdir(parents=True)
    existing = shortcut / "langstudyguard.lnk"
    seen = {"calls": 0}

    def appears_after_first_check() -> bool:
        seen["calls"] += 1
        if seen["calls"] >= 2:
            existing.write_text("appeared", encoding="utf-8")
            return True
        return False

    monkeypatch.setattr(install, "_startup_link_exists", appears_after_first_check)

    assert install.prepare() is False

    assert not installed.exists()
    assert existing.read_text(encoding="utf-8") == "appeared"
    assert record.startup == []
    assert record.launches == []
    assert record.startup_stops == 1


def test_successful_first_install_preserves_preexisting_shortcuts(tmp_path, monkeypatch):
    installed = tmp_path / "Local" / "langstudyguard" / "langstudyguard.exe"
    external = tmp_path / "first.exe"
    _write(external, b"first-install-bytes")
    real_register = install.register_startup
    record = _bind(monkeypatch, tmp_path, frozen=True, executable=external, installed=installed)
    monkeypatch.setattr(install, "register_startup", real_register)
    folder = _startup_folder(tmp_path)
    legacy = folder / "Dutch Guard.lnk"
    unrelated = folder / "unrelated.lnk"
    legacy.write_bytes(b"legacy-bytes")
    unrelated.write_bytes(b"unrelated-bytes")

    def allow_run(args, check=False, creationflags=0):
        return install.subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(install.subprocess, "run", allow_run)

    assert install.prepare() is False

    assert installed.read_bytes() == b"first-install-bytes"
    assert legacy.read_bytes() == b"legacy-bytes"
    assert unrelated.read_bytes() == b"unrelated-bytes"
    assert (folder / "langstudyguard.lnk").is_file()
    assert record.launches == [([str(installed)], str(installed.parent))]


def test_failed_registration_leaves_preexisting_shortcut_bytes_unchanged(tmp_path, monkeypatch):
    installed = tmp_path / "Local" / "langstudyguard" / "langstudyguard.exe"
    external = tmp_path / "first.exe"
    _write(external, b"first")
    real_register = install.register_startup
    record = _bind(monkeypatch, tmp_path, frozen=True, executable=external, installed=installed)
    monkeypatch.setattr(install, "register_startup", real_register)
    monkeypatch.setattr(install.config, "ui", lambda _vi, en: en)
    folder = _startup_folder(tmp_path)
    existing = folder / "langstudyguard.lnk"
    legacy = folder / "Dutch Guard.lnk"
    existing.write_bytes(b"original-link")
    legacy.write_bytes(b"legacy-bytes")

    def refuse_run(args, check=False, creationflags=0):
        raise AssertionError("registration must not launch PowerShell")

    monkeypatch.setattr(install.subprocess, "run", refuse_run)

    assert install.prepare() is False
    with pytest.raises(OSError, match="was not changed"):
        install.register_startup(str(installed))

    assert not installed.exists()
    assert existing.read_bytes() == b"original-link"
    assert legacy.read_bytes() == b"legacy-bytes"
    assert record.launches == []
    assert record.startup_stops == 1


def test_failed_launch_rolls_back_and_preserves_preexisting_shortcuts(tmp_path, monkeypatch):
    installed = tmp_path / "Local" / "langstudyguard" / "langstudyguard.exe"
    external = tmp_path / "first.exe"
    _write(external, b"first")
    real_register = install.register_startup
    _bind(monkeypatch, tmp_path, frozen=True, executable=external, installed=installed)
    monkeypatch.setattr(install, "register_startup", real_register)
    monkeypatch.setattr(install.config, "ui", lambda _vi, en: en)
    folder = _startup_folder(tmp_path)
    legacy = folder / "Dutch Guard.lnk"
    unrelated = folder / "unrelated.lnk"
    legacy.write_bytes(b"legacy-bytes")
    unrelated.write_bytes(b"unrelated-bytes")

    def allow_run(args, check=False, creationflags=0):
        return install.subprocess.CompletedProcess(args, 0)

    def fail_popen(_args, cwd=None, close_fds=False):
        raise OSError("start blocked")

    monkeypatch.setattr(install.subprocess, "run", allow_run)
    monkeypatch.setattr(install.subprocess, "Popen", fail_popen)

    with pytest.raises(OSError, match="could not be started") as caught:
        install.prepare()

    assert isinstance(caught.value.__cause__, OSError)
    assert "start blocked" in str(caught.value.__cause__)
    assert not installed.exists()
    assert not (folder / "langstudyguard.lnk").exists()
    assert legacy.read_bytes() == b"legacy-bytes"
    assert unrelated.read_bytes() == b"unrelated-bytes"


def test_source_launch_does_not_install_or_touch_startup(tmp_path, monkeypatch):
    installed = tmp_path / "installed.exe"
    external = tmp_path / "python.exe"
    _write(installed, b"installed")
    _write(external, b"python")
    record = _bind(monkeypatch, tmp_path, frozen=False, executable=external, installed=installed)

    assert install.prepare() is True

    assert installed.read_bytes() == b"installed"
    assert record.seeds == 0
    assert record.startup == []
    assert record.launches == []
    assert record.notices == 0


def test_updater_still_replaces_installed_executable_directly(tmp_path, monkeypatch):
    destination = tmp_path / "Local" / "langstudyguard" / "langstudyguard.exe"
    downloaded = tmp_path / "download.exe"
    script_dir = tmp_path / "temp"
    script_dir.mkdir()
    downloaded.write_bytes(b"MZ-update")
    monkeypatch.setattr(updater.config, "is_frozen", lambda: True)
    monkeypatch.setattr(updater.config, "installed_exe", lambda: str(destination))
    monkeypatch.setattr(updater, "_MIN_EXE_BYTES", 1)
    monkeypatch.setattr(updater.tempfile, "gettempdir", lambda: str(script_dir))

    calls: list[list[str]] = []

    def popen(args, creationflags=0, close_fds=False):
        calls.append(list(args))
        return object()

    monkeypatch.setattr(updater.subprocess, "Popen", popen)

    def forbid_prepare():
        raise AssertionError("updater must not call install.prepare")

    monkeypatch.setattr(install, "prepare", forbid_prepare)

    updater._swap_and_restart(str(downloaded))

    script = (script_dir / "langstudyguard-update.ps1").read_text(encoding="utf-8")
    assert "Copy-Item -LiteralPath $source -Destination $destination -Force" in script
    assert "install.prepare" not in script
    assert calls
    assert calls[0][0] == "powershell"
    assert calls[0][-2] == str(downloaded)
    assert calls[0][-1] == str(destination)
    assert not destination.exists()
