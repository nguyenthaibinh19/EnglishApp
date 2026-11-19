"""Signed-in vs guest study data gateway (Phase 18C.2).

When an account session is active, Vocabulary / Quiz / Progress / Mistake Book
read and write ``AccountLocalStore``. Guest mode keeps ``languages/{code}/`` files.

Never dual-writes guest files while signed in. Never auto-imports guest data.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date
from typing import Any, List, Optional

import config
from attempt_history import AttemptHistory, LearningAttempt
from progress import Progress, _default_word_stats, today_key
from srs import apply_review_to_stats, parse_utc, to_utc_iso, utc_now
from text_utils import entry_word, normalize, strip_tags
from vocab_identity import entry_id, is_vocab_id, new_vocab_id
from vocabulary_model import (
    entry_meaning,
    normalize_alternatives,
    normalize_entry_dict,
    normalize_examples,
    normalize_forms,
    normalize_part_of_speech,
    normalize_pronunciation,
)


def is_signed_in() -> bool:
    return bool(config.account_token()) and config.account_user_id() > 0


def active_account_store(data_root: Optional[str] = None):
    """Return the open sync-engine store, or open a short-lived AccountLocalStore."""
    if not is_signed_in():
        return None
    from account_sync_engine import active_engine
    from account_local_store import AccountLocalStore

    engine = active_engine()
    if engine is not None and engine.store.user_id == config.account_user_id():
        if data_root is None or engine.store.data_root == data_root:
            return engine.store
    return AccountLocalStore(config.account_user_id(), data_root=data_root)


def _notify():
    try:
        from account_sync_engine import notify_local_change

        notify_local_change()
    except Exception:
        pass


@dataclass
class StudyBundle:
    language_code: str
    signed_in: bool
    vocab: Any
    progress: Any
    attempts: Any
    account_store: Any = None


def open_study_data(
    language_code: str = None, *, data_root: Optional[str] = None
) -> StudyBundle:
    code = str(language_code or config.active_code()).strip().lower()
    if is_signed_in():
        store = active_account_store(data_root=data_root)
        if store is not None:
            vocab = AccountVocabStore(store, code)
            progress = AccountProgress(store, code)
            attempts = AccountAttemptHistory(store, code)
            return StudyBundle(
                language_code=code,
                signed_in=True,
                vocab=vocab,
                progress=progress,
                attempts=attempts,
                account_store=store,
            )
    config.ensure_language_data()
    from vocab_store import VocabStore

    return StudyBundle(
        language_code=code,
        signed_in=False,
        vocab=VocabStore(config.vocab_path(code)),
        progress=Progress(config.progress_path(code)),
        attempts=AttemptHistory(config.attempts_path(code), language_code=code),
        account_store=None,
    )


class AccountVocabStore:
    """VocabStore-compatible view over the signed-in account database."""

    def __init__(self, account_store, language_code: str):
        self._account = account_store
        self.language_code = language_code.strip().lower()
        self.filename = account_store.path
        self.vocab: List[dict] = []
        self.load()

    def load(self):
        rows = self._account.list_vocabulary(self.language_code)
        cleaned = []
        for item in rows:
            row = normalize_entry_dict(item, assign_id=False)
            if row:
                cleaned.append(row)
        self.vocab = cleaned

    def save(self):
        # Mutations persist immediately via upsert/delete.
        return None

    def all(self) -> list:
        return self.vocab

    def count(self) -> int:
        return len(self.vocab)

    def get(self, index: int):
        if 0 <= index < len(self.vocab):
            return self.vocab[index]
        return None

    def get_by_id(self, vocab_id: str):
        target = str(vocab_id or "").strip()
        if not target:
            return None
        for entry in self.vocab:
            if entry_id(entry) == target:
                return entry
        return None

    def index_of_id(self, vocab_id: str):
        target = str(vocab_id or "").strip()
        if not target:
            return None
        for i, entry in enumerate(self.vocab):
            if entry_id(entry) == target:
                return i
        return None

    def index_of(self, word: str):
        target = normalize(word)
        for i, entry in enumerate(self.vocab):
            if normalize(entry["word"]) == target:
                return i
        return None

    def find_duplicates(self) -> list:
        seen = {}
        dups = []
        for entry in self.vocab:
            key = normalize(entry["word"])
            if key in seen:
                dups.append(entry["word"])
            seen[key] = True
        return dups

    def add(self, word: str, meaning: str = None, **extra) -> bool:
        if meaning is None and "vi" in extra:
            meaning = extra.pop("vi")
        word = (word or "").strip()
        meaning = (meaning or "").strip()
        if not word or not meaning:
            return False
        if self.index_of(word) is not None:
            return False
        payload = {"id": new_vocab_id(), "word": word, "meaning": meaning}
        payload.update(self._optional_from_extra(extra))
        entry = normalize_entry_dict(payload, assign_id=True)
        if entry is None:
            return False
        self._account.upsert_vocabulary(
            language_code=self.language_code,
            vocab_id=entry["id"],
            payload=entry,
        )
        _notify()
        self.load()
        return True

    def update(self, index: int, word: str, meaning: str = None, **extra) -> bool:
        if not (0 <= index < len(self.vocab)):
            return False
        if meaning is None and "vi" in extra:
            meaning = extra.pop("vi")
        word = (word or "").strip()
        meaning = (meaning or "").strip()
        if not word or not meaning:
            return False
        existing_id = entry_id(self.vocab[index])
        payload = dict(self.vocab[index])
        payload["word"] = word
        payload["meaning"] = meaning
        if existing_id:
            payload["id"] = existing_id
        for key in ("vi", "alt", "type", "nl", "en", "example"):
            payload.pop(key, None)
        optionals = self._optional_from_extra(extra, clearing=True, existing=self.vocab[index])
        for field_name in (
            "alternatives",
            "examples",
            "note",
            "part_of_speech",
            "pronunciation",
            "forms",
        ):
            if field_name in optionals:
                if optionals[field_name]:
                    payload[field_name] = optionals[field_name]
                else:
                    payload.pop(field_name, None)
        entry = normalize_entry_dict(payload, assign_id=True)
        if entry is None:
            return False
        if existing_id:
            entry["id"] = existing_id
        self._account.upsert_vocabulary(
            language_code=self.language_code,
            vocab_id=entry["id"],
            payload=entry,
        )
        _notify()
        self.load()
        return True

    def delete(self, index: int) -> bool:
        if not (0 <= index < len(self.vocab)):
            return False
        vid = entry_id(self.vocab[index])
        if not vid:
            return False
        self._account.delete_vocabulary(language_code=self.language_code, vocab_id=vid)
        _notify()
        self.load()
        return True

    def entries_for_keys(self, keys) -> list:
        wanted_ids = set()
        wanted_words = set()
        for key in keys or ():
            text = str(key)
            if is_vocab_id(text):
                wanted_ids.add(text)
            else:
                wanted_words.add(normalize(text))
        return [
            e
            for e in self.vocab
            if (entry_id(e) and entry_id(e) in wanted_ids)
            or normalize(e["word"]) in wanted_words
        ]

    def display_list(self) -> list:
        return [f"{strip_tags(e['word'])} — {entry_meaning(e)}" for e in self.vocab]

    def _optional_from_extra(self, extra: dict, clearing: bool = False, existing: dict = None) -> dict:
        from vocab_store import VocabStore

        return VocabStore._optional_from_extra(self, extra, clearing=clearing, existing=existing)


class AccountProgress:
    """Progress-compatible view using provisional stats + account day buckets."""

    def __init__(self, account_store, language_code: str):
        self._account = account_store
        self.language_code = language_code.strip().lower()
        self.filename = account_store.path
        self.data = {"version": 3, "identity": "account", "words": {}, "days": {}}
        self.reload()

    def reload(self):
        words = {}
        for entry in self._account.list_vocabulary(self.language_code):
            vid = entry_id(entry)
            if not vid:
                continue
            prov = self._account.provisional_progress(self.language_code, vid)
            conf = self._account.confirmed_progress(self.language_code, vid)
            src = prov or conf
            if src is None:
                words[vid] = _default_word_stats()
            else:
                words[vid] = {
                    "seen": int(src.get("seen") or 0),
                    "correct": int(src.get("correct") or 0),
                    "wrong": int(src.get("wrong") or 0),
                    "streak": int(src.get("streak") or 0),
                    "interval_days": int(src.get("interval_days") or 0),
                    "due_at": str(src.get("due_at") or "") or None,
                    "last_seen": str(src.get("updated_at") or src.get("due_at") or "") or None,
                }
        # Also include confirmed-only rows (no vocab entity yet should not happen).
        self.data["words"] = words
        self.data["days"] = self._account.account_day_buckets(self.language_code)

    def save(self):
        return None

    def word_stats(self, word: str = None, create: bool = False, *, vocab_id: str = None) -> dict:
        vid = str(vocab_id or "").strip()
        legacy = normalize(word) if word else ""
        if is_vocab_id(vid):
            stats = self.data["words"].get(vid)
            if stats is not None:
                return stats
            if create:
                stats = _default_word_stats()
                self.data["words"][vid] = stats
                return stats
            return _default_word_stats()
        if legacy and legacy in self.data["words"]:
            return self.data["words"][legacy]
        return _default_word_stats()

    def accuracy(self, word: str = None, *, vocab_id: str = None) -> float:
        from scheduler import accuracy_from_stats

        return accuracy_from_stats(self.word_stats(word, vocab_id=vocab_id))

    def weight(self, word: str = None, *, vocab_id: str = None) -> float:
        from scheduler import compute_weight

        return compute_weight(self.word_stats(word, vocab_id=vocab_id))

    def record(
        self,
        word: str,
        correct: bool,
        autosave: bool = True,
        reviewed_at=None,
        *,
        vocab_id: str = None,
    ):
        # QuizEngine also writes AttemptHistory; AccountAttemptHistory.record is
        # the authoritative signed-in write. This method updates the in-memory
        # projection so the scheduler sees provisional state immediately.
        vid = str(vocab_id or "").strip()
        if not is_vocab_id(vid):
            return
        stats = self.word_stats(word, create=True, vocab_id=vid)
        from srs import ensure_utc

        reviewed_at = ensure_utc(reviewed_at or utc_now())
        stats["seen"] = int(stats.get("seen") or 0) + 1
        stats["last_seen"] = to_utc_iso(reviewed_at)
        if correct:
            stats["correct"] = int(stats.get("correct") or 0) + 1
            stats["streak"] = int(stats.get("streak") or 0) + 1
        else:
            stats["wrong"] = int(stats.get("wrong") or 0) + 1
            stats["streak"] = 0
        apply_review_to_stats(stats, mastered=correct, reviewed_at=reviewed_at)
        day = self.data["days"].setdefault(
            today_key(), {"asked": [], "correct": [], "wrong": [], "reading_done": False}
        )
        for bucket in ("asked", "correct" if correct else "wrong"):
            if vid not in day[bucket]:
                day[bucket].append(vid)
        if correct and vid in day["wrong"]:
            day["wrong"].remove(vid)

    def mark_reading_done(self, score: int = None, total: int = None):
        self._account.mark_reading_done(self.language_code, score=score, total=total)
        _notify()
        self.reload()

    def today(self) -> dict:
        return self.data["days"].get(
            today_key(), {"asked": [], "correct": [], "wrong": [], "reading_done": False}
        )

    def words_studied_today(self) -> list:
        return list(self.today().get("asked", []))

    def weakest_words(self, limit: int = 10) -> list:
        scored = [
            (key, stats["correct"] / stats["seen"] if stats.get("seen") else 0.0, stats["wrong"])
            for key, stats in self.data["words"].items()
            if stats.get("seen")
        ]
        scored.sort(key=lambda item: (item[1], -item[2]))
        return [key for key, _, _ in scored[:limit]]

    def summary(self) -> dict:
        day = self.today()
        return {
            "asked_today": len(day.get("asked", [])),
            "correct_today": len(day.get("correct", [])),
            "wrong_today": len(day.get("wrong", [])),
            "reading_done": bool(day.get("reading_done")),
            "known_words": sum(
                1 for s in self.data["words"].values() if s.get("streak", 0) >= 3
            ),
            "total_tracked": len(self.data["words"]),
            "account_day_streak": self.account_day_streak(),
        }

    def account_day_streak(self, *, today: Optional[date] = None) -> int:
        """Consecutive UTC calendar days with activity (matches account_day_buckets).

        Anchor defaults to today's UTC date so local midnight does not shift the
        streak relative to UTC-bucketed attempts. Reading-done alone does not
        extend the streak (asks come from attempts).
        """
        if today is None:
            anchor = utc_now().date()
        else:
            anchor = today
        days = self.data.get("days") or {}
        streak = 0
        cursor = anchor
        while True:
            key = cursor.isoformat()
            bucket = days.get(key) or {}
            asked = bucket.get("asked") or []
            if not asked:
                break
            streak += 1
            cursor = date.fromordinal(cursor.toordinal() - 1)
        return streak


class AccountAttemptHistory:
    """AttemptHistory-compatible sink/source over AccountLocalStore."""

    def __init__(self, account_store, language_code: str):
        self._account = account_store
        self.language_code = language_code.strip().lower()
        self.filename = account_store.path

    def record(self, attempt: LearningAttempt) -> None:
        vid = str(attempt.vocab_id or "").strip()
        if not is_vocab_id(vid):
            return
        verdict = str(attempt.verdict or ("exact" if attempt.correct else "wrong"))
        self._account.record_learning_attempt(
            language_code=self.language_code or attempt.language_code,
            vocab_id=vid,
            verdict=verdict,
            hint_used=bool(attempt.hint_used),
            word_snapshot=str(attempt.word or ""),
            user_answer=str(attempt.user_answer or ""),
            expected_answer=str(attempt.expected_answer or "") or str(attempt.word or ""),
            prompt=str(attempt.prompt or ""),
            occurred_at=str(attempt.timestamp or to_utc_iso(utc_now())),
        )
        _notify()

    def load_attempts(self) -> List[LearningAttempt]:
        rows = self._account.list_attempts(self.language_code)
        out = []
        for row in rows:
            out.append(
                LearningAttempt(
                    timestamp=str(row.get("occurred_at") or row.get("received_at") or ""),
                    language_code=str(row.get("language_code") or self.language_code),
                    word=str(row.get("word_snapshot") or ""),
                    user_answer=str(row.get("user_answer") or ""),
                    expected_answer=str(row.get("expected_answer") or ""),
                    correct=bool(int(row.get("mastered") or 0)),
                    verdict=str(row.get("verdict") or "wrong"),
                    hint_used=bool(int(row.get("hint_used") or 0)),
                    prompt=str(row.get("prompt") or ""),
                    vocab_id=str(row.get("vocab_id") or ""),
                )
            )
        return out

    def iter_attempts(self):
        yield from self.load_attempts()

    def recent_attempts(self, limit: int = 50) -> List[LearningAttempt]:
        if limit <= 0:
            return []
        return self.load_attempts()[-limit:]
