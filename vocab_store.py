# vocab_store.py
import json
import os


class VocabStore:
    def __init__(self, filename: str = "vocab.json"):
        # Đảm bảo file nằm cùng thư mục với code
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.filename = os.path.join(base_dir, filename)
        self.vocab = self._load()

    def _load(self):
        if not os.path.exists(self.filename):
            return []
        try:
            with open(self.filename, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            return []

        cleaned = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "en" in item and "vi" in item:
                    cleaned.append(
                        {
                            "en": str(item["en"]),
                            "vi": str(item["vi"]),
                        }
                    )
        return cleaned

    def save(self):
        with open(self.filename, "w", encoding="utf-8") as f:
            json.dump(self.vocab, f, ensure_ascii=False, indent=2)

    # ---------- APIs đơn giản để dùng ở UI ----------

    def all(self):
        return self.vocab

    def count(self) -> int:
        return len(self.vocab)

    def add(self, en: str, vi: str):
        self.vocab.append({"en": en, "vi": vi})
        self.save()

    def update(self, index: int, en: str, vi: str):
        if 0 <= index < len(self.vocab):
            self.vocab[index] = {"en": en, "vi": vi}
            self.save()

    def delete(self, index: int):
        if 0 <= index < len(self.vocab):
            self.vocab.pop(index)
            self.save()
