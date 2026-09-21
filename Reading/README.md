# Bài đọc tự soạn (không bắt buộc)

Bình thường bài đọc do AI viết theo các từ bạn ôn trong ngày. Thư mục này chỉ là
nguồn dự phòng khi chưa có API key hoặc khi gọi AI thất bại.

Mỗi bài nằm trong một thư mục con kèm file `AnswerKey.json`:

```
Reading/
  Op de markt/
    AnswerKey.json
```

```json
{
  "title": "Op de markt",
  "level": "A2",
  "passage": "Ik ga elke zaterdag naar de markt.\n\nDe markt is altijd druk.",
  "translation_vi": "Tôi ra chợ mỗi thứ Bảy...",
  "glossary": [{ "nl": "druk", "vi": "đông đúc" }],
  "question_groups": [
    {
      "type": "multiple_choice_single",
      "instructions": "Chọn đáp án đúng.",
      "questions": [
        {
          "number": 1,
          "prompt": "Wanneer gaat hij naar de markt?",
          "options": [
            { "key": "A", "text": "Op maandag" },
            { "key": "B", "text": "Op zaterdag" }
          ],
          "answer": "B",
          "explanation_vi": "Câu đầu tiên nói rõ 'elke zaterdag'."
        }
      ]
    },
    {
      "type": "true_false_notgiven",
      "questions": [
        { "number": 2, "prompt": "De markt is rustig.", "answer": "FALSE" }
      ]
    },
    {
      "type": "vocab_matching",
      "prompts": [{ "number": 3, "text": "druk" }],
      "options": [
        { "code": "A", "text": "đông đúc" },
        { "code": "B", "text": "rẻ" }
      ],
      "answers": ["A"]
    }
  ]
}
```

Các loại `question_groups` được hỗ trợ: `multiple_choice_single`,
`true_false_notgiven`, `vocab_matching`, `matching`, và hai định dạng IELTS cũ
`matching_heading` / `matching_person`. Nếu bỏ trường `passage`, app sẽ thử đọc
text từ file PDF khai báo ở `pdf_file` trong cùng thư mục.
