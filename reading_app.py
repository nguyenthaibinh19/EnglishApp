import os
import json
import random
import tkinter as tk
from tkinter import messagebox, ttk

import PyPDF2


# ----------------- Helpers ----------------- #

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


class ReadingApp:
    """
    ReadingApp kiểu IELTS:
    - Mỗi lần mở: chọn ngẫu nhiên 1 folder trong ./Reading
      folder đó phải chứa AnswerKey.json + file PDF.
    - AnswerKey.json chứa các question_groups với nhiều dạng:
      * matching_heading
      * matching_person
      * multiple_choice_single
    """

    def __init__(
        self,
        root: tk.Toplevel,
        on_completed=None,
        on_request_switch=None,
        reading_root: str = "Reading",
    ):
        self.root = root
        self.on_completed = on_completed
        self.on_request_switch = on_request_switch
        self.reading_root = reading_root

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

        # chỗ này sẽ lưu metadata cần cho việc chấm bài
        # mỗi phần tử: {"type": ..., "vars": [...], "answers": [...], ...}
        self.group_states = []

        # --------- Load 1 bài ngẫu nhiên ---------
        self.test_data = self.load_random_test()
        if not self.test_data:
            # Không có dữ liệu hợp lệ -> thoát luôn
            return

        self.build_ui()

    # ============================================================
    # 1) LOAD BÀI & ĐÁP ÁN
    # ============================================================

    def load_random_test(self) -> dict | None:
        """
        Chọn ngẫu nhiên 1 folder con trong self.reading_root
        chứa file AnswerKey.json. Đọc JSON + PDF trong đó.
        """
        if not os.path.isdir(self.reading_root):
            messagebox.showerror(
                "Lỗi dữ liệu",
                f"Không tìm thấy thư mục '{self.reading_root}'.",
                parent=self.root,
            )
            self.root.destroy()
            return None

        # liệt kê các folder con
        subfolders = [
            os.path.join(self.reading_root, name)
            for name in os.listdir(self.reading_root)
            if os.path.isdir(os.path.join(self.reading_root, name))
        ]

        valid_folders = []
        for folder in subfolders:
            ans_path = os.path.join(folder, "AnswerKey.json")
            if os.path.exists(ans_path):
                valid_folders.append(folder)

        if not valid_folders:
            messagebox.showerror(
                "Lỗi dữ liệu",
                "Không tìm thấy folder nào trong 'Reading/' có AnswerKey.json.\n"
                "Mỗi bài nên nằm trong 1 folder con, chứa passage.pdf + AnswerKey.json.",
                parent=self.root,
            )
            self.root.destroy()
            return None

        chosen_folder = random.choice(valid_folders)
        answer_path = os.path.join(chosen_folder, "AnswerKey.json")

        try:
            with open(answer_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception as e:
            messagebox.showerror(
                "Lỗi đọc AnswerKey.json",
                f"Không thể đọc file:\n{answer_path}\n\nChi tiết: {e}",
                parent=self.root,
            )
            self.root.destroy()
            return None

        # tên file PDF: ưu tiên field pdf_file, nếu không có thì dùng "passage.pdf"
        pdf_name = meta.get("pdf_file", "passage.pdf")
        pdf_path = os.path.join(chosen_folder, pdf_name)
        if not os.path.exists(pdf_path):
            messagebox.showerror(
                "Lỗi dữ liệu",
                f"Không tìm thấy file PDF '{pdf_name}' trong folder:\n{chosen_folder}",
                parent=self.root,
            )
            self.root.destroy()
            return None

        passage_text = self.extract_text_from_pdf(pdf_path)

        title = meta.get("title", os.path.basename(chosen_folder))
        question_groups = meta.get("question_groups", [])

        if not question_groups:
            messagebox.showerror(
                "Lỗi dữ liệu",
                "AnswerKey.json không chứa 'question_groups'.",
                parent=self.root,
            )
            self.root.destroy()
            return None

        return {
            "folder": chosen_folder,
            "title": title,
            "passage_text": passage_text,
            "question_groups": question_groups,
        }

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Đọc toàn bộ text từ PDF (đơn giản)."""
        text_parts = []
        try:
            with open(pdf_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    try:
                        t = page.extract_text() or ""
                    except Exception:
                        t = ""
                    if t:
                        text_parts.append(t.strip())
        except Exception as e:
            print("Lỗi đọc PDF:", e)
        return "\n\n".join(text_parts)

    # ============================================================
    # 2) UI CHUNG
    # ============================================================

    def build_ui(self):
        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Tiêu đề
        title_label = tk.Label(
            self.main_frame,
            text=self.test_data["title"],
            font=("Arial", 22, "bold"),
            anchor="w",
        )
        title_label.pack(fill=tk.X, pady=(0, 10))

        # Khung chia 2 cột
        body_frame = tk.Frame(self.main_frame)
        body_frame.pack(fill=tk.BOTH, expand=True)

        # ---------- LEFT: PASSAGE ----------
        left_frame = tk.Frame(body_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        passage_label = tk.Label(
            left_frame,
            text="Reading Passage",
            font=("Arial", 14, "bold"),
            anchor="w",
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

        self.passage_text.insert("1.0", self.test_data["passage_text"])
        self.passage_text.config(state="disabled")

        # ---------- RIGHT: QUESTIONS ----------
        right_frame = tk.Frame(body_frame, width=400)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH)

        # Hộp cuộn cho tất cả question groups (phòng trường hợp nhiều)
        canvas = tk.Canvas(right_frame)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        q_scroll = tk.Scrollbar(
            right_frame, orient=tk.VERTICAL, command=canvas.yview
        )
        q_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.configure(yscrollcommand=q_scroll.set)

        inner = tk.Frame(canvas)
        canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_config(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        inner.bind("<Configure>", _on_config)

        # tạo UI cho từng question_group
        for group in self.test_data["question_groups"]:
            gtype = group.get("type")
            if gtype == "matching_heading":
                self.build_group_matching_heading(inner, group)
            elif gtype == "matching_person":
                self.build_group_matching_person(inner, group)
            elif gtype == "multiple_choice_single":
                self.build_group_mc_single(inner, group)
            else:
                # loại chưa hỗ trợ: hiển thị thông báo text
                frame = tk.LabelFrame(
                    inner,
                    text=f"Nhóm câu hỏi (chưa hỗ trợ type='{gtype}')",
                    font=("Arial", 11, "bold"),
                )
                frame.pack(fill=tk.X, pady=5, padx=5)
                tk.Label(
                    frame,
                    text="Loại câu hỏi này chưa được hỗ trợ trong app.",
                    font=("Arial", 10),
                    fg="red",
                ).pack(fill=tk.X, padx=5, pady=5)

        # Nút chức năng + feedback
        btn_frame = tk.Frame(self.main_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        self.check_button = tk.Button(
            btn_frame,
            text="Chấm bài reading",
            font=("Arial", 12),
            command=self.check_all,
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
            btn_frame,
            text="Thoát khẩn cấp",
            font=("Arial", 10),
            command=self.emergency_exit,
        )
        self.emergency_button.pack(side=tk.RIGHT, padx=5)

        self.feedback_label = tk.Label(
            self.main_frame,
            text="",
            font=("Arial", 11),
            fg="blue",
            wraplength=600,
            justify="left",
        )
        self.feedback_label.pack(fill=tk.X, pady=5)

    # ============================================================
    # 3) UI CHO TỪNG LOẠI QUESTION GROUP
    # ============================================================

    def build_group_matching_heading(self, parent: tk.Frame, group: dict):
        frame = tk.LabelFrame(
            parent,
            text="Matching headings",
            font=("Arial", 11, "bold"),
        )
        frame.pack(fill=tk.X, pady=5, padx=5)

        instr = group.get("instructions", "")
        if instr:
            tk.Label(
                frame, text=instr, font=("Arial", 10), justify="left", wraplength=360
            ).pack(fill=tk.X, padx=5, pady=3)

        sections = group["sections"]
        headings = group["headings"]  # list of {code, text}
        answers = group["answers"]    # list of codes, cùng thứ tự với sections

        # List of Headings
        headings_frame = tk.LabelFrame(
            frame, text="List of Headings", font=("Arial", 10, "bold")
        )
        headings_frame.pack(fill=tk.X, padx=5, pady=5)

        for h in headings:
            code = h["code"]
            text = h["text"]
            tk.Label(
                headings_frame,
                text=f"{code}. {text}",
                font=("Arial", 10),
                justify="left",
                wraplength=340,
                anchor="w",
            ).pack(fill=tk.X, padx=5, pady=1)

        # Các câu 1..n
        q_frame = tk.LabelFrame(
            frame, text="Questions", font=("Arial", 10, "bold")
        )
        q_frame.pack(fill=tk.X, padx=5, pady=5)

        codes_choices = [h["code"] for h in headings]
        answer_vars = []
        # nếu có number_range -> dùng, không thì mặc định từ 1
        start_number = 1
        if "number_range" in group and isinstance(group["number_range"], list):
            start_number = int(group["number_range"][0])

        for idx, section_name in enumerate(sections):
            q_num = start_number + idx

            row = tk.Frame(q_frame)
            row.pack(fill=tk.X, pady=2, padx=5)

            tk.Label(
                row,
                text=str(q_num),
                font=("Arial", 10, "bold"),
                width=3,
                anchor="center",
            ).pack(side=tk.LEFT)

            var = tk.StringVar()
            cb = ttk.Combobox(
                row,
                values=codes_choices,
                textvariable=var,
                state="readonly",
                width=5,
                font=("Arial", 10),
            )

            # >>> thêm 2 dòng bind này <<<
            cb.bind("<Button-1>", self.start_free_focus)
            cb.bind("<<ComboboxSelected>>", self.end_free_focus)

            cb.pack(side=tk.LEFT, padx=4)
            cb.set("")

            tk.Label(
                row,
                text=section_name,
                font=("Arial", 10),
                anchor="w",
            ).pack(side=tk.LEFT, padx=4)

            answer_vars.append(var)

        # lưu state cho chấm bài
        self.group_states.append(
            {
                "type": "matching_heading",
                "answer_vars": answer_vars,
                "answers": answers,   # list of correct codes
            }
        )

    def build_group_matching_person(self, parent: tk.Frame, group: dict):
        frame = tk.LabelFrame(
            parent,
            text="Matching people with statements",
            font=("Arial", 11, "bold"),
        )
        frame.pack(fill=tk.X, pady=5, padx=5)

        instr = group.get("instructions", "")
        if instr:
            tk.Label(
                frame, text=instr, font=("Arial", 10), justify="left", wraplength=360
            ).pack(fill=tk.X, padx=5, pady=3)

        items = group["items"]        # list {number, name}
        statements = group["statements"]  # list {code, text}
        answers = group["answers"]    # list codes A-G, thứ tự theo items

        # List of Statements
        st_frame = tk.LabelFrame(
            frame, text="List of Statements", font=("Arial", 10, "bold")
        )
        st_frame.pack(fill=tk.X, padx=5, pady=5)

        for st in statements:
            code = st["code"]
            text = st["text"]
            tk.Label(
                st_frame,
                text=f"{code}. {text}",
                font=("Arial", 10),
                justify="left",
                wraplength=340,
                anchor="w",
            ).pack(fill=tk.X, padx=5, pady=1)

        # Các câu 6..12
        q_frame = tk.LabelFrame(
            frame, text="Questions", font=("Arial", 10, "bold")
        )
        q_frame.pack(fill=tk.X, padx=5, pady=5)

        codes_choices = [s["code"] for s in statements]
        answer_vars = []

        for item in items:
            number = item["number"]
            name = item["name"]

            row = tk.Frame(q_frame)
            row.pack(fill=tk.X, pady=2, padx=5)

            tk.Label(
                row,
                text=str(number),
                font=("Arial", 10, "bold"),
                width=3,
                anchor="center",
            ).pack(side=tk.LEFT)

            var = tk.StringVar()
            cb = ttk.Combobox(
                row,
                values=codes_choices,
                textvariable=var,
                state="readonly",
                width=5,
                font=("Arial", 10),
            )
            
            # >>> thêm 2 dòng này <<<
            cb.bind("<Button-1>", self.start_free_focus)
            cb.bind("<<ComboboxSelected>>", self.end_free_focus)
            
            cb.pack(side=tk.LEFT, padx=4)
            cb.set("")

            tk.Label(
                row,
                text=name,
                font=("Arial", 10),
                anchor="w",
            ).pack(side=tk.LEFT, padx=4)

            answer_vars.append(var)

        self.group_states.append(
            {
                "type": "matching_person",
                "answer_vars": answer_vars,
                "answers": answers,
            }
        )

    def build_group_mc_single(self, parent: tk.Frame, group: dict):
        frame = tk.LabelFrame(
            parent,
            text="Multiple choice",
            font=("Arial", 11, "bold"),
        )
        frame.pack(fill=tk.X, pady=5, padx=5)

        instr = group.get("instructions", "")
        if instr:
            tk.Label(
                frame, text=instr, font=("Arial", 10), justify="left", wraplength=360
            ).pack(fill=tk.X, padx=5, pady=3)

        questions = group["questions"]
        answer_vars = []
        answers = []

        for q in questions:
            q_num = q["number"]
            prompt = q["prompt"]
            options = q["options"]
            correct = q["answer"]

            q_frame = tk.Frame(frame)
            q_frame.pack(fill=tk.X, padx=5, pady=4)

            tk.Label(
                q_frame,
                text=f"{q_num}. {prompt}",
                font=("Arial", 10, "bold"),
                wraplength=360,
                justify="left",
                anchor="w",
            ).pack(fill=tk.X, pady=(0, 2))

            var = tk.StringVar()
            answer_vars.append(var)
            answers.append(correct)

            # từng option A-D
            for opt in options:
                key = opt["key"]
                text = opt["text"]
                rb = tk.Radiobutton(
                    q_frame,
                    text=f"{key}. {text}",
                    variable=var,
                    value=key,
                    font=("Arial", 10),
                    anchor="w",
                    justify="left",
                    wraplength=360,
                )
                rb.pack(fill=tk.X, padx=15, pady=1)

        self.group_states.append(
            {
                "type": "multiple_choice_single",
                "answer_vars": answer_vars,
                "answers": answers,
            }
        )

    # ============================================================
    # 4) CHẤM BÀI
    # ============================================================

    def check_all(self):
        total_questions = 0
        total_correct = 0
        total_unanswered = 0

        for g in self.group_states:
            gtype = g["type"]
            vars_ = g["answer_vars"]
            answers = g["answers"]

            total_questions += len(answers)

            for idx, var in enumerate(vars_):
                user_val = (var.get() or "").strip()
                if not user_val:
                    total_unanswered += 1
                    continue

                correct = answers[idx]

                # so sánh không phân biệt hoa thường
                if user_val.upper() == str(correct).upper():
                    total_correct += 1

        if total_questions == 0:
            return

        if total_correct == total_questions and total_unanswered == 0:
            self.completed = True
            self.feedback_label.config(
                text=f"Tuyệt vời! Bạn đã làm đúng toàn bộ {total_correct}/{total_questions} câu. ✅",
                fg="green",
            )
            if self.on_completed:
                self.on_completed()
            self.root.destroy()
        else:
            self.completed = False
            self.feedback_label.config(
                text=(
                    f"Bạn làm đúng {total_correct}/{total_questions} câu "
                    f"(bỏ trống {total_unanswered}).\n"
                    "Hãy xem lại passage và chỉnh sửa câu trả lời."
                ),
                fg="red",
            )

    # ============================================================
    # 5) SWITCH & ANTI-ESCAPE
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
        
    def start_free_focus(self, event=None):
        """Tạm tắt ép focus (dùng khi user mở combobox, menu, v.v.)"""
        self.disable_force_focus = True

    def end_free_focus(self, event=None):
        """Bật lại ép focus sau khi user chọn xong"""
        self.disable_force_focus = False
        # gọi lại force_focus nhẹ nhàng sau 200ms nếu cần
        self.root.after(200, self.force_focus)     

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
