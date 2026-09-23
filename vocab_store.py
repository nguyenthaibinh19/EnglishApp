"""Kho từ vựng của ngôn ngữ đang học.

Định dạng mỗi mục:
    {
      "word": "de fiets",        # bắt buộc - từ tiếng đang học (kèm mạo từ nếu là danh từ)
      "vi": "xe đạp",            # bắt buộc - nghĩa tiếng Việt
      "alt": ["fiets"],          # tùy chọn - các cách viết khác cũng tính là đúng
      "example": "Ik ga met de fiets naar school."
    }

File cũ dùng khóa "nl" hoặc "en" vẫn đọc được và được ghi lại thành "word".
"""

import json
import os

import config
from text_utils import entry_word, normalize, strip_tags

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
            for field in OPTIONAL_FIELDS:
                if item.get(field):
                    entry[field] = item[field]
            self.vocab.append(entry)

        # File còn ở định dạng cũ -> ghi lại một lần cho sạch.
        if self._needs_migration:
            self.save()
            self._needs_migration = False

    def save(self):
        tmp = self.filename + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.vocab, f, ensure_ascii=False, indent=2)
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

    def index_of(self, word: str):
        """Tìm vị trí của một từ theo dạng đã chuẩn hóa."""
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

        entry = {"word": word, "vi": vi}
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
        entry["word"] = word
        entry["vi"] = vi
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
        """Lấy các mục theo danh sách từ đã chuẩn hóa (dùng chung với progress.json)."""
        wanted = {normalize(k) for k in keys}
        return [e for e in self.vocab if normalize(e["word"]) in wanted]

    def display_list(self) -> list:
        return [f"{strip_tags(e['word'])} — {e['vi']}" for e in self.vocab]
