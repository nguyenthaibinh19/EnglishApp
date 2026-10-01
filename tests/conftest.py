"""Shared pytest fixtures. Production code is unchanged."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def vocab_file(tmp_path: Path) -> Path:
    path = tmp_path / "vocab.json"
    path.write_text(
        json.dumps(
            [
                {"word": "de fiets", "vi": "xe đạp"},
                {"word": "het huis", "vi": "ngôi nhà"},
                {"word": "de trein", "vi": "tàu hỏa"},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def empty_progress_file(tmp_path: Path) -> Path:
    return tmp_path / "progress.json"
