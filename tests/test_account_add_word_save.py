"""Signed-in Add Word must persist examples without AttributeError."""

from __future__ import annotations

import json
from pathlib import Path

from account_local_store import AccountLocalStore
from study_data import AccountVocabStore
from vocab_store import VocabStore
from vocabulary_app import commit_vocab_edit


def _account_store(tmp_path: Path):
    account = AccountLocalStore(3, data_root=str(tmp_path))
    store = AccountVocabStore(account, "nl")
    return account, store


def test_account_add_empty_example(tmp_path):
    account, store = _account_store(tmp_path)
    assert store.add("fiets", "bike", alternatives=[], example="") is True
    entry = store.get(0)
    assert entry["word"] == "fiets"
    assert "examples" not in entry or entry.get("examples") in (None, [], "")
    assert account.status().pending_vocab == 1
    account.close()


def test_account_add_with_example_and_reopen(tmp_path):
    account, store = _account_store(tmp_path)
    assert store.add("huis", "house", example="een groot huis") is True
    vid = store.get(0)["id"]
    account.close()

    account2 = AccountLocalStore(3, data_root=str(tmp_path))
    reopened = AccountVocabStore(account2, "nl")
    entry = reopened.get(0)
    assert entry["id"] == vid
    texts = [item["text"] for item in entry["examples"]]
    assert texts == ["een groot huis"]
    assert account2.status().pending_vocab == 1
    account2.close()


def test_account_edit_preserves_uuid_and_extra_examples(tmp_path):
    account, store = _account_store(tmp_path)
    assert store.add(
        "boek",
        "book",
        examples=[
            {"text": "een boek", "meaning": "a book"},
            {"text": "twee boeken", "meaning": "two books"},
        ],
    )
    original = store.get(0)
    vid = original["id"]
    assert store.update(0, "boek", "book", example="het boek") is True
    edited = store.get(0)
    assert edited["id"] == vid
    assert [item["text"] for item in edited["examples"]] == ["het boek", "twee boeken"]
    assert edited["examples"][0].get("meaning") == "a book"
    assert account.status().pending_vocab == 1
    account.close()


def test_account_duplicate_rejected_without_extra_outbox(tmp_path):
    account, store = _account_store(tmp_path)
    assert store.add("trein", "train", example="") is True
    pending = account.status().pending_vocab
    live = len(store.all())
    assert store.add("TREIN", "train again", example="de trein") is False
    assert len(store.all()) == live
    assert account.status().pending_vocab == pending
    assert store.get(0)["meaning"] == "train"
    account.close()


def test_guest_add_word_still_works(tmp_path):
    path = tmp_path / "vocab.json"
    path.write_text("[]", encoding="utf-8")
    store = VocabStore(str(path))
    assert store.add("fiets", "bike", example="") is True
    assert store.add("huis", "house", example="een huis") is True
    assert store.add("FIETS", "bicycle") is False
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert [item["word"] for item in saved] == ["fiets", "huis"]
    assert saved[1]["examples"][0]["text"] == "een huis"


def test_commit_vocab_edit_duplicate_and_persistence_failure(tmp_path):
    account, store = _account_store(tmp_path)
    ok, message = commit_vocab_edit(
        store,
        mode="add",
        word="kat",
        meaning="cat",
        extra={"example": ""},
    )
    assert ok is True
    assert message == ""
    ok, message = commit_vocab_edit(
        store,
        mode="add",
        word="kat",
        meaning="cat",
        extra={"example": "de kat"},
    )
    assert ok is False
    assert message

    class _Boom:
        def add(self, *args, **kwargs):
            raise RuntimeError("disk")

        def update(self, *args, **kwargs):
            raise RuntimeError("disk")

    ok, message = commit_vocab_edit(
        _Boom(),
        mode="add",
        word="hond",
        meaning="dog",
        extra={"example": ""},
    )
    assert ok is False
    assert "save" in message.lower() or "lưu" in message.lower()
    assert store.get(0)["word"] == "kat"
    assert account.status().pending_vocab == 1
    account.close()
