"""Từ điển theo từng cặp ngôn ngữ. Không tải sẵn mọi tiếng.

Tiếng Anh: một file SQLite WikDict (CC BY-SA) cho đúng ngôn ngữ đang học.
Tiếng Việt: WikDict không có bản Việt, nên tra trực tuyến rồi lưu kết quả
trên máy. Lần sau cùng một từ không cần gọi mạng nữa.
"""

import json
import os
import sqlite3
import urllib.error
import urllib.parse
import urllib.request

import languages
from text_utils import fold_accents, normalize, without_article, without_elision

WIKIDICT_VERSION = "2_2026-06"
_USER_AGENT = "LanguageGuard/1.0"

# Đuôi hay gặp khi từ trong bài đã bị chia. Tra dạng gốc nếu dạng đủ không có.
_SUFFIXES = {
    "nl": ("en", "e", "s", "t"),
    "en": ("ing", "es", "ed", "er", "s"),
    "fr": ("ent", "es", "e", "s"),
    "de": ("en", "er", "e", "n", "s"),
    "es": ("es", "s"),
    "it": ("es", "i", "e", "o", "a"),
    "pt": ("es", "s"),
}


class DictionaryError(Exception):
    pass


def dict_dir() -> str:
    import config

    path = os.path.join(config.data_dir(), "dicts")
    os.makedirs(path, exist_ok=True)
    return path


def pack_path(source: str, native: str) -> str:
    if native == "en":
        return os.path.join(dict_dir(), f"{source}-en.sqlite3")
    return os.path.join(dict_dir(), f"{source}-vi.sqlite")


def probe_word(source: str) -> str:
    profile = languages.get(source)
    text = normalize(profile.get("sample") or "")
    text = without_elision(without_article(text, profile.get("articles")), profile.get("elisions"))
    return text.split(" ")[0] if text else ""


def lookup_keys(word: str, source: str) -> list:
    """Các dạng để tra: nguyên từ, bỏ mạo từ, bỏ dấu, rồi mới đến dạng gốc."""
    profile = languages.get(source)
    articles = profile.get("articles") or ()
    elisions = profile.get("elisions") or ()
    forms = []

    def add(value: str):
        value = normalize(value)
        if len(value) < 2 or value in articles:
            return
        if value not in forms:
            forms.append(value)
        folded = fold_accents(value)
        if folded not in forms:
            forms.append(folded)

    base = normalize(word)
    add(base)
    add(without_article(base, articles))
    add(without_elision(base, elisions))
    bare = without_elision(without_article(base, articles), elisions)
    add(bare)

    for form in list(forms):
        for suffix in _SUFFIXES.get(source, ()):
            if form.endswith(suffix) and len(form) - len(suffix) >= 3:
                add(form[: -len(suffix)])
    return forms


def split_glosses(text: str) -> list:
    glosses = []
    for piece in str(text or "").split("|"):
        item = piece.strip()
        if item and item not in glosses:
            glosses.append(item)
    return glosses


def lookup_wikdict(path: str, word: str, source: str) -> list:
    if not path or not os.path.isfile(path):
        return []
    keys = lookup_keys(word, source)
    if not keys:
        return []
    try:
        connection = sqlite3.connect(path)
    except sqlite3.Error as error:
        raise DictionaryError(f"Không mở được từ điển: {error}") from error
    try:
        for key in keys:
            rows = connection.execute(
                "SELECT trans_list FROM simple_translation WHERE written_rep = ? "
                "ORDER BY max_score DESC LIMIT 4",
                (key,),
            ).fetchall()
            glosses = []
            for (trans_list,) in rows:
                for gloss in split_glosses(trans_list):
                    if gloss not in glosses:
                        glosses.append(gloss)
            if glosses:
                return glosses[:6]
    except sqlite3.Error as error:
        raise DictionaryError(f"Không tra được từ điển: {error}") from error
    finally:
        connection.close()
    return []


def is_ready(source: str, native: str) -> bool:
    if source == native:
        return True
    path = pack_path(source, native)
    if not os.path.isfile(path):
        return False
    word = probe_word(source)
    if not word:
        return False
    try:
        if native == "en":
            return bool(lookup_wikdict(path, word, source))
        return bool(_cached_glosses(path, [word]))
    except DictionaryError:
        return False


def install(source: str, native: str, on_progress=None):
    """Tải hoặc kiểm tra gói của một ngôn ngữ. on_progress nhận số từ 0 đến 1."""
    report = on_progress or (lambda _fraction: None)
    if source == native:
        report(1)
        return
    if native == "en":
        _install_wikdict(source, report)
        return
    if native == "vi":
        _install_vietnamese(source, report)
        return
    raise DictionaryError("Chỉ dịch được sang tiếng Việt hoặc tiếng Anh.")


def remove_pack(source: str, native: str):
    path = pack_path(source, native)
    for candidate in (path, path + ".part"):
        if os.path.isfile(candidate):
            try:
                os.remove(candidate)
            except OSError:
                pass


def remove_language(source: str):
    """Xóa mọi gói từ điển của một ngôn ngữ, cả bản tiếng Anh và bản tiếng Việt."""
    for native in ("en", "vi"):
        remove_pack(source, native)


def learner_gloss(word: str, source: str = None) -> str:
    """Nghĩa để hiện cho người học, theo ngôn ngữ gốc đang chọn."""
    import config

    source = source or config.active_code()
    native = config.native_code()
    if not word or source == native:
        return ""
    try:
        glosses = lookup(word, source, native)
    except DictionaryError:
        return ""
    return glosses[0] if glosses else ""


def lookup(word: str, source: str, native: str) -> list:
    """Tra một từ. Tiếng Anh đọc file đã tải. Tiếng Việt dùng bản lưu, thiếu thì gọi mạng."""
    if not word or source == native:
        return []
    keys = lookup_keys(word, source)
    if not keys:
        return []
    if native == "en":
        path = pack_path(source, "en")
        if not os.path.isfile(path):
            raise DictionaryError("Chưa tải từ điển tiếng Anh cho ngôn ngữ này.")
        return lookup_wikdict(path, word, source)
    if native != "vi":
        return []

    path = pack_path(source, "vi")
    cached = _cached_glosses(path, keys)
    if cached:
        return cached
    glosses = _cloud_glosses(keys[0], source, "vi")
    if glosses:
        _store_cache(source, keys[0], glosses)
    return glosses


def _install_wikdict(source: str, report):
    url = (
        "https://download.wikdict.com/dictionaries/sqlite/"
        f"{WIKIDICT_VERSION}/{source}-en.sqlite3"
    )
    destination = pack_path(source, "en")
    temporary = destination + ".part"
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            total = int(response.headers.get("Content-Length") or 0)
            received = 0
            with open(temporary, "wb") as handle:
                while True:
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
                    received += len(chunk)
                    if total:
                        report(min(received / total, 0.9))
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        _discard(temporary)
        raise DictionaryError(f"Không tải được từ điển: {error}") from error

    report(0.92)
    try:
        _index_wikdict(temporary)
        word = probe_word(source)
        if word and not lookup_wikdict(temporary, word, source):
            raise DictionaryError(f"Từ điển đã tải nhưng không tra được từ mẫu “{word}”.")
    except DictionaryError:
        _discard(temporary)
        raise
    except sqlite3.Error as error:
        _discard(temporary)
        raise DictionaryError(f"File từ điển bị lỗi: {error}") from error

    os.replace(temporary, destination)
    report(1)


def _index_wikdict(path: str):
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_simple_rep ON simple_translation(written_rep)"
        )
        connection.commit()
    finally:
        connection.close()


def _install_vietnamese(source: str, report):
    word = probe_word(source)
    if not word:
        raise DictionaryError("Không có từ mẫu để kiểm tra từ điển.")
    report(0.3)
    glosses = _cloud_glosses(word, source, "vi")
    if not glosses:
        raise DictionaryError(f"Không tra được từ mẫu “{word}” sang tiếng Việt.")
    _store_cache(source, word, glosses)
    report(1)


def _cached_glosses(path: str, keys: list) -> list:
    if not path or not os.path.isfile(path) or not keys:
        return []
    connection = None
    try:
        connection = sqlite3.connect(path)
        connection.execute("CREATE TABLE IF NOT EXISTS gloss(word TEXT PRIMARY KEY, gloss TEXT)")
        for key in keys:
            row = connection.execute(
                "SELECT gloss FROM gloss WHERE word = ?", (key,)
            ).fetchone()
            if row and row[0]:
                return split_glosses(row[0])[:6]
    except sqlite3.Error as error:
        raise DictionaryError(f"Không đọc được từ điển đã lưu: {error}") from error
    finally:
        if connection is not None:
            connection.close()
    return []


def _store_cache(source: str, word: str, glosses: list):
    path = pack_path(source, "vi")
    connection = sqlite3.connect(path)
    try:
        connection.execute("CREATE TABLE IF NOT EXISTS gloss(word TEXT PRIMARY KEY, gloss TEXT)")
        connection.execute(
            "INSERT OR REPLACE INTO gloss(word, gloss) VALUES (?, ?)",
            (normalize(word), " | ".join(glosses)),
        )
        connection.commit()
    finally:
        connection.close()


def _cloud_glosses(word: str, source: str, native: str) -> list:
    query = urllib.parse.urlencode({"q": word, "langpair": f"{source}|{native}"})
    url = "https://api.mymemory.translated.net/get?" + query
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as error:
        raise DictionaryError(f"Không tra được từ điển trực tuyến: {error}") from error
    return glosses_from_mymemory(payload, word)


def glosses_from_mymemory(payload: dict, word: str) -> list:
    if not isinstance(payload, dict):
        return []
    translated = str((payload.get("responseData") or {}).get("translatedText") or "").strip()
    if "MYMEMORY WARNING" in translated.upper():
        raise DictionaryError("Hết lượt tra từ điển trực tuyến trong hôm nay. Thử lại sau.")

    glosses = []
    for match in payload.get("matches") or []:
        if not isinstance(match, dict):
            continue
        segment = str(match.get("segment") or "").strip().lower()
        if segment and segment != word.lower():
            continue
        text = str(match.get("translation") or "").strip()
        if _usable_gloss(text, word):
            if text not in glosses:
                glosses.append(text)
    if not glosses and _usable_gloss(translated, word):
        glosses.append(translated)
    return glosses[:6]


def _usable_gloss(text: str, word: str) -> bool:
    if not text or text.lower() == word.lower():
        return False
    return "MYMEMORY WARNING" not in text.upper()


def _discard(path: str):
    if path and os.path.isfile(path):
        try:
            os.remove(path)
        except OSError:
            pass
