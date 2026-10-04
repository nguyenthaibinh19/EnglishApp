"""Kho từ vựng của ngôn ngữ đang học.

Định dạng canonical (Phase 14 + 15A):
    {
      "id": "b3db8f73-...",
      "word": "de fiets",
      "meaning": "xe đạp",
      "alternatives": ["fiets"],
      "examples": [{"text": "...", "meaning": "..."}],
      "pronunciation": {"ipa": "..."},
      "forms": {"plural": "..."},
      "note": "...",
      "part_of_speech": "noun"
    }

Legacy ``vi`` / ``alt`` / ``type`` / ``nl`` / ``en`` / ``example`` vẫn đọc được
và được ghi lại thành canonical khi load (idempotent).
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
from vocabulary_model import (
    entry_meaning,
    needs_schema_migration,
    normalize_alternatives,
    normalize_entry_dict,
    normalize_examples,
    normalize_forms,
    normalize_part_of_speech,
    normalize_pronunciation,
)


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
            if needs_schema_migration(item) or not entry_id(item):
                self._needs_migration = True
            normalized = normalize_entry_dict(item, assign_id=False)
            if normalized is None:
                continue
            if not entry_id(normalized):
                self._needs_migration = True
            self.vocab.append(normalized)

        # Lexical schema rewrite before identity sibling migration.
        if self._needs_migration:
            self.vocab, _ = assign_missing_ids(self.vocab)
            # Ensure every row is fully canonical before save.
            cleaned = []
            for item in self.vocab:
                row = normalize_entry_dict(item, assign_id=True)
                if row:
                    cleaned.append(row)
            self.vocab = cleaned
            if not self._save_atomic():
                # Keep in-memory canonical rows; do not claim disk migrated.
                self.vocab, _ = assign_missing_ids(
                    [normalize_entry_dict(x, assign_id=True) or x for x in self.vocab]
                )
                return
            self._needs_migration = False

        # Assign IDs + migrate sibling progress/attempts once (idempotent).
        try:
            migrated = ensure_language_identity(
                self.filename, vocab_entries=self.vocab
            )
            if migrated and len(migrated) == len(self.vocab):
                for index, source in enumerate(migrated):
                    vid = entry_id(source)
                    if vid:
                        self.vocab[index]["id"] = vid
            else:
                self.vocab, id_changed = assign_missing_ids(self.vocab)
                if id_changed:
                    self.save()
        except OSError as e:
            print("Migration identity thất bại — giữ file gốc:", e)
            self.vocab, _ = assign_missing_ids(self.vocab)
            return

    def _save_atomic(self) -> bool:
        tmp = self.filename + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.vocab, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.filename)
            return True
        except OSError as e:
            print("Không ghi được vocab.json:", e)
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except OSError:
                pass
            return False

    def save(self):
        self._save_atomic()

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

    def add(self, word: str, meaning: str = None, **extra) -> bool:
        """Add a word. ``meaning`` is canonical; legacy kwarg ``vi`` accepted."""
        if meaning is None and "vi" in extra:
            meaning = extra.pop("vi")
        word = (word or "").strip()
        meaning = (meaning or "").strip()
        if not word or not meaning:
            return False
        if self.index_of(word) is not None:
            return False

        payload = {
            "id": new_vocab_id(),
            "word": word,
            "meaning": meaning,
        }
        payload.update(self._optional_from_extra(extra))
        entry = normalize_entry_dict(payload, assign_id=True)
        if entry is None:
            return False
        self.vocab.append(entry)
        self.save()
        return True

    def update(self, index: int, word: str, meaning: str = None, **extra) -> bool:
        if not (0 <= index < len(self.vocab)):
            return False
        if meaning is None and "vi" in extra:
            meaning = extra.pop("vi")
        word = (word or "").strip()
        meaning = (meaning or "").strip()
        if not word or not meaning:
            return False

        existing_id = entry_id(self.vocab[index])
        payload = dict(self.vocab[index])
        payload["word"] = word
        payload["meaning"] = meaning
        if existing_id:
            payload["id"] = existing_id
        # Clear legacy keys so save stays canonical.
        payload.pop("vi", None)
        payload.pop("alt", None)
        payload.pop("type", None)
        payload.pop("nl", None)
        payload.pop("en", None)

        optionals = self._optional_from_extra(
            extra, clearing=True, existing=self.vocab[index]
        )
        for field_name in (
            "alternatives",
            "examples",
            "note",
            "part_of_speech",
            "pronunciation",
            "forms",
        ):
            if field_name in optionals:
                if optionals[field_name]:
                    payload[field_name] = optionals[field_name]
                else:
                    payload.pop(field_name, None)
            elif field_name in extra and not extra[field_name]:
                payload.pop(field_name, None)
        # Never keep legacy single-string example after update.
        payload.pop("example", None)

        # Support legacy kw names in extra for call sites still using alt/type/example.
        entry = normalize_entry_dict(payload, assign_id=True)
        if entry is None:
            return False
        if existing_id:
            entry["id"] = existing_id
        self.vocab[index] = entry
        self.save()
        return True

    def _optional_from_extra(
        self,
        extra: dict,
        clearing: bool = False,
        existing: dict = None,
    ) -> dict:
        out = {}
        if not extra:
            return out
        if "alternatives" in extra or "alt" in extra:
            alts = normalize_alternatives(
                extra["alternatives"] if "alternatives" in extra else extra.get("alt")
            )
            if alts or clearing:
                out["alternatives"] = alts
        if "examples" in extra or "example" in extra:
            if "examples" in extra:
                examples = normalize_examples(extra.get("examples"))
            else:
                # Legacy single-field editors pass ``example`` only. Preserve
                # additional structured examples that the UI cannot edit yet.
                examples = self._merge_legacy_example_edit(
                    existing if isinstance(existing, dict) else {},
                    extra.get("example"),
                )
            if examples or clearing:
                out["examples"] = [item.to_storage_dict() for item in examples]
        if "note" in extra:
            text = str(extra.get("note") or "").strip()
            if text or clearing:
                out["note"] = text
        if "part_of_speech" in extra or "type" in extra:
            pos = str(extra.get("part_of_speech") or "").strip()
            if not pos and "type" in extra:
                pos = normalize_part_of_speech(extra.get("type"))
            if pos or clearing:
                out["part_of_speech"] = pos
        if "pronunciation" in extra:
            pronunciation = normalize_pronunciation(extra.get("pronunciation"))
            data = pronunciation.to_storage_dict()
            if data or clearing:
                out["pronunciation"] = data or {}
        if "forms" in extra:
            forms = normalize_forms(extra.get("forms"))
            data = forms.to_storage_dict()
            if data or clearing:
                out["forms"] = data or {}
        return out

    @staticmethod
    def _merge_legacy_example_edit(existing_entry: dict, example_value) -> list:
        """Update first example text from legacy editor without dropping the rest."""
        from vocabulary_model import VocabularyExample

        existing = normalize_examples(existing_entry.get("examples"))
        if not existing and "example" in existing_entry:
            existing = normalize_examples(existing_entry.get("example"))
        new_text = str(example_value or "").strip()
        if not existing:
            return normalize_examples(new_text)
        rest = existing[1:]
        first_meaning = existing[0].meaning
        if new_text:
            return [VocabularyExample(text=new_text, meaning=first_meaning), *rest]
        return list(rest)

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
        return [
            f"{strip_tags(e['word'])} — {entry_meaning(e)}" for e in self.vocab
        ]


class ReadOnlyVocabView:
    """In-memory, read-only vocabulary for quiz-only sessions.

    Preserves canonical fields + ``id`` for Progress/Attempt recording.
    """

    def __init__(self, entries):
        self.filename = None
        self.vocab = []
        for item in entries or []:
            if not isinstance(item, dict):
                continue
            normalized = normalize_entry_dict(item, assign_id=False)
            if normalized is None:
                continue
            # Keep existing id when present; do not invent ids for ephemeral views
            # unless the source already had one (Practice Mistakes copies include id).
            self.vocab.append(normalized)

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
        return [
            f"{strip_tags(e['word'])} — {entry_meaning(e)}" for e in self.vocab
        ]

    def save(self):
        return None

    def add(self, word: str, meaning: str = None, **extra) -> bool:
        return False

    def update(self, index: int, word: str, meaning: str = None, **extra) -> bool:
        return False

    def delete(self, index: int) -> bool:
        return False
