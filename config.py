"""Cấu hình chung cho Dutch Guard.

Mọi hằng số ở đây đều có thể ghi đè bằng biến môi trường (đặt trong file .env),
nhờ vậy không cần sửa code khi muốn đổi mục tiêu học hay đổi model AI.
"""

import os

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    try:
        return float(raw) if raw else default
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "y", "on")


# ---------- Nhận diện ứng dụng ----------

APP_NAME = "Dutch Guard"
TARGET_LANG_NAME_VI = "tiếng Hà Lan"
TARGET_LANG_NAME_EN = "Dutch"

# ---------- Đường dẫn dữ liệu ----------

VOCAB_FILE = os.path.join(BASE_DIR, "vocab.json")
PROGRESS_FILE = os.path.join(BASE_DIR, "progress.json")
CACHE_DIR = os.path.join(BASE_DIR, "cache")
READING_DIR = os.path.join(BASE_DIR, "Reading")

# ---------- Luyện từ vựng ----------

# Số câu đúng cần đạt để mở khóa phần từ vựng.
QUIZ_TARGET_CORRECT = _env_int("QUIZ_TARGET_CORRECT", 30)

# Sau bao nhiêu câu thì một từ trả lời sai được hỏi lại (kiểu Duolingo).
WRONG_REQUEUE_AFTER = _env_int("WRONG_REQUEUE_AFTER", 3)

# Trả lời sai có bị bắt đặt câu ví dụ (chấm bằng AI) hay không.
FORCE_SENTENCE_ON_WRONG = _env_bool("FORCE_SENTENCE_ON_WRONG", True)

# Khoảng cách Levenshtein tối đa để coi là "gõ sai chính tả" thay vì sai hẳn.
TYPO_TOLERANCE = _env_int("TYPO_TOLERANCE", 1)

# ---------- Luyện đọc ----------

# Số từ được đưa vào bài đọc do AI sinh ra.
READING_WORD_COUNT = _env_int("READING_WORD_COUNT", 12)

# Tỉ lệ đúng tối thiểu để qua phần reading (0.8 = 80%).
READING_PASS_RATIO = _env_float("READING_PASS_RATIO", 0.8)

# Trình độ CEFR dùng cho prompt sinh bài đọc: A1, A2, B1, B2...
READING_LEVEL = (os.getenv("DUTCH_LEVEL") or "A2").strip().upper()

# Độ dài bài đọc mong muốn (số từ).
READING_PASSAGE_WORDS = _env_int("READING_PASSAGE_WORDS", 220)

# ---------- OpenAI ----------

# Ưu tiên OPENAI_API_KEY, vẫn chấp nhận tên biến cũ vocab_teacher_key.
OPENAI_API_KEY = (
    os.getenv("OPENAI_API_KEY") or os.getenv("vocab_teacher_key") or ""
).strip()
OPENAI_MODEL = (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()
OPENAI_BASE_URL = (os.getenv("OPENAI_BASE_URL") or "").strip() or None
OPENAI_TIMEOUT = _env_float("OPENAI_TIMEOUT", 90.0)

# ---------- Chế độ khóa màn hình ----------

# Đặt LOCK_SCREEN=0 trong .env khi đang dev để cửa sổ không fullscreen/topmost.
LOCK_SCREEN = _env_bool("LOCK_SCREEN", True)

# Mật khẩu để bấm “Thoát khẩn cấp”. Để trống thì nút đó không thoát được.
EMERGENCY_PASSWORD = (os.getenv("EMERGENCY_PASSWORD") or "").strip()


# Các giá trị mẫu trong .env.example, coi như chưa cấu hình.
_PLACEHOLDER_KEYS = ("sk-...", "sk-xxx", "your-api-key", "<your-key>")


def ai_is_configured() -> bool:
    """Có API key thật hay không (bỏ qua giá trị mẫu chép từ .env.example)."""
    key = OPENAI_API_KEY
    if not key or key.lower() in _PLACEHOLDER_KEYS:
        return False
    return len(key) >= 20
