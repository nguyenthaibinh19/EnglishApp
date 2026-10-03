"""Lịch chọn từ vựng: due filter (SRS v2) + trọng số + requeue trong phiên.

Tách:
  long-term  → srs.is_due / due candidate filtering
  session    → weighted pick among candidates + in-session requeue

Không import Tkinter. Không ghi progress khi chỉ tính trọng số / chọn từ.
"""

from __future__ import annotations

import random
from datetime import date, datetime
from typing import Any, List, Optional

from srs import due_priority_key, ensure_utc, is_due, utc_now
from text_utils import entry_word
from vocab_identity import entry_id


def accuracy_from_stats(stats: dict) -> float:
    """Tỉ lệ đúng từ bản thống kê đã load (không đụng đĩa)."""
    seen = int(stats.get("seen") or 0)
    if not seen:
        return 0.0
    return float(stats.get("correct") or 0) / seen


def compute_weight(stats: dict, today: Optional[date] = None) -> float:
    """Trọng số chọn trong phiên: từ mới / hay sai cao hơn; streak cao thì thấp hơn.

    Công thức giữ nguyên từ Progress.weight (trước khi tách module).
    """
    from srs import parse_utc

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
        parsed = parse_utc(last_seen)
        if parsed is not None:
            days_ago = (today - parsed.date()).days
            weight *= 1.0 + min(days_ago, 14) * 0.15
    return max(weight, 0.15)


def due_candidate_indices(
    store: Any,
    progress: Any,
    *,
    now: Optional[datetime] = None,
    apply_due_filter: bool = True,
) -> List[int]:
    """Indices eligible for selection.

    When ``apply_due_filter`` is True (normal quiz):
      1. due / unseen / legacy-unscheduled words
      2. if none, all words sorted by soonest due (never empty if store non-empty)

    When False (Practice Mistakes): every index in the (already filtered) store.
    """
    total = store.count() if store is not None else 0
    if total <= 0:
        return []
    if not apply_due_filter:
        return list(range(total))

    now = ensure_utc(now or utc_now())
    due: List[int] = []
    not_due: List[tuple] = []
    for index in range(total):
        entry = store.get(index)
        stats = _stats_for_entry(progress, entry) if entry else None
        if is_due(stats, now):
            due.append(index)
        else:
            not_due.append((due_priority_key(stats, now), index))
    if due:
        return due
    # Fallback: nearest upcoming first, but keep all so the quiz can still run.
    not_due.sort(key=lambda item: item[0])
    return [index for _, index in not_due] or list(range(total))


class VocabScheduler:
    """Chọn index: session requeue → due candidates → weighted pick.

    Session state (requeue, last index) sống ở đây. Progress chỉ được đọc khi
    tính trọng số / due; gọi pick_next không ghi file.
    """

    def __init__(
        self,
        progress: Any,
        rng: Optional[random.Random] = None,
        apply_due_filter: bool = True,
        now_provider=None,
    ):
        self.progress = progress
        self.rng = rng or random.Random()
        self.apply_due_filter = apply_due_filter
        self.now_provider = now_provider or utc_now
        self._last_index: Optional[int] = None
        self._requeue: list[tuple[int, int]] = []  # (due_after_answered, index)

    def weight_for(self, word: str = None, *, vocab_id: str = None, entry: dict = None) -> float:
        """Đọc thống kê từ progress (create=False) rồi tính trọng số — không save."""
        if entry is not None:
            stats = _stats_for_entry(self.progress, entry)
        else:
            stats = self.progress.word_stats(word, create=False, vocab_id=vocab_id)
        return compute_weight(stats)

    def pick_next_index(
        self,
        store: Any,
        answered: int,
        now: Optional[datetime] = None,
    ) -> Optional[int]:
        """Chọn index tiếp theo. None nếu kho rỗng. Không mutate progress."""
        total = store.count()
        if total == 0:
            self._last_index = None
            return None

        index = self._pop_due_requeue(total, answered)
        if index is None:
            candidates = due_candidate_indices(
                store,
                self.progress,
                now=now or self.now_provider(),
                apply_due_filter=self.apply_due_filter,
            )
            index = self._weighted_pick(store, candidates)

        self._last_index = index
        return index

    def pick_next(
        self,
        store: Any,
        answered: int,
        now: Optional[datetime] = None,
    ) -> Optional[dict]:
        """Chọn entry tiếp theo. Trả về None nếu kho rỗng. Không mutate progress."""
        index = self.pick_next_index(store, answered, now=now)
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

    def _weighted_pick(self, store: Any, candidates: List[int]) -> int:
        if not candidates:
            return 0
        filtered = [i for i in candidates if i != self._last_index] or list(candidates)
        weights = [
            self.weight_for(entry=store.get(i))
            for i in filtered
        ]
        return self.rng.choices(filtered, weights=weights, k=1)[0]


def _stats_for_entry(progress: Any, entry: Optional[dict]) -> dict:
    if not entry:
        return {}
    vid = entry_id(entry)
    word = entry_word(entry)
    return progress.word_stats(word, create=False, vocab_id=vid or None)
