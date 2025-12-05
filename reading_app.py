# reading_app.py
import tkinter as tk
from tkinter import messagebox


class ReadingApp:
    def __init__(self, root: tk.Toplevel,
                 on_completed=None,
                 on_request_switch=None):
        """
        root: Toplevel dùng riêng cho Reading
        on_completed: callback khi hoàn thành bài reading
        on_request_switch: callback khi bấm 'Chuyển sang luyện từ vựng'
        """
        self.root = root
        self.on_completed = on_completed
        self.on_request_switch = on_request_switch

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

        self.build_ui()

    # ---------- UI ----------

    def build_ui(self):
        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=40)

        title = tk.Label(
            self.main_frame,
            text="Reading Practice",
            font=("Arial", 26, "bold")
        )
        title.pack(pady=10)

        info = tk.Label(
            self.main_frame,
            text="Đọc đoạn văn bên dưới và trả lời các câu hỏi.\n"
                 "Hoàn thành bài reading để mở khóa phần này.",
            font=("Arial", 14)
        )
        info.pack(pady=5)

        # Đoạn văn
        passage_frame = tk.LabelFrame(
            self.main_frame, text="Đoạn văn", font=("Arial", 12, "bold")
        )
        passage_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        passage_text = (
            "Tom is a software engineer who wants to improve his English.\n"
            "Every morning, he spends 20 minutes reading English articles\n"
            "about technology and psychology. In the evening, he uses an\n"
            "app to review new vocabulary and practice writing sentences.\n\n"
            "After three months, Tom feels more confident when reading\n"
            "technical documents at work and communicating with his\n"
            "international colleagues."
        )

        self.passage_box = tk.Text(
            passage_frame, font=("Arial", 12),
            wrap="word", height=10
        )
        self.passage_box.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.passage_box.insert("1.0", passage_text)
        self.passage_box.config(state="disabled")

        # Câu hỏi
        question_frame = tk.LabelFrame(
            self.main_frame, text="Câu hỏi", font=("Arial", 12, "bold")
        )
        question_frame.pack(fill=tk.X, pady=10)

        tk.Label(
            question_frame,
            text="1. What does Tom do every morning to improve his English?",
            font=("Arial", 11),
            wraplength=900,
            justify="left"
        ).grid(row=0, column=0, sticky="w", padx=5, pady=3)

        self.q1_entry = tk.Entry(question_frame, font=("Arial", 11), width=80)
        self.q1_entry.grid(row=1, column=0, sticky="w", padx=5, pady=3)

        tk.Label(
            question_frame,
            text="2. How does Tom feel after three months?",
            font=("Arial", 11),
            wraplength=900,
            justify="left"
        ).grid(row=2, column=0, sticky="w", padx=5, pady=3)

        self.q2_entry = tk.Entry(question_frame, font=("Arial", 11), width=80)
        self.q2_entry.grid(row=3, column=0, sticky="w", padx=5, pady=3)

        # Nút
        btn_frame = tk.Frame(self.main_frame)
        btn_frame.pack(pady=10)

        self.check_button = tk.Button(
            btn_frame, text="Chấm bài reading",
            font=("Arial", 13),
            command=self.check_reading
        )
        self.check_button.pack(side=tk.LEFT, padx=10)

        switch_btn = tk.Button(
            btn_frame, text="Chuyển sang luyện từ vựng",
            font=("Arial", 12),
            command=self.request_switch_to_vocab
        )
        switch_btn.pack(side=tk.LEFT, padx=10)

        self.emergency_button = tk.Button(
            btn_frame, text="Thoát khẩn cấp",
            font=("Arial", 11),
            command=self.emergency_exit
        )
        self.emergency_button.pack(side=tk.LEFT, padx=10)

        self.feedback_label = tk.Label(
            self.main_frame, text="", font=("Arial", 12)
        )
        self.feedback_label.pack(pady=5)

    # ---------- Logic chấm ----------

    def normalize(self, s: str) -> str:
        return " ".join(s.strip().lower().split())

    def check_reading(self):
        ans1 = self.normalize(self.q1_entry.get())
        ans2 = self.normalize(self.q2_entry.get())

        score = 0
        if "english articles" in ans1 or "reading english" in ans1:
            score += 1
        if "more confident" in ans2 or "feels more confident" in ans2:
            score += 1

        if score == 2:
            self.completed = True
            self.feedback_label.config(
                text="Tuyệt vời! Bạn đã trả lời đúng các câu hỏi reading. ✅",
                fg="green"
            )
            if self.on_completed:
                self.on_completed()
            # đóng cửa sổ reading sau khi hoàn thành
            self.root.destroy()
        else:
            self.feedback_label.config(
                text="Chưa chính xác hết. Hãy đọc lại đoạn văn và chỉnh sửa câu trả lời nhé.",
                fg="red"
            )

    # ---------- Switch section ----------

    def request_switch_to_vocab(self):
        if self.on_request_switch:
            self.on_request_switch()

    # ---------- Anti-escape ----------

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
        except:
            pass

    def emergency_exit(self):
        """
        Thoát khẩn cấp:
        - Tạm tắt cơ chế ép focus + topmost
        - Hiện hộp thoại xác nhận thoát
        - Nếu đồng ý -> đóng app
        - Nếu không -> khôi phục trạng thái khóa màn hình
        """
        # 1) TẠM TẮT FORCE FOCUS + TOPMOST TRƯỚC KHI MỞ MESSAGEBOX
        #    để tránh trường hợp messagebox bị giấu sau fullscreen.
        try:
            self.disable_force_focus = True  # để force_focus() không làm gì nữa
        except Exception:
            pass

        try:
            # hạ topmost xuống, để messagebox tự nổi lên đúng cách
            self.root.attributes("-topmost", False)
        except Exception:
            pass

        # 2) HIỆN HỘP THOẠI XÁC NHẬN
        try:
            ok = messagebox.askyesno(
                "Thoát khẩn cấp",
                "Thoát khẩn cấp chỉ nên dùng khi bị lỗi.\n"
                "Bạn có chắc chắn muốn thoát không?",
                parent=self.root  # ép parent là root hiện tại
            )
        except Exception as e:
            # Nếu vì lý do gì đó messagebox lỗi, ta cho thoát luôn để tránh kẹt
            print("Lỗi khi hiện messagebox emergency_exit:", e)
            ok = True

        # 3) XỬ LÝ THEO CÂU TRẢ LỜI
        if ok:
            # Người dùng xác nhận thoát -> destroy cửa sổ
            try:
                self.root.destroy()
            except Exception:
                pass
        else:
            # Người dùng chọn "Không" -> khôi phục trạng thái khóa màn hình
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
