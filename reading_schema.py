"""Chuẩn hóa dữ liệu bài đọc về một định dạng duy nhất cho giao diện.

Bài đọc có thể đến từ hai nguồn:
  1. AI sinh ra theo các từ vừa học hôm nay.
  2. File AnswerKey.json tự soạn trong thư mục Reading/.

Hai nguồn đó dùng nhiều tên trường khác nhau, nên tất cả đi qua đây để quy về
hai loại câu hỏi mà reading_app biết vẽ:
  - "matching": mỗi câu chọn một mã (A, B, C...) từ danh sách lựa chọn dùng chung.
  - "choice"  : mỗi câu có bộ đáp án riêng, chọn bằng radio button.
"""

TRUE_FALSE_OPTIONS = [
    {"key": "TRUE", "text": "TRUE - đúng với bài đọc"},
    {"key": "FALSE", "text": "FALSE - trái với bài đọc"},
    {"key": "NOT GIVEN", "text": "NOT GIVEN - bài đọc không nhắc tới"},
]

_TITLES = {
    "matching_heading": "Chọn tiêu đề cho từng đoạn",
    "matching_person": "Nối nhân vật với nhận định",
    "matching": "Nối các vế với nhau",
    "vocab_matching": "Nối từ với nghĩa",
    "multiple_choice_single": "Trắc nghiệm",
    "true_false_notgiven": "True / False / Not Given",
}


def _as_options(raw, key_name: str) -> list:
    """Đưa danh sách lựa chọn về dạng [{'code'|'key': ..., 'text': ...}]."""
    options = []
    for i, item in enumerate(raw or []):
        if isinstance(item, dict):
            code = item.get("code") or item.get("key") or chr(ord("A") + i)
            text = item.get("text") or item.get("name") or ""
        else:
            code = chr(ord("A") + i)
            text = str(item)
        options.append({key_name: str(code).strip(), "text": str(text).strip()})
    return options


def _as_prompts(raw, start_number: int) -> list:
    """Đưa danh sách câu hỏi dạng nối về [{'number': n, 'text': ...}]."""
    prompts = []
    for i, item in enumerate(raw or []):
        if isinstance(item, dict):
            number = item.get("number", start_number + i)
            text = item.get("text") or item.get("name") or item.get("nl") or ""
        else:
            number = start_number + i
            text = str(item)
        prompts.append({"number": number, "text": str(text).strip()})
    return prompts


def _start_number(group: dict, default: int = 1) -> int:
    rng = group.get("number_range")
    if isinstance(rng, list) and rng:
        try:
            return int(rng[0])
        except (TypeError, ValueError):
            pass
    return default


def normalize_group(group: dict, next_number: int = 1):
    """Chuyển một question_group thô thành dạng chuẩn, hoặc None nếu không hợp lệ."""
    if not isinstance(group, dict):
        return None

    gtype = str(group.get("type") or "").strip().lower()
    title = group.get("title") or _TITLES.get(gtype, "Câu hỏi")
    instructions = str(group.get("instructions") or "").strip()

    # ----- Nhóm câu hỏi dạng nối -----
    if gtype in ("matching", "matching_heading", "matching_person", "vocab_matching"):
        raw_options = group.get("options") or group.get("headings") or group.get("statements")
        raw_prompts = group.get("prompts") or group.get("sections") or group.get("items")
        answers = [str(a).strip() for a in (group.get("answers") or [])]

        options = _as_options(raw_options, "code")
        prompts = _as_prompts(raw_prompts, _start_number(group, next_number))
        if not options or not prompts or len(answers) < len(prompts):
            return None

        return {
            "kind": "matching",
            "title": title,
            "instructions": instructions,
            "options": options,
            "prompts": prompts,
            "answers": answers[: len(prompts)],
            "explanations": [str(x) for x in (group.get("explanations") or [])],
        }

    # ----- Nhóm câu hỏi chọn đáp án -----
    if gtype in ("multiple_choice_single", "multiple_choice", "true_false_notgiven", "true_false"):
        is_tfng = gtype.startswith("true_false")
        questions = []
        for i, q in enumerate(group.get("questions") or []):
            if not isinstance(q, dict):
                continue
            answer = str(q.get("answer") or "").strip()
            prompt = str(q.get("prompt") or q.get("text") or "").strip()
            if not answer or not prompt:
                continue

            options = _as_options(q.get("options"), "key")
            if not options and is_tfng:
                options = [dict(o) for o in TRUE_FALSE_OPTIONS]
            if not options:
                continue

            questions.append(
                {
                    "number": q.get("number", next_number + i),
                    "prompt": prompt,
                    "options": options,
                    "answer": answer.upper(),
                    "explanation": str(q.get("explanation_vi") or q.get("explanation") or ""),
                }
            )

        if not questions:
            return None
        return {
            "kind": "choice",
            "title": title,
            "instructions": instructions,
            "questions": questions,
        }

    return None


def normalize_test(data: dict) -> dict:
    """Chuẩn hóa toàn bộ một bài đọc. Ném ValueError nếu dữ liệu không dùng được."""
    if not isinstance(data, dict):
        raise ValueError("Dữ liệu bài đọc không phải là JSON object.")

    passage = str(data.get("passage") or data.get("passage_text") or "").strip()
    if not passage:
        raise ValueError("Bài đọc không có nội dung ('passage').")

    groups = []
    next_number = 1
    for raw_group in data.get("question_groups") or []:
        group = normalize_group(raw_group, next_number)
        if group is None:
            continue
        groups.append(group)
        next_number += (
            len(group["prompts"]) if group["kind"] == "matching" else len(group["questions"])
        )

    if not groups:
        raise ValueError("Bài đọc không có nhóm câu hỏi nào hợp lệ.")

    glossary = []
    for item in data.get("glossary") or []:
        if isinstance(item, dict) and (item.get("nl") or item.get("word")):
            glossary.append(
                {
                    "nl": str(item.get("nl") or item.get("word")).strip(),
                    "vi": str(item.get("vi") or item.get("meaning") or "").strip(),
                }
            )

    return {
        "title": str(data.get("title") or "Leestekst").strip(),
        "level": str(data.get("level") or "").strip(),
        "passage": passage,
        "translation_vi": str(data.get("translation_vi") or "").strip(),
        "glossary": glossary,
        "groups": groups,
        "source": data.get("source", ""),
    }


def count_questions(test: dict) -> int:
    total = 0
    for group in test.get("groups", []):
        total += len(group["prompts"]) if group["kind"] == "matching" else len(group["questions"])
    return total
