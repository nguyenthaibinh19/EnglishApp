# langstudyguard

Ứng dụng desktop ép bản thân học tiếng Hà Lan mỗi ngày. Cửa sổ chạy
toàn màn hình, luôn nằm trên cùng và chỉ cho đóng khi đã xong cả hai phần:

1. **Luyện từ vựng** — nhìn nghĩa tiếng Việt, gõ từ tiếng Hà Lan.
2. **Luyện đọc** — AI viết một bài đọc mới dựa trên chính những từ bạn vừa ôn
   hôm nay, kèm câu hỏi trắc nghiệm, True/False/Not Given và nối từ.

## Dành cho người dùng

Tải `langstudyguard.exe` (file đính kèm ở mục Releases, không cần cài Python).

1. Mở file đó. Windows có thể báo “Unknown publisher” — bấm **More info**, rồi **Run anyway**.
2. App tự chép vào `%LOCALAPPDATA%\langstudyguard\` và tự thêm vào Startup.
3. Lần đầu đăng nhập tài khoản do người phát triển tạo. API key không nằm trong app.
4. Từ vựng và tiến độ được lưu ở `%APPDATA%\langstudyguard\`. Bản mới tự tải về và thay file cũ khi người dùng đồng ý. Dữ liệu từ thư mục DutchGuard cũ được chép sang, không bị mất.

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

File ra ở `dist\langstudyguard.exe`.

## Thêm từ vựng

Sửa từ trong app, hoặc sửa file từ vựng của từng ngôn ngữ trong thư mục dữ liệu. File mẫu nằm ở `data/vocab.json`.

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

Nếu chưa gọi được AI, app sẽ tìm bài tự soạn trong `data/Reading/<tên bài>/AnswerKey.json`
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

## Cấu trúc

```
main.py              cách chạy: python main.py
app/                 toàn bộ code
data/                từ mẫu, bộ từ khởi đầu, bài đọc soạn sẵn
deploy/hetzner/      cài server tài khoản lên VPS
archive/             dữ liệu bản tiếng Anh cũ
```

| File trong `app/` | Vai trò |
| --- | --- |
| `main.py` | Menu chính, điều phối hai phần và điều kiện thoát |
| `config.py` | Đường dẫn, `.env`, ngôn ngữ đang học |
| `setup_wizard.py` | Đăng nhập tài khoản |
| `quiz_app.py` | Giao diện luyện từ vựng, đặt câu ví dụ, sổ từ |
| `quiz_engine.py` | Chọn câu và chấm điểm, không phụ thuộc Tkinter |
| `reading_app.py` | Giao diện luyện đọc |
| `reading_source.py` | Chọn từ, gọi AI, cache, nguồn dự phòng |
| `ai_teacher.py` | Chấm câu và viết bài đọc |
| `account_server.py` | Server giữ API key |
| `account_client.py` | App người học gọi server |
| `dictionary.py` | Tra từ |
| `ui_common.py` | Khóa màn hình và tiện ích giao diện |
| `smoke_test.py` | Kiểm tra logic: `python app/smoke_test.py` |

Dữ liệu tiếng Anh của phiên bản cũ được giữ trong `archive/`.
