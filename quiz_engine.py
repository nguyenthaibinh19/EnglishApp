"""Logic của phần luyện từ vựng, tách hẳn khỏi giao diện Tkinter.

Nhờ vậy có thể chạy thử bằng script mà không cần mở cửa sổ.
"""

import random
from dataclasses import dataclass, field

import config
from text_utils import display_word, match_answer, strip_tags


@dataclass
class AnswerResult:
    verdict: str              # "exact" | "near" | "wrong"
    is_correct: bool          # "exact" và "near" đều tính là đúng
    entry: dict = field(default_factory=dict)
    correct_display: str = ""
    matched_form: str = ""
    correct_count: int = 0
    remaining: int = 0
    streak: int = 0
    finished: bool = False


class QuizEngine:
    """Chọn câu hỏi theo trọng số SRS và chấm câu trả lời."""

    def __init__(self, store, progress, target: int = None, rng: random.Random = None):
        self.store = store
        self.progress = progress
        self.target = target if target is not None else config.QUIZ_TARGET_CORRECT
        self.rng = rng or random.Random()

        self.correct_count = 0
        self.answered = 0
        self.streak = 0
        self.best_streak = 0
        self.current_index = None
        self.hint_used = False

        self._last_index = None
        self._requeue = []        # [(hỏi lại sau câu thứ n, index)]
        self.session_wrong = []   # các từ đã sai trong phiên này

    # ---------- Trạng thái ----------

    @property
    def finished(self) -> bool:
        return self.correct_count >= self.target

    @property
    def remaining(self) -> int:
        return max(self.target - self.correct_count, 0)

    @property
    def current_entry(self):
        return self.store.get(self.current_index) if self.current_index is not None else None

    # ---------- Chọn câu hỏi ----------

    def pick_next(self):
        """Chọn từ tiếp theo, trả về entry (hoặc None nếu kho từ rỗng)."""
        total = self.store.count()
        if total == 0:
            self.current_index = None
            return None

        index = self._pop_due_requeue(total)
        if index is None:
            index = self._weighted_pick(total)

        self._last_index = index
        self.current_index = index
        self.hint_used = False
        return self.store.get(index)

    def use_hint(self) -> str:
        """Gợi ý chữ cái đầu. Từ được gợi ý sẽ bị hỏi lại trong phiên."""
        entry = self.current_entry
        if entry is None:
            return ""
        self.hint_used = True
        word = strip_tags(entry["nl"])
        masked = "".join("_" if c.isalpha() else c for c in word[1:])
        return f"{word[0]}{masked}  ({len(word)} ký tự)"

    def _pop_due_requeue(self, total: int):
        """Lấy từ đã sai và đã tới lượt hỏi lại."""
        for position, (due_at, index) in enumerate(self._requeue):
            if due_at > self.answered or index >= total:
                continue
            if index == self._last_index and total > 1:
                continue
            self._requeue.pop(position)
            return index
        return None

    def _weighted_pick(self, total: int) -> int:
        candidates = [i for i in range(total) if i != self._last_index] or [self._last_index]
        weights = [self.progress.weight(self.store.get(i)["nl"]) for i in candidates]
        return self.rng.choices(candidates, weights=weights, k=1)[0]

    # ---------- Chấm câu trả lời ----------

    def submit(self, user_answer: str) -> AnswerResult:
        entry = self.current_entry
        if entry is None:
            return AnswerResult(verdict="wrong", is_correct=False)

        verdict, matched = match_answer(user_answer, entry, config.TYPO_TOLERANCE)
        is_correct = verdict in ("exact", "near")

        self.answered += 1
        # Lỗi chính tả hoặc có xem gợi ý vẫn tính là đúng trong phiên,
        # nhưng không được ghi nhận là đã thuộc từ.
        mastered = verdict == "exact" and not self.hint_used
        self.progress.record(entry["nl"], correct=mastered)

        if is_correct:
            self.correct_count += 1
            self.streak += 1
            self.best_streak = max(self.best_streak, self.streak)
        else:
            self.streak = 0
            word = strip_tags(entry["nl"])
            if word not in self.session_wrong:
                self.session_wrong.append(word)

        # Sai hẳn, sai chính tả hoặc đã xem gợi ý đều được xếp lịch hỏi lại.
        if not mastered:
            delay = config.WRONG_REQUEUE_AFTER if not is_correct else config.WRONG_REQUEUE_AFTER * 2
            self._requeue.append((self.answered + delay, self.current_index))

        return AnswerResult(
            verdict=verdict,
            is_correct=is_correct,
            entry=entry,
            correct_display=display_word(entry),
            matched_form=matched,
            correct_count=self.correct_count,
            remaining=self.remaining,
            streak=self.streak,
            finished=self.finished,
        )

    # ---------- Thông tin hiển thị ----------

    def session_stats(self) -> dict:
        accuracy = self.correct_count / self.answered if self.answered else 0.0
        return {
            "answered": self.answered,
            "correct": self.correct_count,
            "target": self.target,
            "accuracy": accuracy,
            "streak": self.streak,
            "best_streak": self.best_streak,
            "wrong_words": list(self.session_wrong),
        }
