"""Các ngôn ngữ dùng bảng chữ cái Latinh mà app hỗ trợ.

Thêm một ngôn ngữ là thêm một mục ở đây, kèm file mẫu starters/<mã>.json.
"""

LANGUAGES = {
    "nl": {
        "label": "Tiếng Hà Lan",
        "name_vi": "tiếng Hà Lan",
        "name_en": "Dutch",
        "articles": ("de", "het", "een", "'t"),
        "elisions": (),
        "sample": "de fiets",
    },
    "en": {
        "label": "Tiếng Anh",
        "name_vi": "tiếng Anh",
        "name_en": "English",
        "articles": ("the", "a", "an"),
        "elisions": (),
        "sample": "the house",
    },
    "fr": {
        "label": "Tiếng Pháp",
        "name_vi": "tiếng Pháp",
        "name_en": "French",
        "articles": ("le", "la", "les", "un", "une", "des", "du", "au", "aux"),
        "elisions": ("l'", "d'", "j'", "n'", "qu'"),
        "sample": "la maison",
    },
    "de": {
        "label": "Tiếng Đức",
        "name_vi": "tiếng Đức",
        "name_en": "German",
        "articles": ("der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "einem", "einer"),
        "elisions": (),
        "sample": "das Haus",
    },
    "es": {
        "label": "Tiếng Tây Ban Nha",
        "name_vi": "tiếng Tây Ban Nha",
        "name_en": "Spanish",
        "articles": ("el", "la", "los", "las", "un", "una", "unos", "unas"),
        "elisions": (),
        "sample": "la casa",
    },
    "it": {
        "label": "Tiếng Ý",
        "name_vi": "tiếng Ý",
        "name_en": "Italian",
        "articles": ("il", "lo", "la", "i", "gli", "le", "un", "uno", "una"),
        "elisions": ("l'", "un'"),
        "sample": "la casa",
    },
    "pt": {
        "label": "Tiếng Bồ Đào Nha",
        "name_vi": "tiếng Bồ Đào Nha",
        "name_en": "Portuguese",
        "articles": ("o", "a", "os", "as", "um", "uma", "uns", "umas"),
        "elisions": (),
        "sample": "a casa",
    },
}


def get(code: str) -> dict:
    return LANGUAGES.get(code) or LANGUAGES["nl"]


def codes() -> list:
    return list(LANGUAGES)
