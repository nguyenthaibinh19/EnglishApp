"""ScreenGuard pause vs display-release — fakes only, no real fullscreen Tk."""

from __future__ import annotations

import ui_common


class _FakeLockWindow:
    def __init__(self):
        self._attrs = {"-fullscreen": True, "-topmost": True}
        self._state = "normal"
        self.calls = []
        self._screen_guard = None

    def attributes(self, *args):
        self.calls.append(("attributes",) + args)
        if len(args) == 1:
            return self._attrs.get(args[0])
        key, value = args[0], args[1]
        self._attrs[key] = value

    def state(self, value=None):
        self.calls.append(("state", value) if value is not None else ("state",))
        if value is None:
            return self._state
        self._state = value

    def withdraw(self):
        self.calls.append(("withdraw",))

    def deiconify(self):
        self.calls.append(("deiconify",))

    def protocol(self, *_args):
        return None

    def bind(self, *_args, **_kwargs):
        return None

    def bind_all(self, *_args, **_kwargs):
        return None

    def after(self, *_args, **_kwargs):
        return "after-id"

    def after_cancel(self, *_args, **_kwargs):
        return None

    def winfo_exists(self):
        return True

    def grab_current(self):
        return None

    def focus_displayof(self):
        return self

    def focus_set(self):
        return None

    def lift(self):
        self.calls.append(("lift",))


def _guard(window=None, enabled=True):
    window = window or _FakeLockWindow()
    # Bypass __init__ fullscreen setup — build a guard on an already-configured window.
    guard = ui_common.ScreenGuard.__new__(ui_common.ScreenGuard)
    guard.window = window
    guard.enabled = enabled
    guard.on_close_attempt = None
    guard._suspend_depth = 0
    guard._combos = []
    guard._refocus_after_ids = set()
    guard._pointer_down = False
    guard._quiet_until = 0.0
    guard._was_fullscreen = False
    guard._fullscreen_released = False
    window._screen_guard = guard
    return guard, window


def test_pause_enforcement_does_not_mutate_display_state():
    guard, window = _guard()
    before_fs = window._attrs["-fullscreen"]
    before_state = window._state
    guard.pause_enforcement()
    assert window._attrs["-fullscreen"] is before_fs
    assert window._state == before_state
    assert window._attrs["-topmost"] is False
    assert ("state", "zoomed") not in window.calls
    assert ("state", "normal") not in window.calls
    assert ("withdraw",) not in window.calls
    assert ("deiconify",) not in window.calls
    assert ("attributes", "-fullscreen", False) not in window.calls
    assert ("attributes", "-fullscreen", True) not in window.calls
    guard.resume_enforcement(refocus=False)
    assert window._attrs["-topmost"] is True
    assert window._attrs["-fullscreen"] is True
    assert window._state == "normal"


def test_enforcement_paused_context_is_lightweight():
    guard, window = _guard()
    with guard.enforcement_paused():
        assert window._attrs["-fullscreen"] is True
        assert window._state == "normal"
        assert ("attributes", "-fullscreen", False) not in window.calls
    assert window._attrs["-fullscreen"] is True
    assert window._state == "normal"


def test_release_display_still_leaves_fullscreen_when_needed():
    guard, window = _guard()
    guard.release_display()
    assert window._attrs["-fullscreen"] is False
    assert window._state == "zoomed"
    assert guard._fullscreen_released is True
    guard.restore_display(refocus=False)
    assert window._attrs["-fullscreen"] is True
    assert window._attrs["-topmost"] is True


def test_suspend_default_is_lightweight():
    guard, window = _guard()
    guard.suspend()  # default leave_fullscreen=False
    assert ("attributes", "-fullscreen", False) not in window.calls
    assert window._state == "normal"
    guard.resume(refocus=False)


def test_reading_word_popup_uses_overlay_not_toplevel_suspend():
    import inspect

    from reading_app import ReadingApp

    src = inspect.getsource(ReadingApp._open_word_popup)
    assert "tk.Toplevel" not in src
    assert "release_display" not in src
    assert "leave_fullscreen=True" not in src
    assert "pause_enforcement" in src
    assert "place" in inspect.getsource(ReadingApp._place_word_overlay)


def test_activity_hand_off_uses_pause_not_display_release():
    import inspect

    from main import StudyMasterApp

    src = inspect.getsource(StudyMasterApp._suspend_for_activity)
    assert "pause_enforcement" in src
    assert "leave_fullscreen=True" not in src
    assert "release_display" not in src
