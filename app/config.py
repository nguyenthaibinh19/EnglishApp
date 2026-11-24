"""Cấu hình chung cho langstudyguard.

Khi chạy bằng Python (đang sửa code): dữ liệu và .env nằm cạnh source
(development). Staging / production frozen builds use isolated AppData folders
per ADR-025 — never infer environment from the EXE filename alone.
"""

import json
import os
import shutil
import sys

from dotenv import load_dotenv

import app_environment
import languages

# Code nằm trong app/. Dữ liệu người dùng và file mẫu nằm ở thư mục gốc của dự án.
_HERE = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(_HERE)


def is_frozen() -> bool:
    """True khi đang chạy file .exe do PyInstaller đóng gói."""
    return bool(getattr(sys, "frozen", False))


def resource_dir() -> str:
    """Thư mục chứa file đóng kèm (vocab mẫu, bài đọc)."""
    if is_frozen():
        return getattr(sys, "_MEIPASS", BASE_DIR)
    return os.path.join(BASE_DIR, "data")


def _migrate_user_data(old: str, new: str):
    """Chép dữ liệu từ thư mục DutchGuard sang langstudyguard, không ghi đè file đã có."""
    if os.path.normcase(old) == os.path.normcase(new) or not os.path.isdir(old):
        return
    os.makedirs(new, exist_ok=True)
    for name in os.listdir(old):
        source = os.path.join(old, name)
        dest = os.path.join(new, name)
        if os.path.exists(dest):
            continue
        try:
            if os.path.isdir(source):
                shutil.copytree(source, dest)
            else:
                shutil.copy2(source, dest)
        except OSError:
            continue


def environment_identity():
    """Resolved build/runtime identity (cached)."""
    return app_environment.get_identity()


def data_dir() -> str:
    """Thư mục người dùng ghi được: từ vựng, tiến độ, cài đặt.

    ``LG_DATA_DIR`` may point at an isolated synthetic directory for tests.
    Non-production builds refuse production AppData / install paths (ADR-025 F1).
    """
    identity = environment_identity()
    explicit = (os.environ.get("LG_DATA_DIR") or "").strip()
    if identity.rc_smoke:
        if not explicit:
            raise app_environment.EnvironmentIdentityError(
                "RC smoke requires LG_DATA_DIR to point at an isolated test data root."
            )
        return app_environment.assert_data_root_allowed(explicit, identity=identity)
    if explicit:
        return app_environment.assert_data_root_allowed(explicit, identity=identity)
    if is_frozen():
        root = os.environ.get("APPDATA") or os.path.expanduser("~")
        current = os.path.join(root, identity.data_folder)
        # Legacy DutchGuard → genuine production only; never into RC/staging/dev.
        if (
            identity.runtime_environment == app_environment.ENV_PRODUCTION
            and not identity.rc_smoke
        ):
            _migrate_user_data(os.path.join(root, "DutchGuard"), current)
        # RC / non-production frozen paths must never touch production AppData.
        if identity.rc_smoke or identity.is_non_production or identity.identity_error:
            return app_environment.assert_data_root_allowed(current, identity=identity)
        return current
    # Source development keeps repo-root data. Staging from source uses AppData.
    if identity.runtime_environment == app_environment.ENV_DEVELOPMENT:
        return BASE_DIR
    root = os.environ.get("APPDATA") or os.path.expanduser("~")
    current = os.path.join(root, identity.data_folder)
    return app_environment.assert_data_root_allowed(current, identity=identity)


def install_dir() -> str:
    """Nơi bản .exe tự chép vào để shortcut Startup không bị gãy."""
    identity = environment_identity()
    root = os.environ.get("LOCALAPPDATA") or data_dir()
    return os.path.join(root, identity.install_folder)


def installed_exe() -> str:
    identity = environment_identity()
    return os.path.join(install_dir(), identity.exe_basename)


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

APP_NAME = "langstudyguard"
APP_VERSION = "1.5.0"
UPDATE_REPO = "nguyenthaibinh19/EnglishApp"

# ---------- Đường dẫn dữ liệu ----------

try:
    SETTINGS_FILE = os.path.join(data_dir(), "settings.json")
except app_environment.EnvironmentIdentityError:
    SETTINGS_FILE = ""
READING_DIR = os.path.join(resource_dir(), "Reading")
STARTER_VOCAB_FILE = os.path.join(resource_dir(), "vocab.json")


def _refresh_settings_path() -> None:
    """Keep SETTINGS_FILE aligned with the active environment data directory."""
    global SETTINGS_FILE
    # Tests may monkeypatch SETTINGS_FILE to a temp path; honor an explicit LG_DATA_DIR
    # or recompute from data_dir() when using the default layout.
    SETTINGS_FILE = os.path.join(data_dir(), "settings.json")


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

# Số từ mục tiêu cho Listening (StudyGuard chọn; AI không chọn).
# Phase 17C hard-caps at LISTENING_MAX_TARGETS regardless of env override.
LISTENING_MAX_TARGETS = 2
LISTENING_WORD_COUNT = _env_int("LISTENING_WORD_COUNT", 2)


def listening_target_count(requested=None) -> int:
    """Effective Listening target count for Phase 17C: clamped to 1..LISTENING_MAX_TARGETS."""
    raw = LISTENING_WORD_COUNT if requested is None else requested
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = LISTENING_MAX_TARGETS
    return max(1, min(int(LISTENING_MAX_TARGETS), value))

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
ACCOUNT_SERVER_URL = "http://127.0.0.1:8765"
ACCOUNT_TOKEN = ""
EMERGENCY_PASSWORD = ""
_DATA_ROOT_ERROR = ""


# Các giá trị mẫu trong .env.example, coi như chưa cấu hình.
_PLACEHOLDER_KEYS = ("sk-...", "sk-xxx", "your-api-key", "<your-key>")


def looks_like_api_key(key: str) -> bool:
    key = (key or "").strip()
    if not key or key.lower() in _PLACEHOLDER_KEYS:
        return False
    return len(key) >= 20


def _settings_path() -> str:
    """Active settings.json path.

    Honors ``LG_DATA_DIR`` for isolation tests. Otherwise uses ``SETTINGS_FILE``
    so pytest monkeypatches keep working.
    """
    if (os.environ.get("LG_DATA_DIR") or "").strip():
        return os.path.join(data_dir(), "settings.json")
    return SETTINGS_FILE


def _read_settings() -> dict:
    path = _settings_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_settings(payload: dict):
    path = _settings_path()
    os.makedirs(os.path.dirname(path) or data_dir(), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def save_account(username: str, token: str, user_id: int = None):
    """Nhớ phiên đăng nhập. Không lưu API key trên máy người học."""
    identity = environment_identity()
    if not identity.network_writes_allowed and identity.identity_error:
        raise app_environment.EnvironmentIdentityError(identity.identity_error)
    payload = _read_settings()
    payload.pop("openai_api_key", None)
    payload.pop("emergency_password", None)
    payload["account_username"] = username.strip().lower()
    payload["account_token"] = token.strip()
    payload["environment"] = app_environment.settings_environment_marker(identity)
    payload["build_channel"] = identity.build_channel
    if user_id is not None:
        payload["account_user_id"] = int(user_id)
    _write_settings(payload)
    reload()


def account_token() -> str:
    return ACCOUNT_TOKEN


def account_user_id() -> int:
    """Server user id for the signed-in account, or 0 when unknown."""
    raw = _read_settings().get("account_user_id")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 0
    return value if value > 0 else 0


def clear_account():
    """Xóa phiên đăng nhập đã hết hạn. Lần mở sau sẽ hỏi đăng nhập lại."""
    payload = _read_settings()
    payload.pop("account_token", None)
    payload.pop("account_username", None)
    payload.pop("account_user_id", None)
    payload.pop("openai_api_key", None)
    _write_settings(payload)
    reload()
    try:
        import account_sync_engine

        account_sync_engine.stop_active()
    except Exception:
        pass


def uses_account_server() -> bool:
    """Bản cài đặt luôn gọi AI qua tài khoản. Máy dev vẫn dùng key trong .env."""
    if is_frozen():
        return bool(ACCOUNT_TOKEN)
    return bool(ACCOUNT_TOKEN) and not looks_like_api_key(OPENAI_API_KEY)


def active_code() -> str:
    code = str(_read_settings().get("language") or languages.default_study_code()).strip().lower()
    return code if languages.is_supported_language(code) else languages.default_study_code()


def current_language() -> dict:
    lang = languages.resolve_language(active_code())
    return lang.as_profile(include_code=True)


def set_language(code: str) -> str:
    """Nhớ ngôn ngữ đang mở để luyện. Không đánh dấu lần mở máy này là đã xong."""
    chosen = (
        str(code).strip().lower()
        if languages.is_supported_language(code)
        else languages.default_study_code()
    )
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
            if languages.is_supported_language(code) and code not in chosen:
                chosen.append(code)
    if chosen:
        return chosen
    return [active_code()]


def native_code() -> str:
    """Ngôn ngữ gốc / UI (vi|en) — khác với study language."""
    code = str(_read_settings().get("native") or "vi").strip().lower()
    return "en" if code == "en" else "vi"


def native_label() -> str:
    return "English" if native_code() == "en" else "Tiếng Việt"


def ui(vi: str, en: str) -> str:
    """Chữ trên nút và thông báo, theo ngôn ngữ gốc của người học."""
    return en if native_code() == "en" else vi


def language_name(code: str) -> str:
    lang = languages.resolve_language(code)
    if native_code() == "en":
        return lang.name_en or lang.label or code
    return lang.label or code


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
        if languages.is_supported_language(code) and code not in chosen:
            chosen.append(code)
    if not chosen:
        chosen = [languages.default_study_code()]
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


# Phần ngoài từ vựng. Thêm mục vào đây khi có dạng bài mới.
OPTIONAL_ACTIVITIES = (
    {"id": "reading", "vi": "Đọc", "en": "Reading"},
    {"id": "listening", "vi": "Nghe", "en": "Listening"},
)


def activity_enabled(activity_id: str) -> bool:
    """True when the learner enables that optional activity.

    Missing settings: Reading defaults ON (historical). Listening defaults OFF
    until a production audio provider exists.
    """
    raw = _read_settings().get("activities")
    if not isinstance(raw, dict) or activity_id not in raw:
        return activity_id == "reading"
    return bool(raw.get(activity_id))


def set_activity_enabled(activity_id: str, enabled: bool) -> None:
    payload = _read_settings()
    activities = payload.get("activities")
    if not isinstance(activities, dict):
        activities = {}
    activities[str(activity_id)] = bool(enabled)
    payload["activities"] = activities
    payload.pop("emergency_password", None)
    _write_settings(payload)
    try:
        from account_prefs import mark_preferences_dirty

        mark_preferences_dirty()
    except Exception:
        pass


def set_study_codes(codes) -> list:
    """Ghi danh sách ngôn ngữ cần học. Luôn giữ ít nhất một ngôn ngữ."""
    chosen = []
    for item in codes:
        code = str(item).strip().lower()
        if languages.is_supported_language(code) and code not in chosen:
            chosen.append(code)
    if not chosen:
        chosen = [active_code()]
    payload = _read_settings()
    payload["study_languages"] = chosen
    if str(payload.get("language") or "").strip().lower() not in chosen:
        payload["language"] = chosen[0]
    payload.pop("emergency_password", None)
    _write_settings(payload)
    try:
        from account_prefs import mark_preferences_dirty

        mark_preferences_dirty()
    except Exception:
        pass
    return chosen


def language_dir(code: str = None) -> str:
    return os.path.join(data_dir(), "languages", code or active_code())


def vocab_path(code: str = None) -> str:
    return os.path.join(language_dir(code), "vocab.json")


def progress_path(code: str = None) -> str:
    return os.path.join(language_dir(code), "progress.json")


def attempts_path(code: str = None) -> str:
    """Nhật ký từng lần trả lời từ vựng (JSONL), tách khỏi progress.json."""
    return os.path.join(language_dir(code), "attempts.jsonl")


def cache_dir(code: str = None) -> str:
    return os.path.join(language_dir(code), "cache")


def _starter_file(code: str):
    specific = os.path.join(resource_dir(), "starters", f"{code}.json")
    if os.path.isfile(specific):
        return specific
    # Legacy: starter Hà Lan từng nằm ở data/vocab.json thay vì starters/nl.json.
    if code == languages.default_study_code() and os.path.isfile(STARTER_VOCAB_FILE):
        return STARTER_VOCAB_FILE
    return None


def ensure_language_data():
    """Tạo thư mục từng ngôn ngữ học; chuyển dữ liệu root cũ sang languages/nl."""
    default = languages.default_study_code()
    os.makedirs(language_dir(default), exist_ok=True)

    legacy_vocab = os.path.join(data_dir(), "vocab.json")
    legacy_progress = os.path.join(data_dir(), "progress.json")
    legacy_cache = os.path.join(data_dir(), "cache")
    if os.path.isfile(legacy_vocab) and not os.path.isfile(vocab_path(default)):
        shutil.copy2(legacy_vocab, vocab_path(default))
    if os.path.isfile(legacy_progress) and not os.path.isfile(progress_path(default)):
        shutil.copy2(legacy_progress, progress_path(default))
    if os.path.isdir(legacy_cache) and not os.path.isdir(cache_dir(default)):
        shutil.copytree(legacy_cache, cache_dir(default))

    for code in languages.codes():
        dest = vocab_path(code)
        if os.path.isfile(dest):
            continue
        starter = _starter_file(code)
        os.makedirs(language_dir(code), exist_ok=True)
        if starter:
            shutil.copy2(starter, dest)


def bundled_password() -> str:
    """Release builds do not embed an emergency password."""
    return ""


def bundled_account_server() -> str:
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
    return str(data.get("account_server_url") or "").strip()


def data_root_error() -> str:
    """Why RC smoke refused its data root, or empty when the root is usable."""
    return _DATA_ROOT_ERROR


def reload():
    """Đọc API key từ settings.json (bản .exe) hoặc .env (lúc dev).

    Mật khẩu thoát khẩn cấp luôn là mật khẩu của dev: trong .env khi sửa code,
    hoặc đóng sẵn trong .exe. Người dùng không được chọn mật khẩu này.
    """
    global OPENAI_API_KEY, OPENAI_MODEL, OPENAI_BASE_URL
    global ACCOUNT_SERVER_URL, ACCOUNT_TOKEN, APP_VERSION, SETTINGS_FILE
    global _DATA_ROOT_ERROR

    app_environment.reset_identity_cache()
    identity = environment_identity()
    if identity.version and identity.version != "unknown":
        APP_VERSION = identity.version
    # Do not reassign SETTINGS_FILE here — tests monkeypatch it; data_dir() already
    # follows LG_DATA_DIR / environment folder for normal runs.

    if not is_frozen():
        load_dotenv()

    if identity.rc_smoke:
        try:
            data_dir()
        except app_environment.EnvironmentIdentityError as error:
            _DATA_ROOT_ERROR = str(error)
            ACCOUNT_TOKEN = ""
            return
    _DATA_ROOT_ERROR = ""

    settings = _read_settings()
    if is_frozen():
        OPENAI_API_KEY = ""
    else:
        OPENAI_API_KEY = str(
            os.getenv("OPENAI_API_KEY")
            or os.getenv("vocab_teacher_key")
            or ""
        ).strip()
    OPENAI_MODEL = str(
        settings.get("openai_model") or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
    ).strip()
    base_url = str(settings.get("openai_base_url") or os.getenv("OPENAI_BASE_URL") or "").strip()
    OPENAI_BASE_URL = base_url or None
    ACCOUNT_SERVER_URL = (
        bundled_account_server()
        or str(os.getenv("ACCOUNT_SERVER_URL") or "").strip()
        or "http://127.0.0.1:8765"
    )
    token = str(settings.get("account_token") or "").strip()
    # Staging/dev must never adopt a production (or other-env) session token.
    if token and not app_environment.settings_token_compatible(settings, identity):
        token = ""
    ACCOUNT_TOKEN = token


def ai_is_configured() -> bool:
    """Có cách gọi AI: key trên máy dev, hoặc phiên đăng nhập của người học."""
    if uses_account_server():
        return True
    return looks_like_api_key(OPENAI_API_KEY)


def is_ready() -> bool:
    """Bản cài đặt cần đã đăng nhập. Máy dev cần key trong .env.

    Emergency-credential enrollment is separate. A missing local emergency
    code must not block account setup, and it must not count as ready for
    screen lock.
    """
    if is_frozen():
        return bool(ACCOUNT_TOKEN)
    return looks_like_api_key(OPENAI_API_KEY) or bool(ACCOUNT_TOKEN)


reload()
