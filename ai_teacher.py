# ai_teacher.py
import json
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

def check_sentence(target_word: str, user_sentence: str) -> dict:
    client = OpenAI(api_key=os.getenv("vocab_teacher_key"))

    SYSTEM_PROMPT = """
You are an English teacher. The learner is Vietnamese.
Your task:
1. Check if the student used the target word correctly.
2. Check grammar & naturalness.
3. Explain clearly in Vietnamese.
4. Provide ONE improved sentence using the target word.
Respond ONLY in JSON with keys:
{
  "is_correct_usage": true/false,
  "score": float (0..1),
  "feedback_vi": "string",
  "suggested_sentence": "string"
}
"""

    user_message = f"""
Từ mục tiêu: {target_word}
Câu của học viên: {user_sentence}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ],
        response_format={"type": "json_object"}   # CHUẨN SDK MỚI
    )

    json_text = response.choices[0].message.content
    return json.loads(json_text)