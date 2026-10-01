"""Theo dõi tiến độ học: thống kê từng từ + nhật ký theo ngày.

Dữ liệu nằm ở progress.json, tách khỏi vocab.json để bạn có thể sửa tay danh
sách từ vựng mà không sợ mất lịch sử học.

Phase 8: mỗi từ có thể thêm due_at / interval_days (SRS v2). Thiếu = tương thích.
"""

import json
import os
from datetime import date, datetime

import config
from text_utils import normalize


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
        default = {"version": 2, "words": {}, "days": {}}
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
        tmp = self.filename + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.filename)
        except OSError as e:
            print("Không ghi được progress.json:", e)

    # ---------- Thống kê từng từ ----------

    def word_stats(self, word: str, create: bool = False) -> dict:
        """Thống kê của một từ. Chỉ ghi vào file khi create=True."""
        key = normalize(word)
        stats = self.data["words"].get(key)
        if stats is None:
            stats = _default_word_stats()
            if create:
                self.data["words"][key] = stats
        return stats

    def accuracy(self, word: str) -> float:
        from scheduler import accuracy_from_stats

        return accuracy_from_stats(self.word_stats(word))

    def weight(self, word: str) -> float:
        """Tương thích ngược: ủy thác cho scheduler.compute_weight.

        Không đổi công thức. Không tạo bản ghi mới khi chỉ đọc trọng số.
        """
        from scheduler import compute_weight

        return compute_weight(self.word_stats(word))

    # ---------- Ghi nhận câu trả lời ----------

    def record(
        self,
        word: str,
        correct: bool,
        autosave: bool = True,
        reviewed_at: datetime = None,
    ):
        """Ghi counters/streak và SRS due_at trong một lần.

        ``correct`` = mastered (exact + không gợi ý), cùng nghĩa AttemptHistory.
        """
        from srs import apply_review_to_stats, ensure_utc, to_utc_iso, utc_now

        reviewed_at = ensure_utc(reviewed_at or utc_now())
        key = normalize(word)
        stats = self.word_stats(word, create=True)
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
        """Các từ đã được kiểm tra hôm nay (dạng đã chuẩn hóa)."""
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
