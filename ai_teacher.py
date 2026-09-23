"""Cầu nối tới OpenAI: chấm câu tiếng Hà Lan và sinh bài đọc theo từ đã học.

Mọi hàm ở đây đều chặn (blocking) nên giao diện phải gọi chúng qua
ui_common.run_async để cửa sổ không bị đơ.
"""

import json

import config
from reading_schema import normalize_test
from text_utils import entry_word, strip_tags

_client = None


class AITeacherError(RuntimeError):
    """Lỗi khi gọi AI, đã được diễn giải sang tiếng Việt cho dễ đọc."""


def is_configured() -> bool:
    return config.ai_is_configured()


def _get_client():
    global _client
    if _client is not None:
        return _client

    if not config.ai_is_configured():
        raise AITeacherError(
            "Chưa có API key. Bản cài đặt hỏi key ở lần mở đầu; "
            "khi chạy source thì điền OPENAI_API_KEY trong file .env."
        )
    try:
        from openai import OpenAI
    except ImportError as e:
        raise AITeacherError(
            "Chưa cài thư viện openai. Chạy: pip install -r requirements.txt"
        ) from e

    kwargs = {"api_key": config.OPENAI_API_KEY, "timeout": config.OPENAI_TIMEOUT}
    if config.OPENAI_BASE_URL:
        kwargs["base_url"] = config.OPENAI_BASE_URL
    _client = OpenAI(**kwargs)
    return _client


def _chat_json(system_prompt: str, user_prompt: str, temperature: float = 0.4) -> dict:
    client = _get_client()
    try:
        response = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            temperature=temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    except AITeacherError:
        raise
    except Exception as e:
        raise AITeacherError(f"Không gọi được OpenAI: {e}") from e

    content = (response.choices[0].message.content or "").strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise AITeacherError(f"AI trả về dữ liệu không phải JSON hợp lệ: {e}") from e


# ============================================================
# 1) Chấm câu học viên tự đặt
# ============================================================

_SENTENCE_SYSTEM = """You are a patient {name_en} teacher.
The learner's native language is {native}. Write feedback_vi in {native} only.
If {native} is English, do not write Vietnamese anywhere in the JSON.
Học viên có ngôn ngữ gốc là {native}, trình độ {level}. Học viên vừa đặt một câu {name_vi}
với một từ mục tiêu.

Nhiệm vụ của bạn:
1. Kiểm tra học viên dùng từ mục tiêu ĐÚNG NGHĨA và ĐÚNG NGỮ PHÁP hay không
   (chú ý: thứ tự từ, chia động từ, mạo từ {articles}, số nhiều).
2. Giải thích NGẮN GỌN bằng {native}, nêu rõ lỗi nếu có.
3. Đưa ra câu đã sửa và một câu mẫu tự nhiên hơn dùng đúng từ mục tiêu.

Chỉ trả lời bằng JSON với đúng các khóa sau:
{{
  "is_correct_usage": true/false,
  "score": số thực từ 0 đến 1,
  "feedback_vi": "nhận xét bằng {native}, tối đa 4 câu",
  "corrected_sentence": "câu {name_vi} đã sửa",
  "suggested_sentence": "một câu mẫu khác dùng từ mục tiêu"
}}"""


def check_sentence(target_word: str, user_sentence: str, meaning_vi: str = "") -> dict:
    """Chấm một câu do học viên đặt trong ngôn ngữ đang học."""
    profile = config.current_language()
    word = strip_tags(target_word)
    user_prompt = (
        f"Ngôn ngữ: {profile['name_en']}\n"
        f"Từ mục tiêu: {word}\n"
        f"Nghĩa ({config.native_label()}): {meaning_vi or '(không có)'}\n"
        f"Câu của học viên: {user_sentence.strip()}"
    )
    data = _chat_json(
        _SENTENCE_SYSTEM.format(
            level=config.READING_LEVEL,
            name_en=profile["name_en"],
            name_vi=profile["name_vi"],
            native=config.native_label(),
            articles=", ".join(profile["articles"]) or "(không có)",
        ),
        user_prompt,
        temperature=0.2,
    )

    return {
        "is_correct_usage": bool(data.get("is_correct_usage")),
        "score": float(data.get("score") or 0.0),
        "feedback_vi": str(data.get("feedback_vi") or "").strip(),
        "corrected_sentence": str(data.get("corrected_sentence") or "").strip(),
        "suggested_sentence": str(data.get("suggested_sentence") or "").strip(),
    }


# ============================================================
# 2) Sinh bài đọc từ các từ đã học hôm nay
# ============================================================

_READING_SYSTEM = """You write reading texts in {name_en} for a student whose native language is {native},
at CEFR level {level}.

The learner's native language is {native}.
translation_vi, glossary meanings, instructions, and explanation_vi MUST be written in {native} only.
If {native} is English, those fields must be English. Do not use Vietnamese in them.

Yêu cầu bài đọc:
- Viết MỘT đoạn văn {name_vi} mạch lạc, khoảng {words} từ, chia 3-4 đoạn nhỏ,
  văn phong tự nhiên, đời thường, phù hợp trình độ {level}.
- Bài đọc PHẢI dùng tất cả các từ mục tiêu được cung cấp, dùng đúng ngữ cảnh.
  Có thể chia động từ hoặc đổi số nhiều cho hợp câu.
- Ngoài các từ mục tiêu, chỉ dùng từ vựng phổ thông ở trình độ {level}.

Yêu cầu câu hỏi (viết đề bằng {name_vi}, giải thích bằng {native}):
- 4 câu trắc nghiệm 4 lựa chọn A-D về nội dung bài đọc.
- 3 câu True / False / Not Given.
- 1 nhóm nối từ với nghĩa {native}, gồm ít nhất 5 từ mục tiêu.
- Đánh số câu liên tục từ 1 trở đi, không trùng số.
- Đáp án phải suy ra được từ bài đọc, không đoán mò.

Chỉ trả lời bằng JSON đúng cấu trúc sau:
{{
  "title": "tiêu đề {name_vi}",
  "level": "{level}",
  "passage": "nội dung bài đọc, dùng \\n\\n để ngăn đoạn",
  "translation_vi": "bản dịch sang {native} của toàn bài",
  "glossary": [{{"word": "từ", "vi": "nghĩa {native}"}}],
  "question_groups": [
    {{
      "type": "multiple_choice_single",
      "instructions": "hướng dẫn bằng {native}",
      "questions": [
        {{"number": 1, "prompt": "câu hỏi {name_vi}",
          "options": [{{"key": "A", "text": "..."}}, {{"key": "B", "text": "..."}},
                      {{"key": "C", "text": "..."}}, {{"key": "D", "text": "..."}}],
          "answer": "A", "explanation_vi": "giải thích ngắn"}}
      ]
    }},
    {{
      "type": "true_false_notgiven",
      "instructions": "hướng dẫn bằng {native}",
      "questions": [
        {{"number": 5, "prompt": "nhận định {name_vi}",
          "answer": "TRUE", "explanation_vi": "giải thích ngắn"}}
      ]
    }},
    {{
      "type": "vocab_matching",
      "instructions": "hướng dẫn bằng {native}",
      "prompts": [{{"number": 8, "text": "từ {name_vi}"}}],
      "options": [{{"code": "A", "text": "nghĩa {native}"}}],
      "answers": ["A"]
    }}
  ]
}}"""


def generate_reading(entries: list, level: str = None, passage_words: int = None) -> dict:
    """Sinh một bài đọc trong ngôn ngữ đang học, xoay quanh các từ đã ôn.

    `entries` là list các dict có khóa word (hoặc nl/en cũ) và vi.
    """
    profile = config.current_language()
    words = [e for e in entries if entry_word(e)]
    if not words:
        raise AITeacherError("Chưa có từ nào để tạo bài đọc.")

    level = (level or config.READING_LEVEL).upper()
    passage_words = passage_words or config.READING_PASSAGE_WORDS

    word_lines = "\n".join(
        f"- {strip_tags(entry_word(e))} = {e.get('vi', '')}" for e in words
    )
    user_prompt = f"Ngôn ngữ: {profile['name_en']}\nDanh sách {len(words)} từ mục tiêu:\n{word_lines}"
    system_prompt = _READING_SYSTEM.format(
        level=level,
        words=passage_words,
        name_en=profile["name_en"],
        name_vi=profile["name_vi"],
        native=config.native_label(),
    )

    last_error = None
    for attempt in range(2):
        try:
            data = _chat_json(system_prompt, user_prompt, temperature=0.7 if attempt else 0.5)
            test = normalize_test(data)
            test["source"] = "ai"
            test["target_words"] = [strip_tags(entry_word(e)) for e in words]
            return test
        except (AITeacherError, ValueError) as e:
            last_error = e

    raise AITeacherError(f"AI không tạo được bài đọc hợp lệ: {last_error}")
