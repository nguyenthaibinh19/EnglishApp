import os
import glob
import json
import random
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk

import PyPDF2


ROMAN_NUMS = [
    "i", "ii", "iii", "iv", "v",
    "vi", "vii", "viii", "ix", "x",
    "xi", "xii", "xiii", "xiv", "xv",
    "xvi", "xvii", "xviii", "xix", "xx",
]


def int_to_roman(n: int) -> str:
    if 1 <= n <= len(ROMAN_NUMS):
        return ROMAN_NUMS[n - 1]
    return str(n)


def roman_to_int(s: str) -> int | None:
    s = s.strip().lower()
    if s in ROMAN_NUMS:
        return ROMAN_NUMS.index(s) + 1
    if s.isdigit():
        return int(s)
    return None


class ReadingApp:
    """
    ReadingApp kiểu IELTS:
    - Bên trái: passage (từ PDF)
    - Bên phải: List of headings + combobox chọn heading cho từng Section
    - Bài + đáp án được lấy ngẫu nhiên từ thư mục Reading/ và Answer/
    """

    def __init__(
        self,
        root: tk.Toplevel,
        on_completed=None,
        on_request_switch=None,
        reading_dir: str = "Reading",
        answer_dir: str = "Answer",
    ):
        """
        root: Toplevel dùng riêng cho Reading
        on_completed: callback khi hoàn thành bài reading (làm đúng hết)
        on_request_switch: callback khi bấm 'Chuyển sang luyện từ vựng'
        reading_dir: thư mục chứa các file PDF
        answer_dir: thư mục chứa các file JSON đáp án
        """
        self.root = root
        self.on_completed = on_completed
        self.on_request_switch = on_request_switch
        self.reading_dir = reading_dir
        self.answer_dir = answer_dir

        self.root.title("Reading Guard")

        # Fullscreen + luôn trên cùng
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)

        # Chặn đóng cửa sổ bằng nút X
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Chặn Alt+F4
        self.root.bind_all("<Alt-F4>", self.disable_alt_f4)

        # Giữ focus
        self.disable_force_focus = False
        self.root.bind("<FocusOut>", self.on_focus_out)

        self.completed = False

        # --------- Load 1 bài ngẫu nhiên ---------
        self.test_data = self.load_random_test()
        # test_data gồm: title, passage_text, sections, headings, answers

        # list StringVar cho câu trả lời
        self.answer_vars: list[tk.StringVar] = []

        self.build_ui()

    # ============================================================
    # 1) LOAD BÀI & ĐÁP ÁN
    # ============================================================

    def load_random_test(self) -> dict:
        """
        Chọn ngẫu nhiên 1 file PDF trong reading_dir
        mà có file JSON cùng tên trong answer_dir.
        Trả về dict:
        {
          "title": str,
          "passage_text": str,
          "sections": [str, ...],
          "headings": [str, ...],
          "answers": [int, ...]  # 1-based index heading đúng cho từng section
        }
        """
        pdf_files = glob.glob(os.path.join(self.reading_dir, "*.pdf"))
        pairs: list[tuple[str, str]] = []

        for pdf_path in pdf_files:
            base = os.path.splitext(os.path.basename(pdf_path))[0]
            ans_path = os.path.join(self.answer_dir, base + ".json")
            if os.path.exists(ans_path):
                pairs.append((pdf_path, ans_path))

        if not pairs:
            messagebox.showerror(
                "Lỗi dữ liệu",
                "Không tìm thấy cặp file PDF + JSON nào trong thư mục Reading/ và Answer/.\n"
                "Hãy kiểm tra lại cấu trúc thư mục và tên file.",
                parent=self.root,
            )
            # Nếu không có dữ liệu thì thoát luôn cho đỡ kẹt
            self.root.destroy()
            return {}

        pdf_path, ans_path = random.choice(pairs)

        # Đọc passage từ PDF
        passage_text = self.extract_text_from_pdf(pdf_path)

        # Đọc cấu hình câu hỏi + đáp án
        with open(ans_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        title = meta.get("title", os.path.basename(pdf_path))
        sections = meta["sections"]
        headings = meta["headings"]
        answers = meta["answers"]

        if len(sections) != len(answers):
            raise ValueError(
                f"Số lượng section ({len(sections)}) và số lượng đáp án ({len(answers)}) không khớp."
            )

        return {
            "title": title,
            "passage_text": passage_text,
            "sections": sections,
            "headings": headings,
            "answers": answers,
        }

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Đọc toàn bộ text từ PDF (đơn giản)."""
        text_parts: list[str] = []
        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                try:
                    t = page.extract_text() or ""
                except Exception:
                    t = ""
                text_parts.append(t.strip())
        return "\n\n".join(p for p in text_parts if p)

    # ============================================================
    # 2) UI
    # ============================================================

    def build_ui(self):
        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Thanh tiêu đề trên cùng
        title_label = tk.Label(
            self.main_frame,
            text=self.test_data.get("title", "Reading Practice"),
            font=("Arial", 22, "bold"),
            anchor="w",
        )
        title_label.pack(fill=tk.X, pady=(0, 10))

        # Khung chia 2 cột: left (passage) & right (questions)
        body_frame = tk.Frame(self.main_frame)
        body_frame.pack(fill=tk.BOTH, expand=True)

        # ---------- LEFT: PASSAGE ----------
        left_frame = tk.Frame(body_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        passage_label = tk.Label(
            left_frame, text="Reading Passage", font=("Arial", 14, "bold"), anchor="w"
        )
        passage_label.pack(fill=tk.X, pady=(0, 5))

        passage_container = tk.Frame(left_frame, relief=tk.GROOVE, borderwidth=1)
        passage_container.pack(fill=tk.BOTH, expand=True)

        self.passage_text = tk.Text(
            passage_container,
            font=("Arial", 12),
            wrap="word",
        )
        self.passage_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        scroll = tk.Scrollbar(
            passage_container, orient=tk.VERTICAL, command=self.passage_text.yview
        )
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.passage_text.config(yscrollcommand=scroll.set)

        self.passage_text.insert("1.0", self.test_data.get("passage_text", ""))
        self.passage_text.config(state="disabled")

        # ---------- RIGHT: QUESTIONS ----------
        right_frame = tk.Frame(body_frame, width=350)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y)

        # Phần chỉ dẫn chung
        instr = tk.Label(
            right_frame,
            text=(
                "Questions\n\n"
                "Choose the correct heading for each section from the list below.\n"
                "Write the correct number (i, ii, iii, ...) for each section."
            ),
            font=("Arial", 11),
            justify="left",
        )
        instr.pack(fill=tk.X, pady=(0, 5))

        # List of Headings
        headings_frame = tk.LabelFrame(
            right_frame, text="List of Headings", font=("Arial", 11, "bold")
        )
        headings_frame.pack(fill=tk.X, pady=5)

        headings = self.test_data["headings"]

        for idx, heading in enumerate(headings, start=1):
            roman = int_to_roman(idx)
            lbl = tk.Label(
                headings_frame,
                text=f"{roman}. {heading}",
                font=("Arial", 10),
                justify="left",
                wraplength=300,
                anchor="w",
            )
            lbl.pack(fill=tk.X, padx=5, pady=2)

        # Khung các câu hỏi: mỗi section 1 combobox
        questions_frame = tk.LabelFrame(
            right_frame, text="Questions by section", font=("Arial", 11, "bold")
        )
        questions_frame.pack(fill=tk.X, pady=5)

        sections = self.test_data["sections"]
        roman_choices = [int_to_roman(i) for i in range(1, len(headings) + 1)]

        for i, section_name in enumerate(sections, start=1):
            row_frame = tk.Frame(questions_frame)
            row_frame.pack(fill=tk.X, pady=3, padx=5)

            num_label = tk.Label(
                row_frame,
                text=str(i),
                font=("Arial", 11, "bold"),
                width=3,
                anchor="center",
            )
            num_label.pack(side=tk.LEFT)

            var = tk.StringVar()
            cb = ttk.Combobox(
                row_frame,
                values=roman_choices,
                textvariable=var,
                state="readonly",
                width=5,
                font=("Arial", 10),
            )
            cb.pack(side=tk.LEFT, padx=5)
            # chưa chọn thì để trống
            cb.set("")

            sec_label = tk.Label(
                row_frame,
                text=section_name,
                font=("Arial", 10),
                anchor="w",
            )
            sec_label.pack(side=tk.LEFT, padx=5)

            self.answer_vars.append(var)

        # Nút chức năng
        btn_frame = tk.Frame(right_frame)
        btn_frame.pack(pady=10)

        self.check_button = tk.Button(
            btn_frame,
            text="Chấm bài reading",
            font=("Arial", 12),
            command=self.check_reading,
        )
        self.check_button.pack(side=tk.LEFT, padx=5)

        switch_btn = tk.Button(
            btn_frame,
            text="Chuyển sang luyện từ vựng",
            font=("Arial", 11),
            command=self.request_switch_to_vocab,
        )
        switch_btn.pack(side=tk.LEFT, padx=5)

        self.emergency_button = tk.Button(
            right_frame,
            text="Thoát khẩn cấp",
            font=("Arial", 10),
            command=self.emergency_exit,
        )
        self.emergency_button.pack(pady=(0, 5))

        self.feedback_label = tk.Label(
            right_frame,
            text="",
            font=("Arial", 11),
            fg="blue",
            wraplength=320,
            justify="left",
        )
        self.feedback_label.pack(pady=5, fill=tk.X)

    # ============================================================
    # 3) LOGIC CHẤM BÀI
    # ============================================================

    def check_reading(self):
        answers_key = self.test_data["answers"]  # list int 1-based
        total = len(answers_key)
        correct_count = 0
        unanswered = 0

        user_choices = []

        for var in self.answer_vars:
            val = var.get().strip()
            if not val:
                user_choices.append(None)
                unanswered += 1
                continue

            idx = roman_to_int(val)
            user_choices.append(idx)

        for idx, chosen in enumerate(user_choices):
            key = answers_key[idx]
            if chosen is not None and chosen == key:
                correct_count += 1

        if correct_count == total and unanswered == 0:
            self.completed = True
            self.feedback_label.config(
                text=f"Tuyệt vời! Bạn đã làm đúng {correct_count}/{total} câu. ✅",
                fg="green",
            )
            if self.on_completed:
                self.on_completed()
            # Tùy app của bạn: nếu muốn đóng luôn cửa sổ:
            self.root.destroy()
        else:
            self.completed = False
            self.feedback_label.config(
                text=(
                    f"Bạn làm đúng {correct_count}/{total} câu "
                    f"(bỏ trống {unanswered}).\n"
                    "Hãy xem lại passage và chỉnh sửa câu trả lời."
                ),
                fg="red",
            )

    # ============================================================
    # 4) SWITCH & ANTI-ESCAPE
    # ============================================================

    def request_switch_to_vocab(self):
        if self.on_request_switch:
            self.on_request_switch()

    def disable_alt_f4(self, event=None):
        return "break"

    def on_focus_out(self, event=None):
        self.root.after(100, self.force_focus)

    def force_focus(self):
        if getattr(self, "disable_force_focus", False):
            return
        try:
            self.root.attributes("-topmost", True)
            self.root.focus_force()
            self.root.lift()
        except Exception:
            pass

    def emergency_exit(self):
        """
        Thoát khẩn cấp:
        - Tạm tắt cơ chế ép focus + topmost
        - Hiện hộp thoại xác nhận thoát
        - Nếu đồng ý -> đóng app
        - Nếu không -> khôi phục trạng thái khóa màn hình
        """
        try:
            self.disable_force_focus = True
        except Exception:
            pass

        try:
            self.root.attributes("-topmost", False)
        except Exception:
            pass

        try:
            ok = messagebox.askyesno(
                "Thoát khẩn cấp",
                "Thoát khẩn cấp chỉ nên dùng khi bị lỗi.\n"
                "Bạn có chắc chắn muốn thoát không?",
                parent=self.root,
            )
        except Exception as e:
            print("Lỗi khi hiện messagebox emergency_exit:", e)
            ok = True

        if ok:
            try:
                self.root.destroy()
            except Exception:
                pass
        else:
            try:
                self.disable_force_focus = False
            except Exception:
                pass
            try:
                self.root.attributes("-topmost", True)
            except Exception:
                pass

    def on_close(self):
        # Không cho tắt bằng nút X
        pass
