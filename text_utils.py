"""Chuẩn hóa và so khớp câu trả lời tiếng Hà Lan.

Toàn bộ logic so sánh đáp án nằm ở đây để phần giao diện không phải biết gì về
mạo từ, dấu phụ hay tag loại từ.
"""

import re
import unicodedata

# Mạo từ tiếng Hà Lan: khi học viên gõ thiếu "de/het/een" vẫn tính là đúng.
DUTCH_ARTICLES = ("de", "het", "een", "'t")

# Tag loại từ có thể xuất hiện trong vocab.json: "fiets (de)", "lopen (ww)"...
_POS_TAG = re.compile(
    r"\s*\(\s*(?:de|het|n|nw|zn|noun|v|ww|verb|adj|bn|adjective|adv|bw|adverb|"
    r"prep|vz|voorzetsel|idiom|uitdrukking|spreekwoord|phr|phrv|pl|mv|"
    r"m|f|o|onz|de/het)\s*\)\s*",
    re.IGNORECASE,
)

# Dấu câu bám ở đầu/cuối đáp án, bỏ đi cho dễ tính.
_EDGE_PUNCT = re.compile(r"^[\s.,;:!?\"'\-–—]+|[\s.,;:!?\"'\-–—]+$")

# Ký tự phân tách nhiều đáp án chấp nhận được trong cùng một ô: "fiets | rijwiel".
_ALT_SPLIT = re.compile(r"\s*[|/;]\s*|\s+of\s+")


def strip_tags(s: str) -> str:
    """Bỏ tag loại từ trong ngoặc và ký hiệu '+' mô tả cấu trúc."""
    if not s:
        return ""
    s = re.sub(r"\s*\+\s*", " ", s.strip())
    s = _POS_TAG.sub(" ", s)
    # Phòng hờ: ngoặc còn sót ở cuối chuỗi (ví dụ "lopen (onregelmatig)").
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s)
    return re.sub(r"\s+", " ", s).strip()


def normalize(s: str) -> str:
    """Đưa chuỗi về dạng chuẩn để so sánh: bỏ tag, lowercase, gọn khoảng trắng."""
    s = strip_tags(s).lower().replace("’", "'").replace("`", "'")
    s = _EDGE_PUNCT.sub("", s)
    return re.sub(r"\s+", " ", s).strip()


def fold_accents(s: str) -> str:
    """Bỏ dấu phụ: 'één' -> 'een', 'café' -> 'cafe'."""
    decomposed = unicodedata.normalize("NFD", s)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def entry_word(entry: dict) -> str:
    """Từ mục tiêu, dù file còn khóa cũ nl/en hay khóa mới word."""
    if not entry:
        return ""
    return str(entry.get("word") or entry.get("nl") or entry.get("en") or "")


def _matching_rules(articles=None, elisions=None):
    if articles is not None or elisions is not None:
        return articles or (), elisions or ()
    import config
    profile = config.current_language()
    return profile.get("articles") or (), profile.get("elisions") or ()


def without_article(s: str, articles=None) -> str:
    """Bỏ mạo từ đứng đầu: 'de fiets' -> 'fiets', 'the house' -> 'house'."""
    articles = articles if articles is not None else _matching_rules()[0]
    parts = s.split(" ", 1)
    if len(parts) == 2 and parts[0] in articles:
        return parts[1].strip()
    return s


def without_elision(s: str, elisions=None) -> str:
    """Bỏ mạo từ dính: l'école -> école."""
    elisions = elisions if elisions is not None else _matching_rules()[1]
    folded = s.replace("’", "'")
    for prefix in elisions:
        if folded.lower().startswith(prefix) and len(folded) > len(prefix):
            return folded[len(prefix):].strip()
    return s


def display_word(entry: dict) -> str:
    """Dạng hiển thị đẹp của một từ (giữ nguyên mạo từ, bỏ tag loại từ)."""
    return strip_tags(entry_word(entry))


def accepted_forms(entry: dict, articles=None, elisions=None) -> set:
    """Tập hợp mọi cách viết được chấp nhận cho một từ.

    Bao gồm: dạng đầy đủ, dạng bỏ mạo từ, các đáp án ngăn bằng '|' hoặc '/',
    và các dạng liệt kê trong trường 'alt'.
    """
    raw_values = [entry_word(entry)]
    alt = entry.get("alt") or []
    if isinstance(alt, str):
        alt = [alt]
    raw_values.extend(alt)

    forms = set()
    for raw in raw_values:
        for piece in _ALT_SPLIT.split(str(raw)):
            norm = normalize(piece)
            if not norm:
                continue
            forms.add(norm)
            bare = without_elision(without_article(norm, articles), elisions)
            forms.add(bare)
            forms.add(without_article(bare, articles))
    return {f for f in forms if f}


def levenshtein(a: str, b: str) -> int:
    """Khoảng cách chỉnh sửa, dùng để phát hiện lỗi gõ nhầm."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            current.append(
                min(
                    previous[j] + 1,
                    current[j - 1] + 1,
                    previous[j - 1] + (ca != cb),
                )
            )
        previous = current
    return previous[-1]


def match_answer(user_answer: str, entry: dict, typo_tolerance: int = 1, articles=None, elisions=None):
    """So khớp câu trả lời với một từ.

    Trả về (verdict, best_form) trong đó verdict là:
      - "exact": đúng hoàn toàn
      - "near" : chỉ sai chính tả / thiếu dấu, vẫn tính là đúng nhưng có nhắc nhở
      - "wrong": sai
    """
    user = normalize(user_answer)
    forms = accepted_forms(entry, articles, elisions)
    if not user or not forms:
        return "wrong", display_word(entry)

    if user in forms:
        return "exact", user

    folded_user = fold_accents(user)
    if any(folded_user == fold_accents(f) for f in forms):
        return "near", min(forms, key=len)

    best_form = min(forms, key=lambda f: levenshtein(folded_user, fold_accents(f)))
    distance = levenshtein(folded_user, fold_accents(best_form))
    # Chỉ tha lỗi gõ nhầm với từ đủ dài, tránh "kat" lọt thành "kan".
    if distance <= typo_tolerance and len(best_form) >= 5:
        return "near", best_form

    return "wrong", display_word(entry)


def sentence_around(passage: str, offset: int) -> str:
    """Câu chứa vị trí offset, cắt theo dấu chấm hoặc xuống dòng."""
    text = passage or ""
    offset = max(0, min(int(offset), len(text)))
    left = 0
    for match in re.finditer(r"[.!?…]+[\"'”»)\]]*|\n+", text[:offset]):
        left = match.end()
    right = re.search(r"[.!?…]+[\"'”»)\]]*|\n+", text[offset:])
    end = offset + right.end() if right else len(text)
    return " ".join(text[left:end].split())
