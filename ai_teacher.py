"""Cầu nối tới OpenAI: chấm câu tiếng Hà Lan và sinh bài đọc theo từ đã học.

Mọi hàm ở đây đều chặn (blocking) nên giao diện phải gọi chúng qua
ui_common.run_async để cửa sổ không bị đơ.
"""

import json

import config
from reading_schema import normalize_test
from text_utils import strip_tags

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

_SENTENCE_SYSTEM = """Je bent een geduldige docent Nederlands.
Học viên là người Việt, trình độ {level}. Học viên vừa đặt một câu tiếng Hà Lan
với một từ mục tiêu.

Nhiệm vụ của bạn:
1. Kiểm tra học viên dùng từ mục tiêu ĐÚNG NGHĨA và ĐÚNG NGỮ PHÁP hay không
   (chú ý: thứ tự từ, chia động từ, mạo từ de/het, số nhiều).
2. Giải thích NGẮN GỌN bằng tiếng Việt, nêu rõ lỗi nếu có.
3. Đưa ra câu đã sửa và một câu mẫu tự nhiên hơn dùng đúng từ mục tiêu.

Chỉ trả lời bằng JSON với đúng các khóa sau:
{{
  "is_correct_usage": true/false,
  "score": số thực từ 0 đến 1,
  "feedback_vi": "nhận xét tiếng Việt, tối đa 4 câu",
  "corrected_sentence": "câu tiếng Hà Lan đã sửa",
  "suggested_sentence": "một câu mẫu khác dùng từ mục tiêu"
}}"""


def check_sentence(target_word: str, user_sentence: str, meaning_vi: str = "") -> dict:
    """Chấm một câu tiếng Hà Lan do học viên đặt."""
    word = strip_tags(target_word)
    user_prompt = (
        f"Từ mục tiêu: {word}\n"
        f"Nghĩa tiếng Việt: {meaning_vi or '(không có)'}\n"
        f"Câu của học viên: {user_sentence.strip()}"
    )
    data = _chat_json(
        _SENTENCE_SYSTEM.format(level=config.READING_LEVEL),
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

_READING_SYSTEM = """Je bent een docent Nederlands die leesteksten schrijft voor
een Vietnamese student op CEFR-niveau {level}.

Yêu cầu bài đọc:
- Viết MỘT đoạn văn tiếng Hà Lan mạch lạc, khoảng {words} từ, chia 3-4 đoạn nhỏ,
  văn phong tự nhiên, đời thường, phù hợp trình độ {level}.
- Bài đọc PHẢI dùng tất cả các từ mục tiêu được cung cấp, dùng đúng ngữ cảnh.
  Có thể chia động từ hoặc đổi số nhiều cho hợp câu.
- Ngoài các từ mục tiêu, chỉ dùng từ vựng phổ thông ở trình độ {level}.

Yêu cầu câu hỏi (viết đề bằng tiếng Hà Lan, giải thích bằng tiếng Việt):
- 4 câu trắc nghiệm 4 lựa chọn A-D về nội dung bài đọc.
- 3 câu True / False / Not Given.
- 1 nhóm nối từ với nghĩa tiếng Việt, gồm ít nhất 5 từ mục tiêu.
- Đánh số câu liên tục từ 1 trở đi, không trùng số.
- Đáp án phải suy ra được từ bài đọc, không đoán mò.

Chỉ trả lời bằng JSON đúng cấu trúc sau:
{{
  "title": "tiêu đề tiếng Hà Lan",
  "level": "{level}",
  "passage": "nội dung bài đọc, dùng \\n\\n để ngăn đoạn",
  "translation_vi": "bản dịch tiếng Việt của toàn bài",
  "glossary": [{{"nl": "từ", "vi": "nghĩa"}}],
  "question_groups": [
    {{
      "type": "multiple_choice_single",
      "instructions": "hướng dẫn tiếng Việt",
      "questions": [
        {{"number": 1, "prompt": "câu hỏi tiếng Hà Lan",
          "options": [{{"key": "A", "text": "..."}}, {{"key": "B", "text": "..."}},
                      {{"key": "C", "text": "..."}}, {{"key": "D", "text": "..."}}],
          "answer": "A", "explanation_vi": "giải thích ngắn"}}
      ]
    }},
    {{
      "type": "true_false_notgiven",
      "instructions": "hướng dẫn tiếng Việt",
      "questions": [
        {{"number": 5, "prompt": "nhận định tiếng Hà Lan",
          "answer": "TRUE", "explanation_vi": "giải thích ngắn"}}
      ]
    }},
    {{
      "type": "vocab_matching",
      "instructions": "hướng dẫn tiếng Việt",
      "prompts": [{{"number": 8, "text": "từ tiếng Hà Lan"}}],
      "options": [{{"code": "A", "text": "nghĩa tiếng Việt"}}],
      "answers": ["A"]
    }}
  ]
}}"""


def generate_reading(entries: list, level: str = None, passage_words: int = None) -> dict:
    """Sinh một bài đọc tiếng Hà Lan xoay quanh danh sách từ đã học.

    `entries` là list các dict {"nl": ..., "vi": ...} lấy từ vocab.json.
    Trả về dict đã chuẩn hóa theo reading_schema.normalize_test.
    """
    words = [e for e in entries if e.get("nl")]
    if not words:
        raise AITeacherError("Chưa có từ nào để tạo bài đọc.")

    level = (level or config.READING_LEVEL).upper()
    passage_words = passage_words or config.READING_PASSAGE_WORDS

    word_lines = "\n".join(
        f"- {strip_tags(e['nl'])} = {e.get('vi', '')}" for e in words
    )
    user_prompt = f"Danh sách {len(words)} từ mục tiêu:\n{word_lines}"
    system_prompt = _READING_SYSTEM.format(level=level, words=passage_words)

    last_error = None
    for attempt in range(2):
        try:
            data = _chat_json(system_prompt, user_prompt, temperature=0.7 if attempt else 0.5)
            test = normalize_test(data)
            test["source"] = "ai"
            test["target_words"] = [strip_tags(e["nl"]) for e in words]
            return test
        except (AITeacherError, ValueError) as e:
            last_error = e

    raise AITeacherError(f"AI không tạo được bài đọc hợp lệ: {last_error}")
