"""Logic của phần luyện từ vựng, tách hẳn khỏi giao diện Tkinter.

Nhờ vậy có thể chạy thử bằng script mà không cần mở cửa sổ.
Chọn từ / trọng số ủy thác cho scheduler; ghi nhận tiến độ vẫn qua Progress.
"""

import os
import random
from dataclasses import dataclass, field

import config
from attempt_history import AttemptHistory, LearningAttempt, utc_now_iso
from scheduler import VocabScheduler
from text_utils import display_word, entry_word, match_answer, strip_tags


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
    """Chấm câu trả lời và điều khiển phiên; lịch hỏi từ nằm ở VocabScheduler."""

    def __init__(
        self,
        store,
        progress,
        target: int = None,
        rng: random.Random = None,
        attempt_history: AttemptHistory = None,
        language_code: str = None,
        apply_due_filter: bool = True,
    ):
        self.store = store
        self.progress = progress
        self.target = target if target is not None else config.QUIZ_TARGET_CORRECT
        self.rng = rng or random.Random()
        self.apply_due_filter = apply_due_filter
        self.scheduler = VocabScheduler(
            progress, rng=self.rng, apply_due_filter=apply_due_filter
        )
        self.language_code = language_code
        if attempt_history is not None:
            self.attempt_history = attempt_history
        else:
            # Cùng thư mục với progress.json → tests dùng tmp_path không đụng AppData.
            attempts_file = os.path.join(
                os.path.dirname(progress.filename) or ".", "attempts.jsonl"
            )
            self.attempt_history = AttemptHistory(
                attempts_file, language_code=language_code
            )

        self.correct_count = 0
        self.answered = 0
        self.streak = 0
        self.best_streak = 0
        self.current_index = None
        self.hint_used = False

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
        index = self.scheduler.pick_next_index(self.store, self.answered)
        self.current_index = index
        self.hint_used = False
        if index is None:
            return None
        return self.store.get(index)

    def use_hint(self) -> str:
        """Gợi ý chữ cái đầu. Từ được gợi ý sẽ bị hỏi lại trong phiên."""
        entry = self.current_entry
        if entry is None:
            return ""
        self.hint_used = True
        word = strip_tags(entry_word(entry))
        masked = "".join("_" if c.isalpha() else c for c in word[1:])
        return f"{word[0]}{masked}  ({len(word)} ký tự)"

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
        word = entry_word(entry)
        self.progress.record(word, correct=mastered)
        self._record_attempt(
            user_answer=user_answer,
            entry=entry,
            word=word,
            correct=mastered,
            verdict=verdict,
        )

        if is_correct:
            self.correct_count += 1
            self.streak += 1
            self.best_streak = max(self.best_streak, self.streak)
        else:
            self.streak = 0
            word = strip_tags(entry_word(entry))
            if word not in self.session_wrong:
                self.session_wrong.append(word)

        # Sai hẳn, sai chính tả hoặc đã xem gợi ý đều được xếp lịch hỏi lại.
        if not mastered and self.current_index is not None:
            delay = config.WRONG_REQUEUE_AFTER if not is_correct else config.WRONG_REQUEUE_AFTER * 2
            self.scheduler.schedule_requeue(self.current_index, self.answered, delay)

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

    def _record_attempt(
        self,
        user_answer: str,
        entry: dict,
        word: str,
        correct: bool,
        verdict: str,
    ) -> None:
        """Ghi lịch sử với cùng quyết định đúng/sai như Progress.record."""
        code = self.language_code or config.active_code()
        attempt = LearningAttempt(
            timestamp=utc_now_iso(),
            language_code=code,
            word=word,
            user_answer=user_answer,
            expected_answer=display_word(entry) or word,
            correct=correct,
            verdict=verdict,
            hint_used=bool(self.hint_used),
            prompt=str(entry.get("vi") or ""),
        )
        self.attempt_history.record(attempt)

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
