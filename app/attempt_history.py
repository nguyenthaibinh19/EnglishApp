"""Nhật ký từng lần trả lời từ vựng (append-only).

Progress giữ trạng thái tổng hợp cho scheduler.
AttemptHistory giữ lịch sử từng lần trả lời — phục vụ Mistake Book / phân tích sau này.

Định dạng: JSON Lines (một object JSON mỗi dòng) tại languages/{code}/attempts.jsonl.
Thiếu file = lịch sử rỗng; không cần migrate.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Iterator, List, Optional

import config


def utc_now_iso() -> str:
    """Timestamp ổn định, timezone-aware UTC ISO-8601."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class LearningAttempt:
    """Một lần trả lời từ vựng đã chốt đúng/sai.

    ``correct`` phải khớp quyết định gửi vào Progress.record (exact + không dùng gợi ý).
    """

    timestamp: str
    language_code: str
    word: str
    user_answer: str
    expected_answer: str
    correct: bool
    # Có sẵn trong quiz flow; hữu ích cho Mistake Book sau này.
    verdict: str = "wrong"  # "exact" | "near" | "wrong"
    hint_used: bool = False
    prompt: str = ""  # nghĩa hiển thị (thường là vi)


def _attempt_from_dict(raw: dict) -> Optional[LearningAttempt]:
    if not isinstance(raw, dict):
        return None
    try:
        return LearningAttempt(
            timestamp=str(raw.get("timestamp") or ""),
            language_code=str(raw.get("language_code") or ""),
            word=str(raw.get("word") or ""),
            user_answer=str(raw.get("user_answer") or ""),
            expected_answer=str(raw.get("expected_answer") or ""),
            correct=bool(raw.get("correct")),
            verdict=str(raw.get("verdict") or "wrong"),
            hint_used=bool(raw.get("hint_used")),
            prompt=str(raw.get("prompt") or ""),
        )
    except (TypeError, ValueError):
        return None


class AttemptHistory:
    """Store append-only; đọc lại tuần tự theo thứ tự ghi."""

    def __init__(self, filename: str = None, language_code: str = None):
        if filename is None:
            config.ensure_language_data()
            code = language_code or config.active_code()
            filename = config.attempts_path(code)
        self.filename = filename
        self.language_code = language_code

    def record(self, attempt: LearningAttempt) -> None:
        """Ghi thêm một attempt. Lỗi I/O cục bộ không làm hỏng phiên học."""
        line = json.dumps(asdict(attempt), ensure_ascii=False) + "\n"
        directory = os.path.dirname(self.filename)
        try:
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(self.filename, "a", encoding="utf-8") as f:
                f.write(line)
        except OSError as e:
            print("Không ghi được attempts.jsonl:", e)

    def iter_attempts(self) -> Iterator[LearningAttempt]:
        """Đọc tuần tự; bỏ qua dòng trống / JSON hỏng / bản ghi không hợp lệ."""
        if not os.path.exists(self.filename):
            return
        try:
            with open(self.filename, "r", encoding="utf-8") as f:
                for line in f:
                    text = line.strip()
                    if not text:
                        continue
                    try:
                        raw = json.loads(text)
                    except json.JSONDecodeError:
                        continue
                    attempt = _attempt_from_dict(raw)
                    if attempt is not None:
                        yield attempt
        except OSError as e:
            print("Không đọc được attempts.jsonl:", e)
            return

    def load_attempts(self) -> List[LearningAttempt]:
        return list(self.iter_attempts())

    def recent_attempts(self, limit: int = 50) -> List[LearningAttempt]:
        if limit <= 0:
            return []
        all_items = self.load_attempts()
        return all_items[-limit:]


def load_attempts(filename: str) -> List[LearningAttempt]:
    return AttemptHistory(filename).load_attempts()


def iter_attempts(filename: str) -> Iterator[LearningAttempt]:
    return AttemptHistory(filename).iter_attempts()


def recent_attempts(filename: str, limit: int = 50) -> List[LearningAttempt]:
    return AttemptHistory(filename).recent_attempts(limit)
