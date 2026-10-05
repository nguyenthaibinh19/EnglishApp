"""Window lifecycle helpers — unit-tested without fragile Tk runtime deps."""

from __future__ import annotations

import inspect

import ui_common
from main import StudyMasterApp


class _FakeWindow:
    """Minimal stand-in for reset_window unit checks."""

    def __init__(self):
        self._attrs = {"-fullscreen": True, "-topmost": True}
        self._state = "zoomed"
        self._children = []
        self._protocol = None
        self.resizable_args = None
        self.destroyed = False
        self.exists = True

    def attributes(self, *args):
        if len(args) == 1:
            return self._attrs.get(args[0])
        self._attrs[args[0]] = args[1]

    def state(self, value=None):
        if value is None:
            return self._state
        self._state = value

    def winfo_children(self):
        return list(self._children)

    def unbind(self, _sequence):
        return None

    def protocol(self, _name, handler):
        self._protocol = handler

    def resizable(self, width, height):
        self.resizable_args = (width, height)

    def winfo_exists(self):
        return self.exists

    def destroy(self):
        self.destroyed = True
        self.exists = False


def test_reset_window_restores_normal_state():
    window = _FakeWindow()
    ui_common.reset_window(window)
    assert window._attrs["-fullscreen"] is False
    assert window._attrs["-topmost"] is False
    assert window._state == "normal"
    assert window.resizable_args == (True, True)


def test_launch_toplevel_app_destroys_partial_on_builder_failure(monkeypatch):
    created = []

    class FakeToplevel(_FakeWindow):
        def __init__(self, parent):
            super().__init__()
            self.parent = parent
            created.append(self)

    monkeypatch.setattr(ui_common.tk, "Toplevel", FakeToplevel)

    parent = _FakeWindow()
    seen = {}

    def boom(window):
        seen["window"] = window
        raise RuntimeError("simulated ReadingApp constructor failure")

    def on_error(error):
        seen["error"] = error

    result = ui_common.launch_toplevel_app(parent, boom, on_error=on_error)
    assert result is None
    assert isinstance(seen["error"], RuntimeError)
    assert seen["window"].destroyed is True
    assert seen["window"].exists is False
    assert len(created) == 1


def test_launch_toplevel_app_keeps_window_on_success(monkeypatch):
    class FakeToplevel(_FakeWindow):
        def __init__(self, parent):
            super().__init__()
            self.parent = parent

    monkeypatch.setattr(ui_common.tk, "Toplevel", FakeToplevel)
    parent = _FakeWindow()
    seen = {}

    def build(window):
        seen["ok"] = True

    child = ui_common.launch_toplevel_app(parent, build)
    assert child is not None
    assert seen["ok"] is True
    assert child.destroyed is False
    assert child.exists is True


def test_study_master_activity_emergency_uses_quit_all():
    """Regression: open_reading/listening used missing self.exit_all → blank Toplevel."""
    reading_src = inspect.getsource(StudyMasterApp.open_reading_section)
    listening_open_src = inspect.getsource(StudyMasterApp.open_listening_section)
    listening_src = inspect.getsource(
        StudyMasterApp._open_listening_with_resolved_provider
    )
    assert "self.exit_all" not in reading_src
    assert "self.exit_all" not in listening_open_src
    assert "self.exit_all" not in listening_src
    assert "on_emergency=self.quit_all" in reading_src
    assert "on_emergency=self.quit_all" in listening_src
    assert "launch_toplevel_app" in reading_src
    assert "launch_toplevel_app" in listening_src
    assert "required=False" in reading_src
    assert "required=False" in listening_src
    assert "_begin_listening_provider_resolve" in listening_open_src
