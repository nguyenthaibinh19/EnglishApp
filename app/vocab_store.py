"""Kho từ vựng của ngôn ngữ đang học.

Định dạng mỗi mục:
    {
      "id": "b3db8f73-...",   # ổn định (UUID), Phase 13
      "word": "de fiets",     # bắt buộc - từ tiếng đang học
      "vi": "xe đạp",         # bắt buộc - nghĩa
      "alt": ["fiets"],       # tùy chọn
      "example": "..."
    }

File cũ dùng khóa "nl" hoặc "en" vẫn đọc được và được ghi lại thành "word".
Thiếu ``id`` được gán khi load (migration idempotent).
"""

import json
import os

import config
from text_utils import entry_word, normalize, strip_tags
from vocab_identity import (
    assign_missing_ids,
    ensure_language_identity,
    entry_id,
    is_vocab_id,
    new_vocab_id,
)

# Các trường tùy chọn được giữ nguyên khi lưu lại file.
OPTIONAL_FIELDS = ("alt", "example", "note", "type")


class VocabStore:
    def __init__(self, filename: str = None):
        if filename is None:
            config.ensure_language_data()
            filename = config.vocab_path()
        self.filename = filename
        self.vocab = []
        self._needs_migration = False
        self.load()

    # ---------- Đọc / ghi ----------

    def load(self):
        self.vocab = []
        self._needs_migration = False

        if not os.path.exists(self.filename):
            return
        try:
            with open(self.filename, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print("Không đọc được vocab.json:", e)
            return

        if not isinstance(data, list):
            return

        for item in data:
            if not isinstance(item, dict):
                continue
            word = entry_word(item)
            meaning = item.get("vi")
            if not word or not meaning:
                continue
            if "word" not in item:
                self._needs_migration = True

            entry = {"word": str(word).strip(), "vi": str(meaning).strip()}
            vid = entry_id(item)
            if vid:
                entry["id"] = vid
            else:
                self._needs_migration = True
            for field in OPTIONAL_FIELDS:
                if item.get(field):
                    entry[field] = item[field]
            self.vocab.append(entry)

        # Assign IDs + migrate sibling progress/attempts once (idempotent).
        try:
            migrated = ensure_language_identity(
                self.filename, vocab_entries=self.vocab
            )
            # Reload IDs from migration result (same order).
            if migrated and len(migrated) == len(self.vocab):
                for index, source in enumerate(migrated):
                    vid = entry_id(source)
                    if vid:
                        self.vocab[index]["id"] = vid
            elif self._needs_migration:
                self.vocab, _ = assign_missing_ids(self.vocab)
                self.save()
        except OSError as e:
            print("Migration identity thất bại — giữ file gốc:", e)
            # Still ensure in-memory IDs so the session can run; do not save half state.
            self.vocab, _ = assign_missing_ids(self.vocab)
            return

        if self._needs_migration:
            # Legacy nl/en → word rewrite already covered by ensure when IDs missing;
            # if only key rename, persist cleaned entries.
            self.save()
            self._needs_migration = False

    def save(self):
        tmp = self.filename + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.vocab, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.filename)
        except OSError as e:
            print("Không ghi được vocab.json:", e)

    # ---------- Truy vấn ----------

    def all(self) -> list:
        return self.vocab

    def count(self) -> int:
        return len(self.vocab)

    def get(self, index: int):
        if 0 <= index < len(self.vocab):
            return self.vocab[index]
        return None

    def get_by_id(self, vocab_id: str):
        target = str(vocab_id or "").strip()
        if not target:
            return None
        for entry in self.vocab:
            if entry_id(entry) == target:
                return entry
        return None

    def index_of_id(self, vocab_id: str):
        target = str(vocab_id or "").strip()
        if not target:
            return None
        for i, entry in enumerate(self.vocab):
            if entry_id(entry) == target:
                return i
        return None

    def index_of(self, word: str):
        """Tìm vị trí của một từ theo dạng đã chuẩn hóa (duplicate policy)."""
        target = normalize(word)
        for i, entry in enumerate(self.vocab):
            if normalize(entry["word"]) == target:
                return i
        return None

    def find_duplicates(self) -> list:
        seen = {}
        dups = []
        for entry in self.vocab:
            key = normalize(entry["word"])
            if key in seen:
                dups.append(entry["word"])
            seen[key] = True
        return dups

    # ---------- Thêm / sửa / xóa ----------

    def add(self, word: str, vi: str, **extra) -> bool:
        word, vi = word.strip(), vi.strip()
        if not word or not vi:
            return False
        if self.index_of(word) is not None:
            return False

        entry = {"id": new_vocab_id(), "word": word, "vi": vi}
        for field in OPTIONAL_FIELDS:
            if extra.get(field):
                entry[field] = extra[field]
        self.vocab.append(entry)
        self.save()
        return True

    def update(self, index: int, word: str, vi: str, **extra) -> bool:
        if not (0 <= index < len(self.vocab)):
            return False
        word, vi = word.strip(), vi.strip()
        if not word or not vi:
            return False

        entry = dict(self.vocab[index])
        # Preserve stable ID — never regenerate on edit/rename.
        existing_id = entry_id(entry)
        entry["word"] = word
        entry["vi"] = vi
        if existing_id:
            entry["id"] = existing_id
        else:
            entry["id"] = new_vocab_id()
        for field in OPTIONAL_FIELDS:
            if field in extra:
                if extra[field]:
                    entry[field] = extra[field]
                else:
                    entry.pop(field, None)
        self.vocab[index] = entry
        self.save()
        return True

    def delete(self, index: int) -> bool:
        if not (0 <= index < len(self.vocab)):
            return False
        self.vocab.pop(index)
        self.save()
        return True

    # ---------- Tiện ích cho phần reading ----------

    def entries_for_keys(self, keys) -> list:
        """Lấy mục theo vocab_id hoặc normalized word (progress day keys)."""
        wanted_ids = set()
        wanted_words = set()
        for key in keys or ():
            text = str(key)
            if is_vocab_id(text):
                wanted_ids.add(text)
            else:
                wanted_words.add(normalize(text))
        result = []
        for entry in self.vocab:
            vid = entry_id(entry)
            if vid and vid in wanted_ids:
                result.append(entry)
            elif normalize(entry["word"]) in wanted_words:
                result.append(entry)
        return result

    def display_list(self) -> list:
        return [f"{strip_tags(e['word'])} — {e['vi']}" for e in self.vocab]


class ReadOnlyVocabView:
    """In-memory, read-only vocabulary for quiz-only sessions.

    QuizEngine/VocabScheduler only need ``count`` / ``get`` / ``all``.
    Mutating methods are no-ops that refuse to touch any vocab.json.
    Preserves ``id`` for Progress/Attempt recording.
    """

    def __init__(self, entries):
        self.filename = None
        self.vocab = []
        for item in entries or []:
            if not isinstance(item, dict):
                continue
            word = entry_word(item)
            meaning = item.get("vi")
            if not word or not meaning:
                continue
            entry = {"word": str(word).strip(), "vi": str(meaning).strip()}
            vid = entry_id(item)
            if vid:
                entry["id"] = vid
            for field in OPTIONAL_FIELDS:
                if item.get(field):
                    entry[field] = item[field]
            self.vocab.append(entry)

    def all(self) -> list:
        return self.vocab

    def count(self) -> int:
        return len(self.vocab)

    def get(self, index: int):
        if 0 <= index < len(self.vocab):
            return self.vocab[index]
        return None

    def get_by_id(self, vocab_id: str):
        target = str(vocab_id or "").strip()
        if not target:
            return None
        for entry in self.vocab:
            if entry_id(entry) == target:
                return entry
        return None

    def index_of(self, word: str):
        target = normalize(word)
        for i, entry in enumerate(self.vocab):
            if normalize(entry["word"]) == target:
                return i
        return None

    def entries_for_keys(self, keys) -> list:
        wanted_ids = set()
        wanted_words = set()
        for key in keys or ():
            text = str(key)
            if is_vocab_id(text):
                wanted_ids.add(text)
            else:
                wanted_words.add(normalize(text))
        return [
            e
            for e in self.vocab
            if (entry_id(e) and entry_id(e) in wanted_ids)
            or normalize(e["word"]) in wanted_words
        ]

    def display_list(self) -> list:
        return [f"{strip_tags(e['word'])} — {e['vi']}" for e in self.vocab]

    def save(self):
        return None

    def add(self, word: str, vi: str, **extra) -> bool:
        return False

    def update(self, index: int, word: str, vi: str, **extra) -> bool:
        return False

    def delete(self, index: int) -> bool:
        return False
