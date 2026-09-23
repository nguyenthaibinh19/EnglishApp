"""Cấu hình chung cho Dutch Guard.

Khi chạy bằng Python (đang sửa code): dữ liệu và .env nằm cạnh source.
Khi chạy file .exe đã đóng gói: dữ liệu nằm ở %APPDATA%\\DutchGuard,
còn file cài nằm ở %LOCALAPPDATA%\\DutchGuard.
"""

import json
import os
import sys

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def is_frozen() -> bool:
    """True khi đang chạy file .exe do PyInstaller đóng gói."""
    return bool(getattr(sys, "frozen", False))


def resource_dir() -> str:
    """Thư mục chứa file đóng kèm (vocab mẫu, bài đọc)."""
    if is_frozen():
        return getattr(sys, "_MEIPASS", BASE_DIR)
    return BASE_DIR


def data_dir() -> str:
    """Thư mục người dùng ghi được: từ vựng, tiến độ, cài đặt."""
    if is_frozen():
        root = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(root, "DutchGuard")
    return BASE_DIR


def install_dir() -> str:
    """Nơi bản .exe tự chép vào để shortcut Startup không bị gãy."""
    root = os.environ.get("LOCALAPPDATA") or data_dir()
    return os.path.join(root, "DutchGuard")


def installed_exe() -> str:
    return os.path.join(install_dir(), "DutchGuard.exe")


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

VOCAB_FILE = os.path.join(data_dir(), "vocab.json")
PROGRESS_FILE = os.path.join(data_dir(), "progress.json")
CACHE_DIR = os.path.join(data_dir(), "cache")
SETTINGS_FILE = os.path.join(data_dir(), "settings.json")
READING_DIR = os.path.join(resource_dir(), "Reading")
STARTER_VOCAB_FILE = os.path.join(resource_dir(), "vocab.json")

# .env chỉ dùng khi chạy source. Bản .exe đọc settings.json trong reload().
if not is_frozen():
    load_dotenv()

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

OPENAI_TIMEOUT = _env_float("OPENAI_TIMEOUT", 90.0)

# ---------- Chế độ khóa màn hình ----------

# Đặt LOCK_SCREEN=0 trong .env khi đang dev để cửa sổ không fullscreen/topmost.
LOCK_SCREEN = _env_bool("LOCK_SCREEN", True)

# Điền ở cuối file, sau khi reload() đọc .env hoặc settings.json.
OPENAI_API_KEY = ""
OPENAI_MODEL = "gpt-4o-mini"
OPENAI_BASE_URL = None
EMERGENCY_PASSWORD = ""


# Các giá trị mẫu trong .env.example, coi như chưa cấu hình.
_PLACEHOLDER_KEYS = ("sk-...", "sk-xxx", "your-api-key", "<your-key>")


def looks_like_api_key(key: str) -> bool:
    key = (key or "").strip()
    if not key or key.lower() in _PLACEHOLDER_KEYS:
        return False
    return len(key) >= 20


def _read_settings() -> dict:
    if not os.path.exists(SETTINGS_FILE):
        return {}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def save_settings(openai_api_key: str):
    """Lưu API key của người dùng. Mật khẩu thoát không ghi ra file này."""
    os.makedirs(data_dir(), exist_ok=True)
    payload = {
        "openai_api_key": openai_api_key.strip(),
        "openai_model": OPENAI_MODEL or "gpt-4o-mini",
    }
    tmp = SETTINGS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, SETTINGS_FILE)
    reload()


def bundled_password() -> str:
    """Mật khẩu dev đóng kèm trong file .exe. Không nằm trong AppData."""
    path = os.path.join(resource_dir(), "bundled_secrets.json")
    if not os.path.isfile(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return ""
    if not isinstance(data, dict):
        return ""
    return str(data.get("emergency_password") or "")


def reload():
    """Đọc API key từ settings.json (bản .exe) hoặc .env (lúc dev).

    Mật khẩu thoát khẩn cấp luôn là mật khẩu của dev: trong .env khi sửa code,
    hoặc đóng sẵn trong .exe. Người dùng không được chọn mật khẩu này.
    """
    global OPENAI_API_KEY, OPENAI_MODEL, OPENAI_BASE_URL, EMERGENCY_PASSWORD

    if not is_frozen():
        load_dotenv()

    settings = _read_settings() if is_frozen() else {}
    OPENAI_API_KEY = str(
        settings.get("openai_api_key")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("vocab_teacher_key")
        or ""
    ).strip()
    OPENAI_MODEL = str(
        settings.get("openai_model") or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
    ).strip()
    base_url = str(settings.get("openai_base_url") or os.getenv("OPENAI_BASE_URL") or "").strip()
    OPENAI_BASE_URL = base_url or None
    if is_frozen():
        EMERGENCY_PASSWORD = bundled_password()
    else:
        EMERGENCY_PASSWORD = str(os.getenv("EMERGENCY_PASSWORD") or "")


def ai_is_configured() -> bool:
    """Có API key thật hay không (bỏ qua giá trị mẫu chép từ .env.example)."""
    return looks_like_api_key(OPENAI_API_KEY)


def is_ready() -> bool:
    """Đủ key và mật khẩu thoát khẩn cấp để vào bài học."""
    return ai_is_configured() and bool(EMERGENCY_PASSWORD)


reload()
