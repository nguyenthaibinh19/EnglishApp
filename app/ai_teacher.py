"""Compatibility facade for StudyGuard AI use cases.

Callers (quiz_app, reading_source, account_server) keep importing this module.
Implementation lives under `ai/` (AIService → AIProvider → OpenAIProvider).

Mọi hàm ở đây đều chặn (blocking) nên giao diện phải gọi chúng qua
ui_common.run_async để cửa sổ không bị đơ.
"""

from ai.base import AIError
from ai.service import get_service

# Giữ tên cũ để except/handlers hiện tại không đổi.
AITeacherError = AIError


def is_configured() -> bool:
    return get_service().is_configured()


def check_sentence(
    target_word: str,
    user_sentence: str,
    meaning_vi: str = "",
    profile: dict = None,
    native_label: str = None,
    level: str = None,
) -> dict:
    """Chấm một câu do học viên đặt trong ngôn ngữ đang học."""
    result = get_service().grade_answer(
        target_word,
        user_sentence,
        meaning_vi,
        profile=profile,
        native_label=native_label,
        level=level,
    )
    return result.as_dict()


def generate_reading(
    entries: list,
    level: str = None,
    passage_words: int = None,
    profile: dict = None,
    native_label: str = None,
) -> dict:
    """Sinh một bài đọc trong ngôn ngữ đang học, xoay quanh các từ đã ôn.

    `entries` là list các dict có khóa word (hoặc nl/en cũ) và vi.
    """
    return get_service().generate_reading(
        entries,
        level=level,
        passage_words=passage_words,
        profile=profile,
        native_label=native_label,
    )
