"""Phase 17C — Listening cache / fallback / source."""

from __future__ import annotations

import json
from pathlib import Path

import config
from listening import ListeningItem
from listening_source import (
    NoListeningAvailable,
    build_listening_item,
    listening_cache_key,
    load_listening_cache,
    save_listening_cache,
    select_listening_targets,
)
from progress import Progress
from vocab_store import VocabStore


def _store(tmp_path: Path) -> VocabStore:
    path = tmp_path / "vocab.json"
    path.write_text(
        json.dumps(
            [
            {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "word": "train", "meaning": "tàu"},
            {"id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", "word": "station", "meaning": "ga"},
        ]
        ),
        encoding="utf-8",
    )
    return VocabStore(str(path))


def _progress(tmp_path: Path) -> Progress:
    path = tmp_path / "progress.json"
    path.write_text(
        json.dumps({"version": 3, "identity": "studyguard-progress", "words": {}, "days": {}}),
        encoding="utf-8",
    )
    return Progress(str(path))


def test_cache_key_distinguishes_dimensions():
    entries = [{"id": "a", "word": "train", "meaning": "tàu"}]
    k1 = listening_cache_key(
        language_code="en", native_code="vi", level="A2", entries=entries, day="2026-01-01"
    )
    k2 = listening_cache_key(
        language_code="nl", native_code="vi", level="A2", entries=entries, day="2026-01-01"
    )
    k3 = listening_cache_key(
        language_code="en", native_code="en", level="A2", entries=entries, day="2026-01-01"
    )
    k4 = listening_cache_key(
        language_code="en", native_code="vi", level="B1", entries=entries, day="2026-01-01"
    )
    k5 = listening_cache_key(
        language_code="en",
        native_code="vi",
        level="A2",
        entries=[{"id": "b", "word": "bus", "meaning": "xe"}],
        day="2026-01-01",
    )
    k6 = listening_cache_key(
        language_code="en", native_code="vi", level="A2", entries=entries, day="2026-01-02"
    )
    assert len({k1, k2, k3, k4, k5, k6}) == 6


def test_valid_cache_avoids_ai(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(config, "cache_dir", lambda code=None: str(tmp_path / "cache"))
    store = _store(tmp_path)
    progress = _progress(tmp_path)
    entries = select_listening_targets(store, progress, language_code="en", count=2)
    item = ListeningItem(
        text="The train leaves at nine.",
        question="What time does the train leave?",
        answer="at nine",
        alternatives=("nine",),
        meaning="Meaning.",
    )
    save_listening_cache(
        item, language_code="en", native_code="vi", level="A2", entries=entries
    )
    calls = []

    def boom(*_a, **_k):
        calls.append(1)
        raise AssertionError("AI must not run")

    monkeypatch.setattr("listening_source.ai_teacher.is_configured", lambda: True)
    result = build_listening_item(
        store,
        progress,
        language_code="en",
        native_code="vi",
        level="A2",
        generate=boom,
    )
    assert result.answer == "at nine"
    assert calls == []


def test_invalid_cache_ignored(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(config, "cache_dir", lambda code=None: str(tmp_path / "cache"))
    store = _store(tmp_path)
    progress = _progress(tmp_path)
    entries = select_listening_targets(store, progress, language_code="en", count=2)
    path = Path(config.cache_dir("en")) / listening_cache_key(
        language_code="en", native_code="vi", level="A2", entries=entries
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"text": "broken"}', encoding="utf-8")
    assert load_listening_cache(
        language_code="en", native_code="vi", level="A2", entries=entries
    ) is None


def test_ai_failure_uses_bundled_sample(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(config, "cache_dir", lambda code=None: str(tmp_path / "cache"))
    store = _store(tmp_path)
    progress = _progress(tmp_path)

    def boom(*_a, **_k):
        raise RuntimeError("network")

    monkeypatch.setattr("listening_source.ai_teacher.is_configured", lambda: True)
    item = build_listening_item(
        store,
        progress,
        language_code="en",
        native_code="vi",
        level="A2",
        generate=boom,
        force_new=True,
    )
    assert item.answer == "at nine"
    assert item.question  # study language


def test_ai_unconfigured_uses_sample_without_ai(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(config, "cache_dir", lambda code=None: str(tmp_path / "cache"))
    store = _store(tmp_path)
    progress = _progress(tmp_path)
    monkeypatch.setattr("listening_source.ai_teacher.is_configured", lambda: False)
    item = build_listening_item(
        store,
        progress,
        language_code="nl",
        native_code="vi",
        level="A2",
        force_new=True,
    )
    assert "trein" in item.text.casefold() or "vertrekt" in item.text.casefold()


def test_fallback_language_isolation(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(config, "cache_dir", lambda code=None: str(tmp_path / "cache"))
    store = _store(tmp_path)
    progress = _progress(tmp_path)
    monkeypatch.setattr("listening_source.ai_teacher.is_configured", lambda: False)
    nl = build_listening_item(
        store, progress, language_code="nl", native_code="vi", force_new=True
    )
    en = build_listening_item(
        store, progress, language_code="en", native_code="vi", force_new=True
    )
    assert nl.question != en.question
