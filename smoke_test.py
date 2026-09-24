"""Kiểm tra nhanh phần logic (không cần Tkinter, không gọi AI).

Chạy: python smoke_test.py
"""

import os
import random
import tempfile

import text_utils
from progress import Progress
from quiz_engine import QuizEngine
from reading_schema import count_questions, normalize_test
from vocab_store import VocabStore

failures = []


def check(label, condition, detail=""):
    status = "ok  " if condition else "FAIL"
    if not condition:
        failures.append(f"{label} {detail}")
    print(f"[{status}] {label}{(' - ' + detail) if detail and not condition else ''}")


# ---------- So khớp đáp án ----------

entry = {"nl": "de fiets", "vi": "xe đạp", "alt": ["rijwiel"]}
check("đúng nguyên văn", text_utils.match_answer("de fiets", entry)[0] == "exact")
check("bỏ mạo từ vẫn đúng", text_utils.match_answer("fiets", entry)[0] == "exact")
check("không phân biệt hoa thường", text_utils.match_answer("  De Fiets ", entry)[0] == "exact")
check("chấp nhận từ đồng nghĩa trong alt", text_utils.match_answer("rijwiel", entry)[0] == "exact")
check("gõ nhầm 1 ký tự -> near", text_utils.match_answer("de fietz", entry)[0] == "near")
check("từ khác hẳn -> wrong", text_utils.match_answer("het huis", entry)[0] == "wrong")

accent = {"nl": "één", "vi": "một"}
check("thiếu dấu -> near", text_utils.match_answer("een", accent)[0] == "near")

tagged = {"nl": "lopen (ww)", "vi": "đi bộ"}
check("bỏ tag loại từ", text_utils.match_answer("lopen", tagged)[0] == "exact")

short = {"nl": "kat", "vi": "con mèo"}
check("từ ngắn không tha lỗi gõ nhầm", text_utils.match_answer("kan", short)[0] == "wrong")

french = {"word": "la maison", "vi": "ngôi nhà"}
check(
    "bỏ mạo từ tiếng Pháp",
    text_utils.match_answer("maison", french, articles=("la", "le"))[0] == "exact",
)
school = {"word": "l'école", "vi": "trường học"}
check(
    "bỏ mạo từ dính l'",
    text_utils.match_answer("ecole", school, elisions=("l'",))[0] in ("exact", "near"),
)


# ---------- Kho từ + tiến độ + engine ----------

tmp_dir = tempfile.mkdtemp()
vocab_path = os.path.join(tmp_dir, "vocab.json")
progress_path = os.path.join(tmp_dir, "progress.json")

with open(vocab_path, "w", encoding="utf-8") as f:
    # Cố tình dùng định dạng cũ "en" để kiểm tra việc tự migrate.
    f.write('[{"en": "de fiets", "vi": "xe đạp"}, {"en": "het huis", "vi": "ngôi nhà"}]')

store = VocabStore(vocab_path)
check("đọc được file định dạng cũ", store.count() == 2)
check("đã đổi khóa en -> word", "word" in store.get(0) and "en" not in store.get(0))

store.add("de trein", "tàu hỏa")
check("thêm từ mới", store.count() == 3)
check("chặn thêm trùng", store.add("DE TREIN", "tàu") is False)
check("đọc lại từ đĩa giữ nguyên", VocabStore(vocab_path).count() == 3)

progress = Progress(progress_path)
engine = QuizEngine(store, progress, target=3, rng=random.Random(7))

asked = engine.pick_next()
check("bốc được câu hỏi", asked is not None)

result = engine.submit("sai bét")
check("trả lời sai bị chấm wrong", result.verdict == "wrong")
check("sai không tăng điểm", result.correct_count == 0)

for _ in range(6):
    current = engine.pick_next()
    engine.submit(current["word"])
    if engine.finished:
        break
check("trả lời đúng đủ số câu thì kết thúc", engine.finished, str(engine.session_stats()))

check("ghi nhận từ đã học hôm nay", len(progress.words_studied_today()) >= 1)
check("từ mới có trọng số cao hơn từ đã thuộc",
      progress.weight("chưa từng học") > progress.weight(store.get(0)["word"]))


# ---------- Chuẩn hóa bài đọc ----------

raw_test = {
    "title": "Op de markt",
    "passage": "Ik ga elke zaterdag naar de markt.\n\nDe markt is altijd druk.",
    "question_groups": [
        {
            "type": "multiple_choice_single",
            "instructions": "Chọn đáp án đúng.",
            "questions": [
                {
                    "number": 1,
                    "prompt": "Wanneer gaat hij naar de markt?",
                    "options": [
                        {"key": "A", "text": "Op maandag"},
                        {"key": "B", "text": "Op zaterdag"},
                    ],
                    "answer": "B",
                    "explanation_vi": "Câu đầu tiên nói rõ 'elke zaterdag'.",
                }
            ],
        },
        {
            "type": "true_false_notgiven",
            "questions": [{"number": 2, "prompt": "De markt is rustig.", "answer": "FALSE"}],
        },
        {
            "type": "vocab_matching",
            "prompts": [{"number": 3, "text": "druk"}],
            "options": [{"code": "A", "text": "bận rộn"}, {"code": "B", "text": "rẻ"}],
            "answers": ["A"],
        },
        {"type": "khong_ho_tro", "questions": []},
    ],
}

test = normalize_test(raw_test)
check("bỏ qua nhóm câu hỏi không hỗ trợ", len(test["groups"]) == 3)
check("đếm đúng tổng số câu", count_questions(test) == 3)
check("tự sinh lựa chọn cho True/False/Not Given",
      len(test["groups"][1]["questions"][0]["options"]) == 3)
check("giữ lại giải thích", test["groups"][0]["questions"][0]["explanation"].startswith("Câu đầu"))

legacy = {
    "passage": "x",
    "question_groups": [
        {
            "type": "matching_heading",
            "sections": ["Section A", "Section B"],
            "headings": [{"code": "i", "text": "Eerste"}, {"code": "ii", "text": "Tweede"}],
            "answers": ["ii", "i"],
            "number_range": [5, 6],
        }
    ],
}
legacy_test = normalize_test(legacy)
check("đọc được AnswerKey.json kiểu cũ", legacy_test["groups"][0]["kind"] == "matching")
check("giữ số thứ tự câu hỏi cũ", legacy_test["groups"][0]["prompts"][0]["number"] == 5)

import os
import sqlite3
import tempfile

import dictionary

keys = dictionary.lookup_keys("de fietsen", "nl")
check("tra được dạng gốc sau mạo từ và đuôi", "fiets" in keys, str(keys))
check("tách nghĩa trong từ điển", dictionary.split_glosses(" bicycle | bike | bicycle ") == ["bicycle", "bike"])
sample = {
    "responseData": {"translatedText": "xe đạp"},
    "matches": [
        {"segment": "fiets", "translation": "xe đạp"},
        {"segment": "fiets", "translation": "xe đạp"},
        {"segment": "auto", "translation": "ô tô"},
    ],
}
check(
    "đọc kết quả từ điển trực tuyến",
    dictionary.glosses_from_mymemory(sample, "fiets") == ["xe đạp"],
)

fd, dict_path = tempfile.mkstemp(suffix=".sqlite3")
os.close(fd)
connection = sqlite3.connect(dict_path)
connection.execute("CREATE TABLE simple_translation(written_rep TEXT, trans_list, max_score, rel_importance)")
connection.execute(
    "INSERT INTO simple_translation VALUES (?, ?, ?, ?)",
    ("fiets", "bicycle | bike", 1, 1),
)
connection.commit()
connection.close()
check(
    "tra file từ điển theo từ đã chia",
    dictionary.lookup_wikdict(dict_path, "fietsen", "nl")[:1] == ["bicycle"],
)
os.remove(dict_path)


passage = "De fiets is rood. Het huis is groot!"
check("dịch đúng câu chứa từ", text_utils.sentence_around(passage, passage.index("huis")) == "Het huis is groot!")
check("dịch câu đầu", text_utils.sentence_around(passage, 3) == "De fiets is rood.")

print()
if failures:
    print(f"{len(failures)} kiểm tra thất bại:")
    for item in failures:
        print(" -", item)
    raise SystemExit(1)
print("Tất cả kiểm tra đều đạt.")
