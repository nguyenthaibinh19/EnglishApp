"""Registry ngôn ngữ học (study languages) — nguồn sự thật duy nhất.

Tách biệt với ngôn ngữ gốc / UI (native): native chỉ là vi|en trong settings,
không nằm trong registry này.

Thêm ngôn ngữ học = thêm một StudyLanguage + file starters/<mã>.json.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional


# Default / fallback lịch sử (Dutch-first). Đổi giá trị này sẽ đổi hành vi
# khi settings thiếu hoặc mã không hợp lệ — giữ "nl" để tương thích.
DEFAULT_STUDY_CODE = "nl"


@dataclass(frozen=True)
class StudyLanguage:
    """Metadata một ngôn ngữ học mà app đã hỗ trợ.

    Chỉ gồm trường mà runtime hiện dùng (UI label, AI prompts, so khớp đáp án,
    starter mẫu). Không thêm field dự phòng.
    """

    code: str
    label: str
    name_vi: str
    name_en: str
    articles: tuple
    elisions: tuple
    sample: str

    def as_profile(self, include_code: bool = False) -> dict:
        """Dict tương thích callers cũ (current_language, AI, dictionary)."""
        profile = {
            "label": self.label,
            "name_vi": self.name_vi,
            "name_en": self.name_en,
            "articles": self.articles,
            "elisions": self.elisions,
            "sample": self.sample,
        }
        if include_code:
            profile["code"] = self.code
        return profile


def _build_registry() -> tuple:
    return (
        StudyLanguage(
            code="nl",
            label="Tiếng Hà Lan",
            name_vi="tiếng Hà Lan",
            name_en="Dutch",
            articles=("de", "het", "een", "'t"),
            elisions=(),
            sample="de fiets",
        ),
        StudyLanguage(
            code="en",
            label="Tiếng Anh",
            name_vi="tiếng Anh",
            name_en="English",
            articles=("the", "a", "an"),
            elisions=(),
            sample="the house",
        ),
        StudyLanguage(
            code="fr",
            label="Tiếng Pháp",
            name_vi="tiếng Pháp",
            name_en="French",
            articles=("le", "la", "les", "un", "une", "des", "du", "au", "aux"),
            elisions=("l'", "d'", "j'", "n'", "qu'"),
            sample="la maison",
        ),
        StudyLanguage(
            code="de",
            label="Tiếng Đức",
            name_vi="tiếng Đức",
            name_en="German",
            articles=(
                "der", "die", "das", "den", "dem", "des",
                "ein", "eine", "einen", "einem", "einer",
            ),
            elisions=(),
            sample="das Haus",
        ),
        StudyLanguage(
            code="es",
            label="Tiếng Tây Ban Nha",
            name_vi="tiếng Tây Ban Nha",
            name_en="Spanish",
            articles=("el", "la", "los", "las", "un", "una", "unos", "unas"),
            elisions=(),
            sample="la casa",
        ),
        StudyLanguage(
            code="it",
            label="Tiếng Ý",
            name_vi="tiếng Ý",
            name_en="Italian",
            articles=("il", "lo", "la", "i", "gli", "le", "un", "uno", "una"),
            elisions=("l'", "un'"),
            sample="la casa",
        ),
        StudyLanguage(
            code="pt",
            label="Tiếng Bồ Đào Nha",
            name_vi="tiếng Bồ Đào Nha",
            name_en="Portuguese",
            articles=("o", "a", "os", "as", "um", "uma", "uns", "umas"),
            elisions=(),
            sample="a casa",
        ),
    )


SUPPORTED_LANGUAGES: tuple = _build_registry()
_BY_CODE = {lang.code: lang for lang in SUPPORTED_LANGUAGES}

# Mapping cũ: code -> profile dict (không có khóa "code"). Callers đọc
# LANGUAGES[code]["label"] / .items() / `in LANGUAGES` vẫn chạy.
LANGUAGES = {lang.code: lang.as_profile(include_code=False) for lang in SUPPORTED_LANGUAGES}


def default_study_code() -> str:
    return DEFAULT_STUDY_CODE


def default_language() -> StudyLanguage:
    return _BY_CODE[DEFAULT_STUDY_CODE]


def is_supported_language(code: str) -> bool:
    return str(code or "").strip().lower() in _BY_CODE


def get_language(code: str) -> Optional[StudyLanguage]:
    """Tra cứu đúng mã. Không fallback — None nếu không hỗ trợ."""
    return _BY_CODE.get(str(code or "").strip().lower())


def resolve_language(code: str) -> StudyLanguage:
    """Tra cứu có fallback DEFAULT_STUDY_CODE (hành vi get() cũ)."""
    return get_language(code) or default_language()


def get(code: str) -> dict:
    """Profile dict; mã lạ → profile của ngôn ngữ mặc định (tương thích cũ)."""
    return resolve_language(code).as_profile(include_code=False)


def codes() -> list:
    return [lang.code for lang in SUPPORTED_LANGUAGES]


def iter_languages() -> Iterable[StudyLanguage]:
    return SUPPORTED_LANGUAGES
