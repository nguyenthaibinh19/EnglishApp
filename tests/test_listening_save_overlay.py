"""Phase 17C hardening — truthful Listening word-save overlay results."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import config
from listening_app import ListeningApp
from vocab_store import VocabStore


def _store(tmp_path: Path) -> VocabStore:
    path = tmp_path / "vocab.json"
    path.write_text(
        json.dumps(
            [
                {
                    "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                    "word": "train",
                    "meaning": "tau",
                }
            ]
        ),
        encoding="utf-8",
    )
    return VocabStore(str(path))


def test_listening_save_word_success_and_duplicate(tmp_path: Path):
    store = _store(tmp_path)
    app = object.__new__(ListeningApp)
    app.vocab_store = store
    app.language_code = "en"

    assert app._save_word("station", "ga") == "saved"
    assert store.index_of("station") is not None
    assert app._save_word("train", "tau hoa") == "duplicate"
    assert app._save_word("", "x") == "failed"
    assert app._save_word("bus", "") == "failed"


def test_overlay_maps_save_statuses_to_messages(monkeypatch):
    """Exercise save_word closure messaging without a real Tk display."""
    from word_lookup_overlay import open_word_action_overlay

    labels = []
    commands = {}

    class FakeLabel:
        def __init__(self, *a, **k):
            self.kwargs = k

        def pack(self, **k):
            return self

        def config(self, **kwargs):
            if "text" in kwargs and self.kwargs.get("wraplength"):
                labels.append(kwargs["text"])

    class FakeButton:
        def __init__(self, *a, **k):
            self.text = k.get("text") or (a[1] if len(a) > 1 else "")
            self.command = k.get("command")
            if self.command is not None:
                commands[str(self.text)] = self.command

        def pack(self, **k):
            return self

    class FakeVar:
        def get(self):
            return "a meaning"

    parent = MagicMock()
    parent.winfo_rootx.return_value = 0
    parent.winfo_rooty.return_value = 0
    parent.winfo_width.return_value = 800
    parent.winfo_height.return_value = 600
    parent.update_idletasks = MagicMock()

    frame = MagicMock()
    frame.pack = MagicMock(return_value=frame)
    frame.bind = MagicMock()
    frame.place = MagicMock()
    frame.lift = MagicMock()
    frame.focus_set = MagicMock()
    frame.winfo_exists = lambda: True
    frame.winfo_reqwidth = lambda: 220
    frame.winfo_reqheight = lambda: 120
    frame.grab_release = MagicMock()
    frame.destroy = MagicMock()

    monkeypatch.setattr("word_lookup_overlay.tk.Frame", lambda *a, **k: frame)
    monkeypatch.setattr("word_lookup_overlay.ttk.Frame", lambda *a, **k: MagicMock(pack=MagicMock()))
    monkeypatch.setattr("word_lookup_overlay.ttk.Label", FakeLabel)
    monkeypatch.setattr("word_lookup_overlay.ttk.Entry", lambda *a, **k: MagicMock(pack=MagicMock()))
    monkeypatch.setattr("word_lookup_overlay.ttk.Button", FakeButton)
    monkeypatch.setattr("word_lookup_overlay.tk.StringVar", FakeVar)

    statuses = iter(["saved", "duplicate", "failed"])
    open_word_action_overlay(
        parent,
        word="train",
        x_root=10,
        y_root=10,
        language_code="en",
        on_save=lambda _w, _m: next(statuses),
    )
    save_key = next(
        key
        for key in commands
        if "Save" in key or "Lưu" in key
    )
    save = commands[save_key]
    save()
    save()
    save()
    joined = " | ".join(labels)
    assert "Saved." in joined or config.ui("Đã lưu.", "Saved.") in labels
    assert (
        "already in your list" in joined
        or "đã có" in joined
        or any("already" in m for m in labels)
    )
    assert (
        "Could not save" in joined
        or "Không lưu được" in joined
        or any("Could not save" in m or "Không lưu được" in m for m in labels)
    )
