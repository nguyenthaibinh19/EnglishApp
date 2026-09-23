"""Theo dõi tiến độ học: thống kê từng từ + nhật ký theo ngày.

Dữ liệu nằm ở progress.json, tách khỏi vocab.json để bạn có thể sửa tay danh
sách từ vựng mà không sợ mất lịch sử học.
"""

import json
import os
from datetime import date, datetime

import config
from text_utils import normalize


def today_key() -> str:
    return date.today().isoformat()


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
            stats = {"seen": 0, "correct": 0, "wrong": 0, "streak": 0, "last_seen": None}
            if create:
                self.data["words"][key] = stats
        return stats

    def accuracy(self, word: str) -> float:
        stats = self.word_stats(word)
        if not stats["seen"]:
            return 0.0
        return stats["correct"] / stats["seen"]

    def weight(self, word: str) -> float:
        """Trọng số khi bốc câu hỏi: từ mới và từ hay sai được ưu tiên."""
        stats = self.word_stats(word)
        if not stats["seen"]:
            return 4.0

        weight = 1.0 + 4.0 * (1.0 - self.accuracy(word))
        # Từ đã thuộc (đúng liên tiếp nhiều lần) thì giãn ra cho đỡ nhàm.
        weight /= 1.0 + 0.6 * min(stats["streak"], 5)

        last_seen = stats.get("last_seen")
        if last_seen:
            try:
                days_ago = (date.today() - datetime.fromisoformat(last_seen).date()).days
                weight *= 1.0 + min(days_ago, 14) * 0.15
            except ValueError:
                pass
        return max(weight, 0.15)

    # ---------- Ghi nhận câu trả lời ----------

    def record(self, word: str, correct: bool, autosave: bool = True):
        key = normalize(word)
        stats = self.word_stats(word, create=True)
        stats["seen"] += 1
        stats["last_seen"] = datetime.now().isoformat(timespec="seconds")
        if correct:
            stats["correct"] += 1
            stats["streak"] += 1
        else:
            stats["wrong"] += 1
            stats["streak"] = 0

        day = self.data["days"].setdefault(
            today_key(), {"asked": [], "correct": [], "wrong": [], "reading_done": False}
        )
        for bucket in ("asked", "correct" if correct else "wrong"):
            if key not in day[bucket]:
                day[bucket].append(key)
        # Trả lời đúng ở lần sau thì gỡ khỏi danh sách sai của ngày hôm đó.
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
            (key, stats["correct"] / stats["seen"] if stats["seen"] else 0.0, stats["wrong"])
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
