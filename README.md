# Dutch Guard

Ứng dụng desktop ép bản thân học tiếng Hà Lan mỗi ngày. Cửa sổ chạy
toàn màn hình, luôn nằm trên cùng và chỉ cho đóng khi đã xong cả hai phần:

1. **Luyện từ vựng** — nhìn nghĩa tiếng Việt, gõ từ tiếng Hà Lan.
2. **Luyện đọc** — AI viết một bài đọc mới dựa trên chính những từ bạn vừa ôn
   hôm nay, kèm câu hỏi trắc nghiệm, True/False/Not Given và nối từ.

## Dành cho người dùng

Tải `DutchGuard.exe` (file đính kèm ở mục Releases, không cần cài Python).

1. Mở file đó. Windows có thể báo “Unknown publisher” — bấm **More info**, rồi **Run anyway**.
2. App tự chép vào `%LOCALAPPDATA%\DutchGuard\` và tự thêm vào Startup.
3. Lần đầu nhập OpenAI API key. Mật khẩu thoát khẩn cấp là mật khẩu dev đã đóng trong file cài, người dùng không đặt và không xem được mật khẩu đó.
4. Từ vựng và tiến độ được lưu ở `%APPDATA%\DutchGuard\`, nên cập nhật bản mới không mất dữ liệu.

Từ đó mỗi lần đăng nhập Windows, app tự mở.

## Dành cho người phát triển

```bash
pip install -r requirements.txt
copy .env.example .env      # rồi điền OPENAI_API_KEY
```

Chạy bằng `start_dutch_guard.bat` hoặc `python main.py`. Cách này dùng file trong thư mục dự án, không đụng bản cài của người dùng.

Đóng gói file `.exe`:

```bash
build_exe.bat
```

File ra ở `dist\DutchGuard.exe`.

## Thêm từ vựng

Sửa trực tiếp `vocab.json`, hoặc dùng nút **Quản lý từ vựng** ngay trong app.

```json
{
  "nl": "de fiets",
  "vi": "xe đạp",
  "alt": ["rijwiel"],
  "example": "Ik ga met de fiets naar mijn werk."
}
```

Chỉ `nl` và `vi` là bắt buộc. Vài điều tiện lợi khi làm bài:

- Danh từ nên viết kèm mạo từ (`de`/`het`), nhưng gõ thiếu mạo từ vẫn tính đúng.
- `alt` liệt kê các cách viết khác cũng được chấp nhận.
- Sai một ký tự hoặc thiếu dấu (`een` vs `één`) được tính là đúng nhưng có nhắc
  chính tả, và từ đó sẽ bị hỏi lại trong phiên.
- Tag loại từ trong ngoặc như `lopen (ww)` được bỏ qua khi so đáp án.

File `vocab.json` định dạng cũ dùng khóa `en` vẫn đọc được — lần chạy đầu tiên
app sẽ tự đổi sang `nl`.

## Cách app chọn câu hỏi

`progress.json` lưu thống kê từng từ (số lần đúng/sai, chuỗi đúng, lần ôn gần
nhất). Từ mới và từ hay sai được ưu tiên hỏi, từ đã thuộc thì giãn ra. Trả lời
sai thì vài câu sau sẽ bị hỏi lại, và nếu có API key thì bạn phải đặt một câu
với từ đó cho AI chấm mới được đi tiếp.

## Bài đọc do AI sinh

Phần đọc lấy các từ đã kiểm tra trong ngày (thiếu thì bù bằng từ hay sai rồi từ
ngẫu nhiên) và nhờ AI viết một bài ở trình độ CEFR cấu hình được. Bài đã sinh
được lưu trong `cache/` theo ngày, nên mở lại không tốn thêm tiền API; bấm
**Tạo bài đọc mới** nếu muốn bài khác.

Nếu chưa có API key, app sẽ tìm bài tự soạn trong `Reading/<tên bài>/AnswerKey.json`
(hỗ trợ cả định dạng IELTS cũ và đọc passage từ PDF).

## Cấu hình

Mọi thứ chỉnh trong `.env`, xem `.env.example`. Đáng chú ý:

| Biến | Mặc định | Ý nghĩa |
| --- | --- | --- |
| `QUIZ_TARGET_CORRECT` | 30 | Số câu đúng cần đạt mỗi ngày |
| `DUTCH_LEVEL` | A2 | Trình độ CEFR của bài đọc |
| `READING_WORD_COUNT` | 12 | Số từ đưa vào bài đọc |
| `READING_PASS_RATIO` | 0.8 | Tỉ lệ đúng tối thiểu để qua phần đọc |
| `LOCK_SCREEN` | 1 | Đặt `0` khi sửa code để cửa sổ không chiếm màn hình |
| `EMERGENCY_PASSWORD` | (trong `.env`) | Mật khẩu để dùng nút thoát khẩn cấp |

## Cấu trúc mã nguồn

| File | Vai trò |
| --- | --- |
| `main.py` | Menu chính, điều phối hai phần và điều kiện thoát |
| `quiz_app.py` | Giao diện luyện từ vựng, đặt câu ví dụ, quản lý từ |
| `quiz_engine.py` | Logic chọn câu và chấm điểm, không phụ thuộc Tkinter |
| `reading_app.py` | Giao diện luyện đọc |
| `reading_source.py` | Chọn từ, gọi AI, cache, nguồn dự phòng |
| `reading_schema.py` | Quy mọi định dạng câu hỏi về một dạng chuẩn |
| `ai_teacher.py` | Gọi OpenAI: chấm câu và viết bài đọc |
| `vocab_store.py` | Đọc/ghi `vocab.json` |
| `progress.py` | Thống kê từng từ và nhật ký theo ngày |
| `text_utils.py` | Chuẩn hóa và so khớp đáp án tiếng Hà Lan |
| `ui_common.py` | Khóa màn hình, chạy AI ở luồng nền, widget dùng chung |
| `smoke_test.py` | Kiểm tra nhanh phần logic: `python smoke_test.py` |

Dữ liệu tiếng Anh của phiên bản cũ được giữ trong `archive/`.
