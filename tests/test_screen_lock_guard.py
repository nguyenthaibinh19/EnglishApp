"""Screen lock cannot engage without an acknowledged emergency credential.

Uses fake windows and a temporary data root. It does not open a real screen lock.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import config
import emergency_credential
import install
import ui_common
from home_app import FreeHome
from listening_app import ListeningApp
from main import StudyMasterApp
from quiz_app import VocabQuizApp
from reading_app import ReadingApp


class IdentityTestProtection:
    name = "injected"

    def protect(self, plaintext: bytes) -> bytes:
        return b"test-v1:" + plaintext

    def unprotect(self, protected: bytes) -> bytes:
        prefix = b"test-v1:"
        if not protected.startswith(prefix):
            raise emergency_credential.CredentialUnreadable("unreadable")
        return protected[len(prefix) :]


class FakeWindow:
    def __init__(self):
        self.attrs = {}
        self.bindings = {}
        self.protocol_handler = None
        self.destroyed = False
        self.exists = True
        self.geometry_value = None
        self.children = []
        self.state_value = "normal"
        self.resizable_args = None

    def attributes(self, *args):
        if len(args) == 1:
            return self.attrs.get(args[0])
        self.attrs[args[0]] = args[1]

    def protocol(self, _name=None, handler=None):
        if handler is not None:
            self.protocol_handler = handler
        return self.protocol_handler

    def bind(self, sequence, handler=None, add=None):
        self.bindings[sequence] = handler

    def bind_all(self, sequence, handler=None, add=None):
        self.bindings[sequence] = handler

    def unbind(self, sequence):
        self.bindings.pop(sequence, None)

    def geometry(self, value=None):
        if value is not None:
            self.geometry_value = value
        return self.geometry_value

    def destroy(self):
        self.destroyed = True
        self.exists = False

    def winfo_exists(self):
        return self.exists

    def winfo_children(self):
        return list(self.children)

    def state(self, value=None):
        if value is None:
            return self.state_value
        self.state_value = value

    def resizable(self, width, height):
        self.resizable_args = (width, height)

    def after(self, *_args, **_kwargs):
        return "after"

    def after_cancel(self, *_args, **_kwargs):
        return None

    def close(self):
        self.protocol_handler()


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("LG_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    monkeypatch.setattr(config, "LOCK_SCREEN", True)
    emergency_credential.set_protection_for_tests(IdentityTestProtection())
    yield
    emergency_credential.set_protection_for_tests(None)


def _enroll() -> str:
    secret = emergency_credential.begin_or_resume()
    assert emergency_credential.acknowledge_current(secret) is True
    return secret


def test_cancel_enrollment_then_start_study_stays_unlocked():
    secret = emergency_credential.begin_or_resume()
    emergency_credential.cancel_enrollment()
    assert emergency_credential.lock_allowed() is False
    assert secret

    home = FreeHome.__new__(FreeHome)
    home.root = FakeWindow()
    home.refresh = lambda: None
    home._invalidate_owned_callbacks = lambda: None
    home._stop_sync_status_polling = lambda: None
    home._close_bank = lambda: None
    home._close_mistake_book = lambda: None
    started = {}

    class Started:
        def __init__(self, root, on_finished=None):
            self.completed = False
            self.guard = ui_common.ScreenGuard(
                root,
                on_close_attempt=lambda: setattr(self, "completed", True),
                on_unlocked_close=root.destroy,
            )
            started["guard"] = self.guard

    home._study_master_class = lambda: Started
    home._start_study()

    guard = started["guard"]
    assert guard.enabled is False
    assert guard.allows_unlocked_leave() is True
    assert home.root.attrs.get("-fullscreen") is not True
    home.root.close()
    assert home.root.destroyed is True


def test_explicit_enabled_true_cannot_bypass_a_missing_credential():
    window = FakeWindow()
    blocked = {"hit": False}
    guard = ui_common.ScreenGuard(
        window,
        enabled=True,
        on_close_attempt=lambda: blocked.__setitem__("hit", True),
        on_unlocked_close=window.destroy,
    )
    assert guard.enabled is False
    assert window.attrs.get("-fullscreen") is not True
    window.close()
    assert blocked["hit"] is False
    assert window.destroyed is True


def test_unacknowledged_and_corrupt_credentials_do_not_lock(tmp_path):
    emergency_credential.begin_or_resume()
    window = FakeWindow()
    guard = ui_common.ScreenGuard(window, enabled=True, on_unlocked_close=window.destroy)
    assert guard.enabled is False
    path = Path(emergency_credential.credential_path())
    path.write_text("{broken", encoding="utf-8")
    again = FakeWindow()
    corrupt = ui_common.ScreenGuard(again, enabled=True)
    assert corrupt.enabled is False
    assert emergency_credential.status() == "unreadable"


def test_child_windows_close_without_completing_when_unlocked():
    for cls in (VocabQuizApp, ReadingApp, ListeningApp):
        window = FakeWindow()
        app = cls.__new__(cls)
        app.window = window
        app.completed = False
        app.required = True
        app.load_failed = False
        app._closed = False
        app.session = type("Session", (), {"completed": False, "unavailable": False})()
        app.on_skip = lambda: (_ for _ in ()).throw(AssertionError("skip"))
        app.on_failed = lambda: (_ for _ in ()).throw(AssertionError("failed"))
        app.guard = ui_common.ScreenGuard(
            window,
            enabled=True,
            on_close_attempt=app._on_close_attempt,
            on_unlocked_close=app._leave_unlocked,
        )
        assert app.guard.enabled is False
        window.close()
        assert window.destroyed is True
        assert app.completed is False
        assert app.session.completed is False


def test_study_close_returns_home_without_marking_complete():
    window = FakeWindow()
    app = StudyMasterApp.__new__(StudyMasterApp)
    app._force_exit = False
    app._marked_complete = False
    app.progress = type("Progress", (), {"save": lambda self: None})()
    app.vocab_window = None
    app.reading_window = None
    app.listening_window = None
    app.root = window
    returned = []
    app.on_finished = lambda: returned.append("home")
    app.guard = ui_common.ScreenGuard(
        window,
        enabled=True,
        on_close_attempt=app._on_close_root,
        on_unlocked_close=app._leave_unlocked,
    )
    window.close()
    assert returned == ["home"]
    assert app._force_exit is False
    assert app._marked_complete is False
    assert window.attrs.get("-fullscreen") is not True


def test_acknowledged_credential_allows_requested_lock_and_keeps_close_gate():
    _enroll()
    window = FakeWindow()
    blocked = {"hit": False}
    guard = ui_common.ScreenGuard(
        window,
        enabled=True,
        on_close_attempt=lambda: blocked.__setitem__("hit", True),
    )
    assert guard.enabled is True
    assert guard.locks_the_user() is True
    assert window.attrs["-fullscreen"] is True
    assert window.attrs["-topmost"] is True
    window.close()
    assert blocked["hit"] is True
    assert window.destroyed is False


def test_emergency_exit_accepts_the_local_code_offline(monkeypatch):
    secret = _enroll()
    window = FakeWindow()
    guard = ui_common.ScreenGuard(window, enabled=True, on_close_attempt=lambda: None)
    monkeypatch.setattr(ui_common, "prompt_password", lambda *_args, **_kwargs: secret)
    assert guard.confirm_emergency_exit() is True
    assert guard.enabled is True


def test_wrong_emergency_code_does_not_dismiss_an_active_lock(monkeypatch):
    _enroll()
    window = FakeWindow()
    guard = ui_common.ScreenGuard(window, enabled=True, on_close_attempt=lambda: None)
    monkeypatch.setattr(ui_common, "prompt_password", lambda *_args, **_kwargs: "not-the-code")
    monkeypatch.setattr(ui_common.messagebox, "showerror", lambda *_args, **_kwargs: None)
    assert guard.confirm_emergency_exit() is False
    assert guard.enabled is True
    assert guard.locks_the_user() is True
    assert window.attrs["-fullscreen"] is True
    assert window.destroyed is False


def test_lost_credential_releases_an_active_guard_without_completion():
    _enroll()
    window = FakeWindow()
    completed = {"hit": False}
    guard = ui_common.ScreenGuard(
        window,
        enabled=True,
        on_close_attempt=lambda: completed.__setitem__("hit", True),
        on_unlocked_close=window.destroy,
    )
    assert guard.enabled is True
    Path(emergency_credential.credential_path()).write_text("{broken", encoding="utf-8")
    guard.force_focus()
    assert guard.enabled is False
    assert window.attrs["-fullscreen"] is False
    window.close()
    assert completed["hit"] is False
    assert window.destroyed is True


def test_existing_startup_shortcut_stays_and_upgrade_does_not_lock(tmp_path, monkeypatch):
    installed = tmp_path / "Local" / "langstudyguard" / "langstudyguard.exe"
    installed.parent.mkdir(parents=True)
    installed.write_bytes(b"installed")
    monkeypatch.setattr(install.config, "is_frozen", lambda: True)
    monkeypatch.setattr(install.config, "installed_exe", lambda: str(installed))
    monkeypatch.setattr(
        install.config,
        "environment_identity",
        lambda: __import__("app_environment").EnvironmentIdentity(
            build_channel="production",
            runtime_environment="production",
            version="test",
            commit_sha="test",
            data_folder="langstudyguard",
            install_folder="langstudyguard",
            exe_basename="langstudyguard.exe",
            startup_link="langstudyguard.lnk",
            network_writes_allowed=True,
        ),
    )
    monkeypatch.setattr(install, "is_release_candidate_smoke", lambda: False)
    link = (
        tmp_path
        / "Roaming"
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
        / "langstudyguard.lnk"
    )
    link.parent.mkdir(parents=True)
    link.write_bytes(b"existing-shortcut")
    assert install.register_startup_after_enrollment() is False
    assert link.read_bytes() == b"existing-shortcut"
    window = FakeWindow()
    guard = ui_common.ScreenGuard(window, enabled=True)
    assert guard.enabled is False
    secret = _enroll()
    assert install.register_startup_after_enrollment() is False
    assert link.read_bytes() == b"existing-shortcut"
    assert secret
    enrolled = ui_common.ScreenGuard(FakeWindow(), enabled=True)
    assert enrolled.enabled is True


def test_native_windows_dpapi_round_trip_without_screen_lock(tmp_path, monkeypatch):
    if os.name != "nt":
        pytest.skip("Windows DPAPI is required for this round trip")
    emergency_credential.set_protection_for_tests(None)
    monkeypatch.setenv("LG_DATA_DIR", str(tmp_path / "dpapi-synthetic"))
    secret = emergency_credential.begin_or_resume()
    stored = Path(emergency_credential.credential_path()).read_bytes()
    assert (secret.encode("utf-8") in stored) is False
    assert emergency_credential.acknowledge_current(secret) is True
    assert emergency_credential.validate_offline(secret) is True
    assert emergency_credential.lock_allowed() is True
    window = FakeWindow()
    guard = ui_common.ScreenGuard(window, enabled=False)
    assert guard.enabled is False
    assert window.attrs.get("-fullscreen") is not True
