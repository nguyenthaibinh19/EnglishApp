"""Cấu hình chung cho Dutch Guard.

Khi chạy bằng Python (đang sửa code): dữ liệu và .env nằm cạnh source.
Khi chạy file .exe đã đóng gói: dữ liệu nằm ở %APPDATA%\\DutchGuard,
còn file cài nằm ở %LOCALAPPDATA%\\DutchGuard.
"""

import json
import os
import shutil
import sys

from dotenv import load_dotenv

import languages

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

APP_NAME = "Language Guard"

# ---------- Đường dẫn dữ liệu ----------

SETTINGS_FILE = os.path.join(data_dir(), "settings.json")
READING_DIR = os.path.join(resource_dir(), "Reading")
STARTER_VOCAB_FILE = os.path.join(resource_dir(), "vocab.json")

# .env chỉ dùng khi chạy source. Bản .exe đọc settings.json trong reload().
if not is_frozen():
    load_dotenv()

# ---------- Luyện từ vựng ----------

# Số câu đúng cần đạt trong một lần mở app. Lần mở sau tính lại từ đầu.
QUIZ_TARGET_CORRECT = _env_int("QUIZ_TARGET_CORRECT", 5)

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


def _write_settings(payload: dict):
    os.makedirs(data_dir(), exist_ok=True)
    tmp = SETTINGS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, SETTINGS_FILE)


def save_settings(openai_api_key: str):
    """Lưu API key của người dùng. Mật khẩu thoát không ghi ra file này."""
    payload = _read_settings()
    payload["openai_api_key"] = openai_api_key.strip()
    payload["openai_model"] = OPENAI_MODEL or "gpt-4o-mini"
    payload.pop("emergency_password", None)
    _write_settings(payload)
    reload()


def active_code() -> str:
    code = str(_read_settings().get("language") or "nl").strip().lower()
    return code if code in languages.LANGUAGES else "nl"


def current_language() -> dict:
    profile = dict(languages.get(active_code()))
    profile["code"] = active_code()
    return profile


def set_language(code: str) -> str:
    """Nhớ ngôn ngữ đang mở để luyện. Không đánh dấu lần mở máy này là đã xong."""
    chosen = code if code in languages.LANGUAGES else "nl"
    payload = _read_settings()
    payload["language"] = chosen
    payload.pop("emergency_password", None)
    _write_settings(payload)
    return chosen


def study_codes() -> list:
    """Ngôn ngữ người dùng đã chọn để học. Chỉ những mã này mới bị bắt làm bài."""
    raw = _read_settings().get("study_languages")
    chosen = []
    if isinstance(raw, list):
        for item in raw:
            code = str(item).strip().lower()
            if code in languages.LANGUAGES and code not in chosen:
                chosen.append(code)
    if chosen:
        return chosen
    return [active_code()]


def native_code() -> str:
    """Ngôn ngữ gốc để dịch nghĩa: vi hoặc en."""
    code = str(_read_settings().get("native") or "vi").strip().lower()
    return "en" if code == "en" else "vi"


def native_label() -> str:
    return "English" if native_code() == "en" else "Tiếng Việt"


def language_setup_done() -> bool:
    settings = _read_settings()
    native = str(settings.get("native") or "").strip().lower()
    chosen = settings.get("study_languages")
    return native in ("vi", "en") and isinstance(chosen, list) and bool(chosen)


def save_language_choices(native: str, codes) -> list:
    """Ghi ngôn ngữ gốc và danh sách tiếng cần học sau khi từ điển đã được kiểm tra."""
    chosen = []
    for item in codes:
        code = str(item).strip().lower()
        if code in languages.LANGUAGES and code not in chosen:
            chosen.append(code)
    if not chosen:
        chosen = ["nl"]
    payload = _read_settings()
    payload["native"] = "en" if str(native).strip().lower() == "en" else "vi"
    payload["study_languages"] = chosen
    if str(payload.get("language") or "").strip().lower() not in chosen:
        payload["language"] = chosen[0]
    payload.pop("emergency_password", None)
    _write_settings(payload)
    return chosen


def set_native(code: str) -> str:
    chosen = "en" if str(code).strip().lower() == "en" else "vi"
    payload = _read_settings()
    payload["native"] = chosen
    payload.pop("emergency_password", None)
    _write_settings(payload)
    return chosen


def set_study_codes(codes) -> list:
    """Ghi danh sách ngôn ngữ cần học. Luôn giữ ít nhất một ngôn ngữ."""
    chosen = []
    for item in codes:
        code = str(item).strip().lower()
        if code in languages.LANGUAGES and code not in chosen:
            chosen.append(code)
    if not chosen:
        chosen = [active_code()]
    payload = _read_settings()
    payload["study_languages"] = chosen
    if str(payload.get("language") or "").strip().lower() not in chosen:
        payload["language"] = chosen[0]
    payload.pop("emergency_password", None)
    _write_settings(payload)
    return chosen


def language_dir(code: str = None) -> str:
    return os.path.join(data_dir(), "languages", code or active_code())


def vocab_path(code: str = None) -> str:
    return os.path.join(language_dir(code), "vocab.json")


def progress_path(code: str = None) -> str:
    return os.path.join(language_dir(code), "progress.json")


def cache_dir(code: str = None) -> str:
    return os.path.join(language_dir(code), "cache")


def _starter_file(code: str):
    specific = os.path.join(resource_dir(), "starters", f"{code}.json")
    if os.path.isfile(specific):
        return specific
    if code == "nl" and os.path.isfile(STARTER_VOCAB_FILE):
        return STARTER_VOCAB_FILE
    return None


def ensure_language_data():
    """Tách dữ liệu theo ngôn ngữ và giữ bộ từ Hà Lan đang có."""
    os.makedirs(language_dir("nl"), exist_ok=True)

    legacy_vocab = os.path.join(data_dir(), "vocab.json")
    legacy_progress = os.path.join(data_dir(), "progress.json")
    legacy_cache = os.path.join(data_dir(), "cache")
    if os.path.isfile(legacy_vocab) and not os.path.isfile(vocab_path("nl")):
        shutil.copy2(legacy_vocab, vocab_path("nl"))
    if os.path.isfile(legacy_progress) and not os.path.isfile(progress_path("nl")):
        shutil.copy2(legacy_progress, progress_path("nl"))
    if os.path.isdir(legacy_cache) and not os.path.isdir(cache_dir("nl")):
        shutil.copytree(legacy_cache, cache_dir("nl"))

    for code in languages.codes():
        dest = vocab_path(code)
        if os.path.isfile(dest):
            continue
        starter = _starter_file(code)
        os.makedirs(language_dir(code), exist_ok=True)
        if starter:
            shutil.copy2(starter, dest)


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
