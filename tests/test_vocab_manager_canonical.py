"""Vocabulary Manager / Reading word-bank — canonical ``meaning`` regressions."""

from __future__ import annotations

import inspect
import tkinter as tk
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from progress import Progress
from quiz_app import VocabQuizApp
from reading_app import ReadingApp
from text_utils import entry_word, strip_tags
from vocab_store import VocabStore
from vocabulary_model import entry_meaning, normalize_entry_dict


CANONICAL = {
    "id": "11111111-1111-4111-8111-111111111111",
    "word": "the train",
    "meaning": "xe lửa",
    "alternatives": ["train"],
}


def _canonical_store(tmp_path) -> VocabStore:
    path = tmp_path / "vocab.json"
    path.write_text("[]", encoding="utf-8")
    store = VocabStore(str(path))
    assert store.add("the train", "xe lửa", alternatives=["train"])
    entry = store.get(0)
    assert "meaning" in entry
    assert "vi" not in entry
    return store


def test_canonical_entry_has_meaning_not_vi():
    row = normalize_entry_dict(
        {"word": "huis", "meaning": "house"}, assign_id=True
    )
    assert row["meaning"] == "house"
    assert "vi" not in row
    assert entry_meaning(row) == "house"
    with pytest.raises(KeyError):
        _ = row["vi"]


def test_quiz_manager_source_avoids_direct_vi_field_reads():
    src = inspect.getsource(VocabQuizApp._refresh_word_list)
    assert "entry['vi']" not in src
    assert 'entry["vi"]' not in src
    assert "entry_meaning" in src

    delete_src = inspect.getsource(VocabQuizApp._delete_word)
    assert "entry['vi']" not in delete_src
    assert 'entry["vi"]' not in delete_src
    assert "entry_meaning" in delete_src


def test_refresh_word_list_with_canonical_only_entries(tmp_path, monkeypatch):
    store = _canonical_store(tmp_path)
    app = object.__new__(VocabQuizApp)
    app.store = store
    app.search_var = SimpleNamespace(get=lambda: "")
    app._filtered_indices = []
    inserted = []
    app.word_listbox = MagicMock()
    app.word_listbox.insert.side_effect = lambda *_a: inserted.append(_a[1])
    app.manager_count_label = MagicMock()

    # Must not raise KeyError: 'vi'
    app._refresh_word_list()

    assert len(app._filtered_indices) == 1
    assert inserted
    assert "the train" in inserted[0]
    assert "xe lửa" in inserted[0]


def test_refresh_word_list_search_matches_canonical_meaning(tmp_path):
    store = _canonical_store(tmp_path)
    app = object.__new__(VocabQuizApp)
    app.store = store
    app.search_var = SimpleNamespace(get=lambda: "xe lửa")
    app._filtered_indices = []
    app.word_listbox = MagicMock()
    app.manager_count_label = MagicMock()

    app._refresh_word_list()
    assert app._filtered_indices == [0]

    app.search_var = SimpleNamespace(get=lambda: "missing-gloss")
    app._refresh_word_list()
    assert app._filtered_indices == []


def test_select_loads_canonical_meaning_into_form(tmp_path):
    store = _canonical_store(tmp_path)
    app = object.__new__(VocabQuizApp)
    app.store = store
    app._filtered_indices = [0]
    app.word_listbox = MagicMock()
    app.word_listbox.curselection.return_value = (0,)
    vars_map = {
        "word": MagicMock(),
        "vi": MagicMock(),
        "alt": MagicMock(),
        "example": MagicMock(),
    }
    app.form_vars = vars_map

    app._on_word_selected()
    vars_map["word"].set.assert_called_with("the train")
    vars_map["vi"].set.assert_called_with("xe lửa")


def test_add_update_delete_preserve_uuid_and_canonical_schema(tmp_path):
    store = _canonical_store(tmp_path)
    original_id = store.get(0)["id"]

    assert store.add("the bike", "xe đạp")
    bike = store.get(1)
    assert bike["meaning"] == "xe đạp"
    assert "vi" not in bike
    assert bike["id"] != original_id

    assert store.update(0, "the train", "tàu hỏa", alternatives=["train"])
    updated = store.get(0)
    assert updated["id"] == original_id
    assert updated["meaning"] == "tàu hỏa"
    assert "vi" not in updated

    assert store.delete(1)
    assert store.count() == 1
    assert store.get(0)["id"] == original_id


def test_delete_confirm_message_uses_entry_meaning(tmp_path, monkeypatch):
    store = _canonical_store(tmp_path)
    app = object.__new__(VocabQuizApp)
    app.store = store
    app.manage_only = True
    app._filtered_indices = [0]
    app.word_listbox = MagicMock()
    app.word_listbox.curselection.return_value = (0,)
    app.form_vars = {"word": MagicMock(), "vi": MagicMock(), "alt": MagicMock(), "example": MagicMock()}
    app.form_entries = {"word": MagicMock()}
    prompts = []

    class Guard:
        def ask_yes_no(self, title, message):
            prompts.append(message)
            return True

        def show_error(self, *_a, **_k):
            raise AssertionError("unexpected error")

    app.guard = Guard()
    app._clear_form = MagicMock()
    app._refresh_word_list = MagicMock()

    app._delete_word()
    assert prompts
    assert "the train" in prompts[0]
    assert "xe lửa" in prompts[0]
    assert store.count() == 0


def test_reading_glossary_accepts_meaning_only_items():
    app = object.__new__(ReadingApp)
    app.test = {
        "translation_vi": "",
        "glossary": [
            {"word": "train", "meaning": "xe lửa"},
            {"nl": "fiets", "vi": "xe đạp"},
        ],
    }
    text = app._translation_content()
    assert "train" in text and "xe lửa" in text
    assert "fiets" in text and "xe đạp" in text


def test_reading_word_bank_restores_screenguard_on_construction_failure(monkeypatch):
    app = object.__new__(ReadingApp)
    app.window = MagicMock()
    app.store = MagicMock()
    app.progress = MagicMock()
    app._bank = None
    app._bank_suspended = False

    guard = MagicMock()
    app.guard = guard

    bank = MagicMock()
    bank.winfo_exists.return_value = True
    monkeypatch.setattr("reading_app.ui_common.open_owned_popup", lambda *a, **k: bank)

    class Boom(Exception):
        pass

    def boom_quiz(*_a, **_k):
        raise Boom("canonical KeyError stand-in")

    monkeypatch.setattr("quiz_app.VocabQuizApp", boom_quiz)

    with pytest.raises(Boom):
        app._open_word_bank()

    guard.pause_enforcement.assert_called_once()
    guard.resume_enforcement.assert_called_once_with(refocus=False)
    assert app._bank_suspended is False
    assert app._bank is None
    bank.destroy.assert_called_once()


def test_reading_word_bank_success_keeps_pause_until_destroy(monkeypatch):
    app = object.__new__(ReadingApp)
    app.window = MagicMock()
    app.store = MagicMock()
    app.progress = MagicMock()
    app._bank = None
    app._bank_suspended = False
    app.guard = MagicMock()

    bank = MagicMock()
    bank.winfo_exists.return_value = True
    destroy_handler = {}

    def bind(sequence, handler):
        destroy_handler[sequence] = handler

    bank.bind.side_effect = bind
    monkeypatch.setattr("reading_app.ui_common.open_owned_popup", lambda *a, **k: bank)
    monkeypatch.setattr("quiz_app.VocabQuizApp", lambda *a, **k: MagicMock())

    app._open_word_bank()
    assert app._bank is bank
    assert app._bank_suspended is True
    app.guard.pause_enforcement.assert_called_once()
    app.guard.resume_enforcement.assert_not_called()

    destroy_handler["<Destroy>"](SimpleNamespace(widget=bank))
    assert app._bank_suspended is False
    app.guard.resume_enforcement.assert_called_once_with(refocus=False)


def test_manager_listbox_disables_exportselection():
    src = inspect.getsource(VocabQuizApp._build_manager_view)
    assert "exportselection=False" in src


def test_listbox_keeps_selection_when_entry_takes_primary():
    """Real Tk: Ctrl+A-style Entry selection must not clear Listbox curselection."""
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Tk/Tcl unavailable in this Python env: {exc}")
    root.withdraw()
    try:
        broken = tk.Listbox(root)  # default exportselection=True
        fixed = tk.Listbox(root, exportselection=False)
        entry = tk.Entry(root)
        for box in (broken, fixed):
            box.insert(0, "the train — xe lửa")
            box.selection_set(0)
        assert broken.curselection() == (0,)
        assert fixed.curselection() == (0,)

        entry.focus_set()
        entry.insert(0, "old meaning")
        entry.select_range(0, tk.END)
        root.update_idletasks()
        root.update()

        assert broken.curselection() == ()
        assert fixed.curselection() == (0,)
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass


def test_enter_updates_when_selected_adds_when_not(tmp_path):
    store = _canonical_store(tmp_path)
    app = object.__new__(VocabQuizApp)
    app.store = store
    app._filtered_indices = [0]
    app.word_listbox = MagicMock()
    calls = {"update": 0, "add": 0}
    app._update_word = lambda: calls.__setitem__("update", calls["update"] + 1)
    app._add_word = lambda: calls.__setitem__("add", calls["add"] + 1)

    app.word_listbox.curselection.return_value = (0,)
    app._on_manager_enter()
    assert calls == {"update": 1, "add": 0}

    app.word_listbox.curselection.return_value = ()
    app._on_manager_enter()
    assert calls == {"update": 1, "add": 1}


def test_update_meaning_keeps_uuid_after_selection(tmp_path):
    store = _canonical_store(tmp_path)
    original_id = store.get(0)["id"]
    app = object.__new__(VocabQuizApp)
    app.store = store
    app.manage_only = True
    app._filtered_indices = [0]
    app.word_listbox = MagicMock()
    app.word_listbox.curselection.return_value = (0,)
    app.form_vars = {
        "word": SimpleNamespace(get=lambda: "the train"),
        "vi": SimpleNamespace(get=lambda: "tàu hỏa"),
        "alt": SimpleNamespace(get=lambda: "train"),
        "example": SimpleNamespace(get=lambda: ""),
    }
    app.form_entries = {"word": MagicMock()}
    app.guard = MagicMock()
    refreshed = []

    def refresh(select_index=None):
        refreshed.append(select_index)

    app._refresh_word_list = refresh
    app._update_word()

    updated = store.get(0)
    assert updated["id"] == original_id
    assert updated["meaning"] == "tàu hỏa"
    assert "vi" not in updated
    assert refreshed == [0]


def test_selected_index_follows_filtered_list_positions(tmp_path):
    """After filter, selection position maps through ``_filtered_indices`` only."""
    path = tmp_path / "vocab.json"
    path.write_text("[]", encoding="utf-8")
    store = VocabStore(str(path))
    assert store.add("alpha", "một")
    assert store.add("beta", "hai")
    assert store.add("gamma", "ba")

    app = object.__new__(VocabQuizApp)
    app.store = store
    app.search_var = SimpleNamespace(get=lambda: "a")  # alpha + beta + gamma all contain "a"
    app._filtered_indices = []
    app.word_listbox = MagicMock()
    app.manager_count_label = MagicMock()
    app._refresh_word_list()
    assert app._filtered_indices == [0, 1, 2]

    # Narrower filter: only gamma remains visible at list position 0 → store index 2.
    app.search_var = SimpleNamespace(get=lambda: "gamma")
    app._refresh_word_list()
    assert app._filtered_indices == [2]
    app.word_listbox.curselection.return_value = (0,)
    assert app._selected_store_index() == 2
    assert store.get(2)["word"] == "gamma"
