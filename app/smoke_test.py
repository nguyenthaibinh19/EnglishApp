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
import languages

failures = []


def check(label, condition, detail=""):
    status = "ok  " if condition else "FAIL"
    if not condition:
        failures.append(f"{label} {detail}")
    print(f"[{status}] {label}{(' - ' + detail) if detail and not condition else ''}")


# ---------- Registry ngôn ngữ học ----------

EXPECTED_CODES = ["nl", "en", "fr", "de", "es", "it", "pt"]
check("registry đủ 7 mã học", languages.codes() == EXPECTED_CODES)
check("default study code vẫn là nl", languages.default_study_code() == "nl")
check("get_language('fr') trả về StudyLanguage", languages.get_language("fr").code == "fr")
check("get_language mã lạ là None", languages.get_language("xx") is None)
check("is_supported_language từ chối mã lạ", not languages.is_supported_language("xx"))
check(
    "resolve_language mã lạ fallback default",
    languages.resolve_language("xx").code == languages.default_study_code(),
)
check(
    "get() mã lạ vẫn trả profile default (tương thích)",
    languages.get("xx")["name_en"] == languages.default_language().name_en,
)
nl = languages.get_language("nl")
check("nl articles còn de/het/een", "de" in nl.articles and "het" in nl.articles)
fr = languages.get_language("fr")
check("fr elisions còn l'", "l'" in fr.elisions)
check("registry không trộn native vi", "vi" not in languages.codes())
import config as _config
check("native_code tách khỏi study codes", _config.native_code() in ("vi", "en"))
check(
    "LANGUAGES mapping cũ còn label",
    languages.LANGUAGES["de"]["label"] == languages.get_language("de").label,
)


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


# ---------- Scheduler (tách khỏi persistence) ----------

import copy
import scheduler as vocab_scheduler

# Từ mới / chưa thấy
unseen = {"seen": 0, "correct": 0, "wrong": 0, "streak": 0, "last_seen": None}
# Hay sai
weak = {"seen": 10, "correct": 2, "wrong": 8, "streak": 0, "last_seen": "2026-10-01T12:00:00"}
# Đã thuộc (streak cao)
strong = {"seen": 10, "correct": 10, "wrong": 0, "streak": 5, "last_seen": "2026-10-01T12:00:00"}
# Cùng accuracy/streak nhưng lâu chưa gặp
stale = {"seen": 10, "correct": 10, "wrong": 0, "streak": 5, "last_seen": "2026-09-01T12:00:00"}
today = __import__("datetime").date(2026, 10, 1)

check(
    "scheduler: từ mới trọng số cao hơn từ thuộc",
    vocab_scheduler.compute_weight(unseen, today) > vocab_scheduler.compute_weight(strong, today),
)
check(
    "scheduler: từ hay sai trọng số cao hơn từ thuộc",
    vocab_scheduler.compute_weight(weak, today) > vocab_scheduler.compute_weight(strong, today),
)
check(
    "scheduler: streak cao làm giảm trọng số",
    vocab_scheduler.compute_weight(
        {"seen": 5, "correct": 5, "wrong": 0, "streak": 5, "last_seen": None}, today
    )
    < vocab_scheduler.compute_weight(
        {"seen": 5, "correct": 5, "wrong": 0, "streak": 0, "last_seen": None}, today
    ),
)
check(
    "scheduler: từ lâu chưa gặp tăng lại trọng số",
    vocab_scheduler.compute_weight(stale, today) > vocab_scheduler.compute_weight(strong, today),
)

# Chọn từ không được ghi progress
sched_dir = tempfile.mkdtemp()
sched_vocab = os.path.join(sched_dir, "vocab.json")
sched_progress = os.path.join(sched_dir, "progress.json")
with open(sched_vocab, "w", encoding="utf-8") as f:
    f.write(
        '[{"word": "alpha", "vi": "a"}, {"word": "beta", "vi": "b"}, '
        '{"word": "gamma", "vi": "c"}]'
    )
with open(sched_progress, "w", encoding="utf-8") as f:
    f.write(
        '{"version": 2, "words": {"alpha": {"seen": 4, "correct": 4, "wrong": 0, '
        '"streak": 4, "last_seen": "2026-10-01T10:00:00"}}, "days": {}}'
    )
before_progress = open(sched_progress, encoding="utf-8").read()
sched_store = VocabStore(sched_vocab)
sched_prog = Progress(sched_progress)
snapshot = copy.deepcopy(sched_prog.data)
chooser = vocab_scheduler.VocabScheduler(sched_prog, rng=random.Random(1))
picked = chooser.pick_next(sched_store, answered=0)
check("scheduler: pick_next trả về entry", picked is not None and "word" in picked)
check("scheduler: pick_next không đổi data trong bộ nhớ", sched_prog.data == snapshot)
check(
    "scheduler: pick_next không ghi đĩa",
    open(sched_progress, encoding="utf-8").read() == before_progress,
)
# Progress.weight vẫn tương thích và trùng compute_weight
check(
    "progress.weight ủy thác cùng công thức scheduler",
    abs(
        sched_prog.weight("alpha")
        - vocab_scheduler.compute_weight(sched_prog.word_stats("alpha"))
    )
    < 1e-9,
)
# File progress cũ (version 2) vẫn load
legacy = Progress(sched_progress)
check("progress.json cũ vẫn load được", legacy.data.get("version") == 2)
check("progress.json cũ còn thống kê từ", "alpha" in legacy.data["words"])


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

import tempfile
import account_store
import updater

check("bản mới hơn thì cần cập nhật", updater.is_newer("v1.4.0", "1.3.4"))
check("cùng bản thì không cập nhật", not updater.is_newer("v1.3.4", "1.3.4"))
check("bản cũ hơn thì không cập nhật", not updater.is_newer("v1.3.3", "1.3.4"))
url, size, kind = updater._pick_asset(
    {
        "assets": [
            {"name": "langstudyguard.exe", "browser_download_url": "https://example/e", "size": 10},
            {"name": "langstudyguard.zip", "browser_download_url": "https://example/z", "size": 9},
        ]
    }
)
check("ưu tiên tải zip hơn exe", kind == "zip" and url.endswith("/z"))

folder = tempfile.mkdtemp()
account_store.add_user("hocvien", "matkhau", folder)
token = account_store.login("hocvien", "matkhau", folder)
check("đăng nhập đúng mật khẩu", account_store.user_for_token(token, folder)["username"] == "hocvien")
try:
    account_store.login("hocvien", "sai", folder)
    check("từ chối mật khẩu sai", False)
except ValueError:
    check("từ chối mật khẩu sai", True)
account_store.set_active("hocvien", False, folder)
check("khóa tài khoản thì hết phiên", account_store.user_for_token(token, folder) is None)
account_store.set_active("hocvien", True, folder)
account_store.set_password("hocvien", "matkhau2", folder)
try:
    account_store.login("hocvien", "matkhau", folder)
    check("mật khẩu cũ không còn dùng", False)
except ValueError:
    check("mật khẩu cũ không còn dùng", True)
check("đăng nhập bằng mật khẩu mới", account_store.login("hocvien", "matkhau2", folder) != "")

# ---------- AI provider boundary (không gọi mạng / OpenAI) ----------

import ai_teacher
from ai.base import AIError, AIProvider, GradeRequest, GradeResult, ReadingRequest
from ai.service import AIService, set_service


class FakeProvider(AIProvider):
    def __init__(self):
        self.grade_calls = []
        self.reading_calls = []

    def grade_answer(self, request: GradeRequest) -> GradeResult:
        self.grade_calls.append(request)
        return GradeResult(
            is_correct_usage=True,
            score=0.9,
            feedback_vi=f"ok:{request.study_language.code}",
            corrected_sentence=request.user_sentence,
            suggested_sentence="sample",
        )

    def generate_reading(self, request: ReadingRequest) -> dict:
        self.reading_calls.append(request)
        return {
            "title": "Fake",
            "level": request.level,
            "passage": "Hallo.",
            "source": "ai",
            "target_words": ["hallo"],
            "groups": [],
            "study_code": request.study_language.code if request.study_language else "",
        }


fake = FakeProvider()
set_service(AIService(provider=fake))
try:
    graded = ai_teacher.check_sentence(
        "fiets",
        "Ik heb een fiets.",
        "xe đạp",
        profile={"code": "nl", "name_en": "Dutch", "name_vi": "tiếng Hà Lan", "articles": (), "elisions": ()},
        native_label="Tiếng Việt",
        level="A2",
    )
    check("facade chấm câu qua provider", graded["is_correct_usage"] is True)
    check("facade không cần OpenAI SDK", graded["feedback_vi"].startswith("ok:"))
    check("StudyLanguage tới AI layer", fake.grade_calls[0].study_language.code == "nl")
    check(
        "grade request mang câu học viên",
        fake.grade_calls[0].user_sentence == "Ik heb een fiets.",
    )

    reading = ai_teacher.generate_reading(
        [{"word": "hallo", "vi": "xin chào"}],
        profile={"code": "de"},
        native_label="English",
        level="A2",
        passage_words=80,
    )
    check("facade sinh bài đọc qua provider", reading.get("source") == "ai")
    check("reading nhận StudyLanguage de", fake.reading_calls[0].study_language.code == "de")
    check(
        "thay provider không đụng quiz/reading business API",
        callable(ai_teacher.check_sentence) and callable(ai_teacher.generate_reading),
    )
    check("AITeacherError alias AIError", ai_teacher.AITeacherError is AIError)
finally:
    set_service(None)

print()
if failures:
    print(f"{len(failures)} kiểm tra thất bại:")
    for item in failures:
        print(" -", item)
    raise SystemExit(1)
print("Tất cả kiểm tra đều đạt.")
