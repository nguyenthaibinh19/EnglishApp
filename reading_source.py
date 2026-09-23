"""Chuẩn bị bài đọc: chọn từ, gọi AI, lưu cache, và nguồn dự phòng.

Tách khỏi giao diện để reading_app chỉ còn lo việc vẽ và chấm bài.
"""

import hashlib
import json
import os
import random

import ai_teacher
import config
from progress import today_key
from reading_schema import normalize_test
from text_utils import entry_word, normalize, strip_tags


# ============================================================
# Chọn từ cho bài đọc
# ============================================================


def select_words(store, progress, count: int = None) -> list:
    """Ưu tiên từ đã kiểm tra hôm nay, thiếu thì bù bằng từ yếu rồi từ ngẫu nhiên."""
    count = count or config.READING_WORD_COUNT
    if store.count() == 0:
        return []

    chosen = []
    seen = set()

    def take(entries):
        for entry in entries:
            key = normalize(entry_word(entry))
            if key in seen:
                continue
            seen.add(key)
            chosen.append(entry)
            if len(chosen) >= count:
                return True
        return False

    # 1) Từ đã học hôm nay - đây là mục tiêu chính.
    today_entries = store.entries_for_keys(progress.words_studied_today())
    random.shuffle(today_entries)
    if take(today_entries):
        return chosen

    # 2) Từ hay sai nhất.
    if take(store.entries_for_keys(progress.weakest_words(count * 2))):
        return chosen

    # 3) Bù ngẫu nhiên cho đủ số lượng.
    pool = [e for e in store.all() if normalize(entry_word(e)) not in seen]
    random.shuffle(pool)
    take(pool)
    return chosen


# ============================================================
# Cache theo ngày
# ============================================================


def _cache_key(words: list) -> str:
    raw = config.native_code() + "|" + "|".join(sorted(normalize(entry_word(w)) for w in words))
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]
    return f"reading_{today_key()}_{digest}.json"


def load_cached(words: list):
    path = os.path.join(config.cache_dir(), _cache_key(words))
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return normalize_test(json.load(f))
    except (json.JSONDecodeError, OSError, ValueError):
        return None


def save_cache(test: dict, words: list):
    os.makedirs(config.cache_dir(), exist_ok=True)
    path = os.path.join(config.cache_dir(), _cache_key(words))
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(test, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print("Không lưu được cache bài đọc:", e)


# ============================================================
# Nguồn dự phòng: bài tự soạn trong thư mục Reading/
# ============================================================


def _extract_pdf_text(pdf_path: str) -> str:
    try:
        import PyPDF2
    except ImportError:
        return ""
    parts = []
    try:
        with open(pdf_path, "rb") as f:
            for page in PyPDF2.PdfReader(f).pages:
                try:
                    parts.append((page.extract_text() or "").strip())
                except Exception:  # noqa: BLE001 - trang hỏng thì bỏ qua
                    continue
    except OSError as e:
        print("Không đọc được PDF:", e)
    return "\n\n".join(p for p in parts if p)


def load_local_test():
    """Bốc ngẫu nhiên một bài trong Reading/<tên bài>/AnswerKey.json."""
    root = config.READING_DIR
    if not os.path.isdir(root):
        return None

    folders = [
        os.path.join(root, name)
        for name in os.listdir(root)
        if os.path.isfile(os.path.join(root, name, "AnswerKey.json"))
    ]
    if not folders:
        return None

    folder = random.choice(folders)
    try:
        with open(os.path.join(folder, "AnswerKey.json"), "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print("Không đọc được AnswerKey.json:", e)
        return None

    if not data.get("passage"):
        pdf_path = os.path.join(folder, data.get("pdf_file", "passage.pdf"))
        if os.path.exists(pdf_path):
            data["passage"] = _extract_pdf_text(pdf_path)

    data.setdefault("title", os.path.basename(folder))
    data["source"] = "local"
    try:
        return normalize_test(data)
    except ValueError as e:
        print(f"Bài đọc {folder} không hợp lệ: {e}")
        return None


# ============================================================
# Đầu vào chính
# ============================================================


class NoReadingAvailable(RuntimeError):
    """Không tạo được bài đọc và cũng không có bài dự phòng."""


def build_test(store, progress, force_new: bool = False) -> dict:
    """Trả về một bài đọc đã chuẩn hóa. Hàm này chặn, hãy gọi qua run_async."""
    words = select_words(store, progress)

    if words and not force_new:
        cached = load_cached(words)
        if cached is not None:
            return cached

    if words and ai_teacher.is_configured():
        try:
            test = ai_teacher.generate_reading(words)
            test["target_words"] = [strip_tags(entry_word(w)) for w in words]
            save_cache(test, words)
            return test
        except ai_teacher.AITeacherError as ai_error:
            local = load_local_test()
            if local is not None:
                local["warning"] = f"Không gọi được AI ({ai_error}). Đang dùng bài đọc có sẵn."
                return local
            raise

    local = load_local_test()
    if local is not None:
        if not ai_teacher.is_configured():
            local["warning"] = (
                "Chưa cấu hình API key nên không tạo được bài đọc mới. "
                "Đang dùng bài đọc có sẵn trong thư mục Reading/."
            )
        return local

    raise NoReadingAvailable(
        "Chưa tạo được bài đọc.\n\n"
        "Cần một trong hai thứ sau:\n"
        "• API key OpenAI trong file .env (OPENAI_API_KEY=sk-...) để AI tự viết bài theo từ đã học.\n"
        "• Hoặc một thư mục con trong Reading/ có file AnswerKey.json."
    )
