"""Theo dõi tiến độ học: thống kê từng từ + nhật ký theo ngày.

Dữ liệu nằm ở progress.json, tách khỏi vocab.json để bạn có thể sửa tay danh
sách từ vựng mà không sợ mất lịch sử học.

Phase 8: mỗi từ có thể thêm due_at / interval_days (SRS v2). Thiếu = tương thích.
Phase 13: khóa chính của ``words`` là vocab_id (UUID). Legacy normalized-word
keys vẫn đọc được cho đến khi migration / compatibility lookup.
"""

import json
import os
from datetime import date, datetime

import config
from text_utils import normalize
from vocab_identity import IDENTITY_MARKER, PROGRESS_IDENTITY_VERSION, is_vocab_id


def today_key() -> str:
    return date.today().isoformat()


def _default_word_stats() -> dict:
    return {
        "seen": 0,
        "correct": 0,
        "wrong": 0,
        "streak": 0,
        "last_seen": None,
    }


class Progress:
    def __init__(self, filename: str = None):
        if filename is None:
            config.ensure_language_data()
            filename = config.progress_path()
        self.filename = filename
        self.data = self._load()

    # ---------- Đọc / ghi ----------

    def _load(self) -> dict:
        default = {
            "version": PROGRESS_IDENTITY_VERSION,
            "identity": IDENTITY_MARKER,
            "words": {},
            "days": {},
        }
        if not os.path.exists(self.filename):
            return default
        try:
            with open(self.filename, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return default

        if not isinstance(data, dict):
            return default
        data.setdefault("version", 2)
        data.setdefault("words", {})
        data.setdefault("days", {})
        return data

    def save(self):
        # Once we persist under the identity model, stamp the marker.
        if self.data.get("identity") != IDENTITY_MARKER:
            self.data["identity"] = IDENTITY_MARKER
        if int(self.data.get("version") or 0) < PROGRESS_IDENTITY_VERSION:
            self.data["version"] = PROGRESS_IDENTITY_VERSION
        tmp = self.filename + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.filename)
        except OSError as e:
            print("Không ghi được progress.json:", e)

    # ---------- Thống kê từng từ ----------

    def word_stats(
        self,
        word: str = None,
        create: bool = False,
        *,
        vocab_id: str = None,
    ) -> dict:
        """Thống kê theo vocab_id (ưu tiên) hoặc legacy normalized word."""
        vid = str(vocab_id or "").strip()
        legacy = normalize(word) if word else ""

        if is_vocab_id(vid):
            stats = self.data["words"].get(vid)
            if stats is not None:
                if legacy:
                    self._remember_legacy(legacy, vid)
                return stats
            # Read fallback: pre-migration / in-memory legacy keys.
            if legacy and legacy in self.data["words"]:
                stats = self.data["words"][legacy]
                if create:
                    # Promote legacy → stable id on first write path.
                    self.data["words"][vid] = stats
                    del self.data["words"][legacy]
                    self._remember_legacy(legacy, vid)
                return stats
            mapped = (self.data.get("legacy_index") or {}).get(legacy)
            if is_vocab_id(mapped) and mapped in self.data["words"]:
                return self.data["words"][mapped]
            if create:
                stats = _default_word_stats()
                self.data["words"][vid] = stats
                if legacy:
                    self._remember_legacy(legacy, vid)
                return stats
            return _default_word_stats()

        if not legacy:
            return _default_word_stats()
        if legacy in self.data["words"]:
            stats = self.data["words"][legacy]
        else:
            mapped = (self.data.get("legacy_index") or {}).get(legacy)
            if is_vocab_id(mapped) and mapped in self.data["words"]:
                return self.data["words"][mapped]
            stats = None
        if stats is None:
            stats = _default_word_stats()
            if create:
                self.data["words"][legacy] = stats
        return stats

    def _remember_legacy(self, normalized_word: str, vocab_id: str) -> None:
        if not normalized_word or not is_vocab_id(vocab_id):
            return
        index = self.data.setdefault("legacy_index", {})
        if index.get(normalized_word) != vocab_id:
            index[normalized_word] = vocab_id

    def accuracy(self, word: str = None, *, vocab_id: str = None) -> float:
        from scheduler import accuracy_from_stats

        return accuracy_from_stats(self.word_stats(word, vocab_id=vocab_id))

    def weight(self, word: str = None, *, vocab_id: str = None) -> float:
        """Tương thích ngược: ủy thác cho scheduler.compute_weight.

        Không đổi công thức. Không tạo bản ghi mới khi chỉ đọc trọng số.
        """
        from scheduler import compute_weight

        return compute_weight(self.word_stats(word, vocab_id=vocab_id))

    # ---------- Ghi nhận câu trả lời ----------

    def record(
        self,
        word: str,
        correct: bool,
        autosave: bool = True,
        reviewed_at: datetime = None,
        *,
        vocab_id: str = None,
    ):
        """Ghi counters/streak và SRS due_at trong một lần.

        ``correct`` = mastered (exact + không gợi ý), cùng nghĩa AttemptHistory.
        Prefer ``vocab_id`` as the persistent key when provided.
        """
        from srs import apply_review_to_stats, ensure_utc, to_utc_iso, utc_now

        reviewed_at = ensure_utc(reviewed_at or utc_now())
        vid = str(vocab_id or "").strip()
        legacy = normalize(word) if word else ""
        stats = self.word_stats(word, create=True, vocab_id=vocab_id)
        # Authoritative day/progress key: vocab_id when provided.
        if is_vocab_id(vid):
            key = vid
        elif legacy:
            key = legacy
        else:
            return
        stats["seen"] += 1
        stats["last_seen"] = to_utc_iso(reviewed_at)
        if correct:
            stats["correct"] += 1
            stats["streak"] += 1
        else:
            stats["wrong"] += 1
            stats["streak"] = 0

        apply_review_to_stats(stats, mastered=correct, reviewed_at=reviewed_at)

        day = self.data["days"].setdefault(
            today_key(), {"asked": [], "correct": [], "wrong": [], "reading_done": False}
        )
        for bucket in ("asked", "correct" if correct else "wrong"):
            if key not in day[bucket]:
                day[bucket].append(key)
        if correct and key in day["wrong"]:
            day["wrong"].remove(key)

        if autosave:
            self.save()

    def mark_reading_done(self, score: int = None, total: int = None):
        day = self.data["days"].setdefault(
            today_key(), {"asked": [], "correct": [], "wrong": [], "reading_done": False}
        )
        day["reading_done"] = True
        if score is not None and total:
            day["reading_score"] = f"{score}/{total}"
        self.save()

    # ---------- Truy vấn ----------

    def today(self) -> dict:
        return self.data["days"].get(
            today_key(), {"asked": [], "correct": [], "wrong": [], "reading_done": False}
        )

    def words_studied_today(self) -> list:
        """Keys đã kiểm tra hôm nay (vocab_id sau migration, hoặc legacy word)."""
        return list(self.today().get("asked", []))

    def weakest_words(self, limit: int = 10) -> list:
        """Những từ có tỉ lệ đúng thấp nhất, dùng khi hôm nay học chưa đủ từ."""
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
        }
