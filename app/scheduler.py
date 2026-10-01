"""Lịch chọn từ vựng: trọng số và thứ tự hỏi tiếp theo.

Tách khỏi progress.py để progress chỉ lo lưu trạng thái, còn quyết định
“hỏi từ nào tiếp” nằm ở đây. Thuật toán hiện tại (weighted / requeue) giữ
nguyên hành vi — chưa phải SM-2 hay FSRS.

Không import Tkinter. Không ghi progress khi chỉ tính trọng số / chọn từ.
"""

from __future__ import annotations

import random
from datetime import date, datetime
from typing import Any, Optional

from text_utils import entry_word


def accuracy_from_stats(stats: dict) -> float:
    """Tỉ lệ đúng từ bản thống kê đã load (không đụng đĩa)."""
    seen = int(stats.get("seen") or 0)
    if not seen:
        return 0.0
    return float(stats.get("correct") or 0) / seen


def compute_weight(stats: dict, today: Optional[date] = None) -> float:
    """Trọng số SRS hiện tại: từ mới / hay sai cao hơn; streak cao thì thấp hơn.

    Công thức giữ nguyên từ Progress.weight (trước khi tách module).
    """
    if today is None:
        today = date.today()

    seen = int(stats.get("seen") or 0)
    if not seen:
        return 4.0

    weight = 1.0 + 4.0 * (1.0 - accuracy_from_stats(stats))
    # Từ đã thuộc (đúng liên tiếp nhiều lần) thì giãn ra cho đỡ nhàm.
    streak = int(stats.get("streak") or 0)
    weight /= 1.0 + 0.6 * min(streak, 5)

    last_seen = stats.get("last_seen")
    if last_seen:
        try:
            days_ago = (today - datetime.fromisoformat(str(last_seen)).date()).days
            weight *= 1.0 + min(days_ago, 14) * 0.15
        except ValueError:
            pass
    return max(weight, 0.15)


class VocabScheduler:
    """Chọn index từ trong kho theo trọng số progress + hàng chờ hỏi lại trong phiên.

    Session state (requeue, last index) sống ở đây. Progress chỉ được đọc khi
    tính trọng số; gọi pick_next không ghi file.
    """

    def __init__(self, progress: Any, rng: Optional[random.Random] = None):
        self.progress = progress
        self.rng = rng or random.Random()
        self._last_index: Optional[int] = None
        self._requeue: list[tuple[int, int]] = []  # (due_after_answered, index)

    def weight_for(self, word: str) -> float:
        """Đọc thống kê từ progress (create=False) rồi tính trọng số — không save."""
        stats = self.progress.word_stats(word, create=False)
        return compute_weight(stats)

    def pick_next_index(self, store: Any, answered: int) -> Optional[int]:
        """Chọn index tiếp theo. None nếu kho rỗng. Không mutate progress."""
        total = store.count()
        if total == 0:
            self._last_index = None
            return None

        index = self._pop_due_requeue(total, answered)
        if index is None:
            index = self._weighted_pick(store, total)

        self._last_index = index
        return index

    def pick_next(self, store: Any, answered: int) -> Optional[dict]:
        """Chọn entry tiếp theo. Trả về None nếu kho rỗng. Không mutate progress."""
        index = self.pick_next_index(store, answered)
        if index is None:
            return None
        return store.get(index)

    def remember_pick(self, index: Optional[int]) -> None:
        """Đồng bộ last_index khi caller đã chọn index bên ngoài scheduler."""
        self._last_index = index

    def schedule_requeue(self, index: int, answered: int, delay: int) -> None:
        """Xếp từ vào hàng chờ hỏi lại sau `answered + delay` câu."""
        self._requeue.append((answered + delay, index))

    def _pop_due_requeue(self, total: int, answered: int) -> Optional[int]:
        for position, (due_at, index) in enumerate(self._requeue):
            if due_at > answered or index >= total:
                continue
            if index == self._last_index and total > 1:
                continue
            self._requeue.pop(position)
            return index
        return None

    def _weighted_pick(self, store: Any, total: int) -> int:
        candidates = [i for i in range(total) if i != self._last_index] or (
            [self._last_index] if self._last_index is not None else [0]
        )
        weights = [
            self.weight_for(entry_word(store.get(i)))
            for i in candidates
        ]
        return self.rng.choices(candidates, weights=weights, k=1)[0]
