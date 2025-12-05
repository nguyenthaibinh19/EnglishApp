# quiz_app.py
import tkinter as tk
from tkinter import messagebox
import random
import re  # <-- để xử lý bỏ (N), (adj)...
from vocab_store import VocabStore

NUM_CORRECT_TO_EXIT = 10  # số câu đúng cần để thoát


class VocabGuardApp:
    def __init__(self, root: tk.Tk):
        self.practice_frame = None
        self.root = root
        self.root.title("Vocab Guard")

        # full screen + luôn nằm trên cùng
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)

        # chặn đóng cửa sổ bằng nút X + Alt+F4
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.bind_all("<Alt-F4>", self.disable_alt_f4)

        # nếu mất focus (Alt+Tab ra chỗ khác) thì kéo cửa sổ quay lại
        self.root.bind("<FocusOut>", self.on_focus_out)

        # store quản lý vocab.json
        self.store = VocabStore()

        if self.store.count() == 0:
            messagebox.showerror("Lỗi", "Không tìm thấy hoặc không có dữ liệu trong vocab.json")
            self.root.destroy()
            return

        # ---------- STATE CHUNG CHO QUIZ ----------
        self.correct_count = 0
        self.total_count = 0              # NEW: tổng số câu đã trả lời
        self.current_index = None
        self.last_index = None  # để tránh lặp lại đúng câu trước đó

        # ---------- STATE CHO CƠ CHẾ DUOLINGO STYLE ----------
        vocab = self.store.all()
        self.total_words = len(vocab)         # NEW: tổng số từ hiện có

        # NEW: danh sách index sẽ được hỏi trong "vòng hiện tại"
        # (ban đầu là tất cả từ, sau này sẽ thay bằng các từ sai, v.v.)
        self.remaining_indices = list(range(self.total_words))
        random.shuffle(self.remaining_indices)

        # NEW: lưu lại các index mà người dùng đã trả lời sai ít nhất 1 lần
        self.wrong_indices = []

        # NEW: dùng cho chế độ "sai là bị bắt đặt câu ngay"
        # nếu != None nghĩa là đang bị ép practice từ này
        self.pending_practice_index = None
        self.practice_mode = None   # ví dụ: None hoặc "forced_from_quiz"

        # ---------- QUẢN LÝ CỬA SỔ TỪ VỰNG ----------
        self.vocab_frame = None
        
        # ---------- XÂY UI + BẮT ĐẦU QUIZ ----------
        self.build_ui()
        self.update_progress_label()
        self.next_question()

    # ---------- UI chính ----------

    def build_ui(self):
        # lưu frame chính để sau này pack_forget()
        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(expand=True)

        frame = self.main_frame

        self.info_label = tk.Label(
            frame,
            text=f"Cần trả lời đúng {NUM_CORRECT_TO_EXIT} câu để mở khóa",
            font=("Arial", 20),
        )
        self.info_label.pack(pady=10)

        self.progress_label = tk.Label(
            frame,
            text="Đúng: 0 / 0",
            font=("Arial", 18),
        )
        self.progress_label.pack(pady=5)

        self.question_label = tk.Label(
            frame,
            text="",
            font=("Arial", 24),
            wraplength=900,
            justify="center",
        )
        self.question_label.pack(pady=20)

        self.answer_entry = tk.Entry(frame, font=("Arial", 20), width=30)
        self.answer_entry.pack(pady=10)
        self.answer_entry.bind("<Return>", self.check_answer)

        self.feedback_label = tk.Label(frame, text="", font=("Arial", 16))
        self.feedback_label.pack(pady=10)

        btn_frame = tk.Frame(frame)
        btn_frame.pack(pady=20)

        self.submit_button = tk.Button(
            btn_frame, text="Trả lời", font=("Arial", 16), command=self.check_answer
        )
        self.submit_button.pack(side=tk.LEFT, padx=10)

        manage_button = tk.Button(
            btn_frame,
            text="Quản lý từ vựng",
            font=("Arial", 12),
            command=self.open_vocab_manager,
        )
        manage_button.pack(side=tk.LEFT, padx=10)

        self.exit_button = tk.Button(
            btn_frame,
            text="Thoát khẩn cấp",
            font=("Arial", 12),
            command=self.emergency_exit,
        )
        self.exit_button.pack(side=tk.LEFT, padx=10)

        practice_button = tk.Button(
            btn_frame,
            text="Đặt câu ví dụ",
            font=("Arial", 12),
            command=self.prepare_practice
        )
        practice_button.pack(side=tk.LEFT, padx=10)

    def _setup_practice_for_current_index(self):
        vocab = self.store.all()
        if self.current_index is None or not vocab:
            return
        word_raw = vocab[self.current_index]["en"]
        self.current_target_word = self.clean_en(word_raw)
        # nếu có label hiển thị từ trong practice_frame thì update ở show_practice_frame
        
    def prepare_practice(self):
        """
        Người dùng tự bấm nút 'Đặt câu ví dụ' (practice tự nguyện).
        """
        vocab = self.store.all()
        if self.current_index is None or not vocab:
            return

        self.practice_mode = "free"
        self._setup_practice_for_current_index()
        self.show_practice_frame()

    def start_forced_practice(self):
        """
        Bị ép practice sau khi trả lời SAI trong quiz.
        Dùng CHÍNH self.current_index (từ vừa sai).
        """
        vocab = self.store.all()
        if self.current_index is None or not vocab:
            return

        self.practice_mode = "forced_from_quiz"
        self._setup_practice_for_current_index()
        self.show_practice_frame()

    def update_progress_label(self):
        self.progress_label.config(
            text=f"Đúng: {self.correct_count} / Mục tiêu: {NUM_CORRECT_TO_EXIT}"
        )

    def _show_only(self, frame_to_show):
        """
        Ẩn hết các frame khác, chỉ hiển thị frame_to_show.
        Đảm bảo không bao giờ có trạng thái 'trắng bóc'.
        """
        for f in (getattr(self, "main_frame", None),
                  getattr(self, "practice_frame", None),
                  getattr(self, "vocab_frame", None)):
            if f is not None and f is not frame_to_show:
                f.pack_forget()

        if frame_to_show is not None:
            frame_to_show.pack(fill=tk.BOTH, expand=True)

    def show_practice_frame(self):
        # Tạo frame nếu chưa có
        if self.practice_frame is None:
            self.practice_frame = tk.Frame(self.root)
            
            # LƯU label vào thuộc tính để còn update text về sau
            self.practice_word_label = tk.Label(
                self.practice_frame,
                text="",   # set sau
                font=("Arial", 16, "bold")
            )
            self.practice_word_label.pack(pady=10)

            tk.Label(
                self.practice_frame,
                text="Hãy đặt 1 câu tiếng Anh sử dụng từ trên:",
                font=("Arial", 12)
            ).pack()

            self.practice_input = tk.Text(
                self.practice_frame, height=4, width=80, font=("Arial", 12)
            )
            self.practice_input.pack(pady=10)

            self.result_box = tk.Text(
                self.practice_frame, height=10, width=80,
                font=("Arial", 12), wrap="word"
            )
            self.result_box.config(state="disabled")
            self.result_box.pack(pady=10)

            tk.Button(
                self.practice_frame, text="Chấm câu",
                font=("Arial", 14), command=self.grade_sentence
            ).pack(pady=5)

            tk.Button(
                self.practice_frame, text="Quay về bài học",
                font=("Arial", 12), command=self.return_to_quiz
            ).pack(pady=5)

        # ------------- CẬP NHẬT UI MỖI LẦN MỞ PRACTICE -------------
        # Cập nhật từ cần dùng theo self.current_target_word MỚI
        self.practice_word_label.config(
            text=f"Từ cần dùng: {self.current_target_word}"
        )

        # Xóa input cũ
        self.practice_input.delete("1.0", "end")

        # Xóa feedback cũ
        self.result_box.config(state="normal")
        self.result_box.delete("1.0", "end")
        self.result_box.config(state="disabled")

        # Hiện frame practice, ẩn frame khác
        self._show_only(self.practice_frame)

        # Focus vào ô nhập câu
        self.practice_input.focus_set()

    #----------- AI Window ----------
    def open_practice_window(self):
        vocab = self.store.all()
        if self.current_index is None:
            return

        word_raw = vocab[self.current_index]["en"]
        target_word = self.clean_en(word_raw)

        win = tk.Toplevel(self.root)
        win.title(f"Đặt câu với: {target_word}")
        win.geometry("600x400")
        win.grab_set()

        tk.Label(win, text=f"Từ cần dùng: {target_word}", font=("Arial", 14, "bold")).pack(pady=10)

        tk.Label(win, text="Hãy đặt 1 câu tiếng Anh sử dụng từ trên:", font=("Arial", 12)).pack()

        input_box = tk.Text(win, height=4, width=60, font=("Arial", 12))
        input_box.pack(pady=10)

        result_box = tk.Text(win, font=("Arial", 12), height=10, width=60, wrap="word")
        result_box.config(state="disabled")  # khóa edit
        result_box.pack(pady=10)

        def submit_sentence():
            from ai_teacher import check_sentence

            user_sentence = input_box.get("1.0", "end").strip()
            if not user_sentence:
                result_box.config(text="Bạn chưa nhập câu!", fg="red")
                return

            try:
                result = check_sentence(target_word, user_sentence)
            except Exception as e:
                result_box.config(text=f"Lỗi API: {e}", fg="red")
                return

            feedback = (
                f"Đúng ngữ cảnh: {'✔' if result['is_correct_usage'] else '❌'}\n"
                f"Điểm: {result['score']:.2f}\n\n"
                f"Nhận xét:\n{result['feedback_vi']}\n\n"
                f"Gợi ý tốt hơn:\n{result['suggested_sentence']}"
            )

            result_box.config(state="normal")
            result_box.delete("1.0", "end")
            result_box.insert("1.0", feedback)
            result_box.config(state="disabled")

        tk.Button(win, text="Chấm câu", font=("Arial", 12), command=submit_sentence).pack(pady=5)

        tk.Button(win, text="Đóng", font=("Arial", 12), command=win.destroy).pack(pady=5)

    def grade_sentence(self):
        from ai_teacher import check_sentence

        user_sentence = self.practice_input.get("1.0", "end").strip()
        if not user_sentence:
            self.result_box.config(state="normal")
            self.result_box.delete("1.0", "end")
            self.result_box.insert("1.0", "Bạn chưa nhập câu!")
            self.result_box.config(state="disabled")
            return

        try:
            result = check_sentence(self.current_target_word, user_sentence)
        except Exception as e:
            self.result_box.config(state="normal")
            self.result_box.delete("1.0", "end")
            self.result_box.insert("1.0", f"Lỗi API: {e}")
            self.result_box.config(state="disabled")
            return

        is_correct = bool(result.get("is_correct_usage", False))
        score = result.get("score", 0.0)
        feedback_vi = result.get("feedback_vi", "")
        suggested = result.get("suggested_sentence", "")

        feedback = (
            f"Đúng ngữ cảnh: {'✔' if is_correct else '❌'}\n"
            f"Điểm: {score:.2f}\n\n"
            f"Nhận xét:\n{feedback_vi}\n\n"
            f"Gợi ý tốt hơn:\n{suggested}"
        )

        self.result_box.config(state="normal")
        self.result_box.delete("1.0", "end")
        self.result_box.insert("1.0", feedback)
        self.result_box.config(state="disabled")

        # Nếu đây là câu bị phạt và AI chấm ĐÚNG → quay lại quiz + sang câu mới
        if is_correct and getattr(self, "practice_mode", None) == "forced_from_quiz":
            self.practice_mode = None

            def _back_to_quiz():
                self.return_to_quiz()   # ẩn practice_frame, show main_frame
                self.next_question()    # hỏi câu mới

            self.root.after(1500, _back_to_quiz)
        else:
            # free practice hoặc vẫn sai -> ở lại màn practice
            pass

    def return_to_quiz(self):
        self._show_only(self.main_frame)

    # ---------- Chặn/giảm thiểu phím tắt ----------
    def open_practice_window(self):
        # TẠM TẮT CHẾ ĐỘ KHÓA MÀN HÌNH
        self.root.attributes("-topmost", False)
        self.disable_force_focus = True

        vocab = self.store.all()
        if self.current_index is None:
            return

        word_raw = vocab[self.current_index]["en"]
        target_word = self.clean_en(word_raw)

        win = tk.Toplevel(self.root)
        win.title(f"Đặt câu với: {target_word}")
        win.geometry("600x400")
        win.grab_set()  # khóa focus trong cửa sổ này, không ra desktop được

        # ===== UI =====
        tk.Label(win, text=f"Từ cần dùng: {target_word}",
                font=("Arial", 14, "bold")).pack(pady=10)

        tk.Label(win, text="Hãy đặt 1 câu tiếng Anh sử dụng từ trên:",
                font=("Arial", 12)).pack()

        input_box = tk.Text(win, height=4, width=60, font=("Arial", 12))
        input_box.pack(pady=10)

        result_box = tk.Text(win, font=("Arial", 12), height=10, width=60, wrap="word")
        result_box.config(state="disabled")  # khóa edit
        result_box.pack(pady=10)

        # Submit
        def submit_sentence():
            from ai_teacher import check_sentence

            user_sentence = input_box.get("1.0", "end").strip()
            if not user_sentence:
                result_box.config(state="normal")
                return

            try:
                result = check_sentence(target_word, user_sentence)
            except Exception as e:
                result_box.config(text=f"Lỗi API: {e}", fg="red")
                return

            feedback = (
                f"Đúng ngữ cảnh: {'✔' if result['is_correct_usage'] else '❌'}\n"
                f"Điểm: {result['score']:.2f}\n\n"
                f"Nhận xét:\n{result['feedback_vi']}\n\n"
                f"Gợi ý tốt hơn:\n{result['suggested_sentence']}"
            )
            result_box.config(state="normal")
            result_box.delete("1.0", "end")
            result_box.insert("1.0", feedback)
            result_box.config(state="disabled")

        def close_window():
            win.destroy()
            # BẬT LẠI KHÓA MÀN HÌNH
            self.root.attributes("-topmost", True)
            self.disable_force_focus = False
            self.force_focus()  # gọi lại focus nếu bạn muốn

        tk.Button(win, text="Chấm câu", font=("Arial", 12),
                command=submit_sentence).pack(pady=5)

        tk.Button(win, text="Đóng", font=("Arial", 12),
                command=close_window).pack(pady=5)

    def disable_alt_f4(self, event=None):
        # Chặn Alt+F4
        return "break"

    def on_focus_out(self, event=None):
        # Nếu người dùng Alt+Tab ra ngoài, kéo app quay lại
        # (không đảm bảo 100%, nhưng gây "khó chịu" đủ mạnh để họ ở lại học 😈)
        self.root.after(100, self.force_focus)

    def force_focus(self):
        if getattr(self, "disable_force_focus", False):
            return  # đang mở popup -> KHÔNG ép focus
        try:
            self.root.attributes("-topmost", True)
            self.root.focus_force()
            self.root.lift()
        except:
            pass


    # ---------- Xử lý chuẩn hóa từ, bỏ (N), (adj)... ----------


    def clean_en(self, s: str) -> str:
        """
        Chuẩn hóa phần tiếng Anh:
        - Bỏ các tag loại từ trong ngoặc: (N), (Adj), (Verb), (phrV), (idiom)...
        ở BẤT KỲ vị trí nào trong chuỗi.
        - Bỏ dấu '+' dùng làm ký hiệu cấu trúc.
        - Đưa về lowercase + gọn khoảng trắng.
        Ví dụ:
            'apple (N)'                  -> 'apple'
            'go up (phrV)'               -> 'go up'
            'rule out (Verb) + something' -> 'rule out something'
            'break down (phrv) (N)'      -> 'break down'
        """
        if not s:
            return ""

        # Chuẩn trước
        s = s.strip()

        # 1) Bỏ các dấu '+' dùng để mô tả cấu trúc: "verb + object"...
        #    'rule out (Verb) + something' -> 'rule out (Verb) something'
        s = re.sub(r"\s*\+\s*", " ", s)

        # 2) Bỏ các (tag) loại từ ở BẤT KỲ vị trí nào
        #    Bạn có thể thêm/bớt tag trong nhóm dưới đây tùy bộ từ vựng.
        tag_pattern = r"\s*\((?:n|noun|v|verb|adj|adjective|adv|adverb|phrv|phr\s*verb|idiom|prep|preposition)\)\s*"
        s = re.sub(tag_pattern, " ", s, flags=re.IGNORECASE)

        # 3) Phòng hờ: nếu vẫn còn ngoặc ở CUỐI chuỗi thì xóa nốt
        #    (vẫn giữ behavior cũ của bạn)
        s = re.sub(r"\s*\([^)]*\)\s*$", "", s)

        # 4) Gọn khoảng trắng + lowercase
        s = re.sub(r"\s+", " ", s)
        return s.strip().lower()

    def normalize_answer(self, s: str) -> str:
        """
        Chuẩn hóa câu trả lời: trim + lower + bỏ (N), (adj) nếu có.
        """
        return self.clean_en(s)

    # ---------- Logic chọn câu hỏi, KHÔNG lặp lại câu trước ----------

    def next_question(self):
        vocab = self.store.all()
        if not vocab:
            messagebox.showerror("Lỗi", "Không còn từ vựng nào. Hãy thêm từ vựng trước.")
            return

        # Nếu vocab thay đổi (thêm/xóa từ), reset lại tracking
        if self.total_words != len(vocab):
            self.total_words = len(vocab)
            self.remaining_indices = list(range(self.total_words))
            random.shuffle(self.remaining_indices)
            self.wrong_indices = []

        # Nếu đang có từ phải practice ép, không được nhảy câu mới
        if self.pending_practice_index is not None:
            return

        # Hết từ trong vòng hiện tại
        if not self.remaining_indices:
            if self.wrong_indices:
                # chuyển sang vòng ôn lại các từ đã sai
                self.remaining_indices = self.wrong_indices
                self.wrong_indices = []
                random.shuffle(self.remaining_indices)
                self.info_label.config(text="Đang ôn lại các từ bạn đã sai 🔁")
            else:
                # Không còn từ sai nữa -> bắt đầu vòng mới với toàn bộ từ
                self.remaining_indices = list(range(self.total_words))
                random.shuffle(self.remaining_indices)
                self.info_label.config(
                    text=f"Cần trả lời đúng {NUM_CORRECT_TO_EXIT} câu để mở khóa"
                )

        if not self.remaining_indices:
            self.question_label.config(text="Không còn từ vựng nào để hỏi.")
            return

        # Lấy index kế tiếp
        idx = self.remaining_indices.pop()

        # Giữ lại last_index nếu bạn còn dùng chỗ khác
        self.current_index = idx
        self.last_index = idx

        item = vocab[self.current_index]
        vi = item.get("vi", "")

        self.question_label.config(
            text=(
                f"Từ TIẾNG ANH nào có nghĩa là:\n\n"
                f"\"{vi}\"\n\n(Hãy gõ tiếng Anh, ví dụ: apple, improve...)"
            )
        )
        self.answer_entry.config(state="normal")
        self.submit_button.config(state="normal")
        self.answer_entry.delete(0, tk.END)
        self.answer_entry.focus()
        self.feedback_label.config(text="", fg="black")

    def check_answer(self, event=None):
        vocab = self.store.all()
        if self.current_index is None or not vocab:
            return

        item = vocab[self.current_index]

        raw_user_answer = self.answer_entry.get().strip()
        user_answer = self.normalize_answer(self.answer_entry.get())
        correct_answer = self.normalize_answer(item.get("en", ""))

        if not user_answer:
            self.feedback_label.config(text="Bạn chưa nhập gì cả!", fg="red")
            return

        if user_answer == correct_answer:
            # ---------- ĐÚNG ----------
            self.correct_count += 1
            self.update_progress_label()
            remaining = NUM_CORRECT_TO_EXIT - self.correct_count

            if remaining <= 0:
                self.feedback_label.config(
                    text=(
                        f"ĐÚNG! Bạn đã hoàn thành {self.correct_count} / "
                        f"{NUM_CORRECT_TO_EXIT} câu. Mở khóa thành công!"
                    ),
                    fg="green",
                )
                messagebox.showinfo("Hoàn thành", "Quá giỏi! Bạn đã trả lời đủ số câu.")
                self.root.destroy()
            else:
                self.feedback_label.config(
                    text=f"ĐÚNG! Bạn đã đúng {self.correct_count} câu. Còn {remaining} câu nữa.",
                    fg="green",
                )
                self.root.after(500, self.next_question)

        else:
            # ---------- SAI ----------
            correct_display = self.clean_en(item.get("en", ""))
            self.feedback_label.config(
                text=(
                    "SAI.\n"
                    f"Bạn trả lời: {raw_user_answer or '(trống)'}\n"
                    f"Đáp án đúng: {correct_display}\n\n"
                    "Bây giờ hãy đặt 1 câu ví dụ với từ này."
                ),
                fg="red",
            )

            # ghi nhớ từ sai để vòng sau hỏi lại
            if self.current_index not in self.wrong_indices:
                self.wrong_indices.append(self.current_index)

            # đánh dấu đang ở chế độ “bị phạt”
            self.practice_mode = "forced_from_quiz"

            # khóa input để bắt user đọc kỹ
            self.answer_entry.config(state="disabled")
            self.submit_button.config(state="disabled")

            # sau 3.5s thì chuyển sang màn đặt câu cho CHÍNH TỪ ĐANG SAI
            self.root.after(3500, self.after_showing_correct_answer)

    def after_showing_correct_answer(self):
        # mở lại input + nút trả lời
        self.answer_entry.config(state="normal")
        self.submit_button.config(state="normal")

        # Nếu đang ở chế độ bị phạt -> sang practice
        if getattr(self, "practice_mode", None) == "forced_from_quiz":
            self.start_forced_practice()
        else:
            # bình thường thì sang câu hỏi tiếp theo
            self.next_question()

        self.answer_entry.focus()

    def emergency_exit(self):
        ok = messagebox.askyesno(
            "Thoát khẩn cấp",
            "Thoát khẩn cấp chỉ nên dùng khi bị lỗi.\nBạn có chắc chắn muốn thoát không?",
        )
        if ok:
            self.root.destroy()

    def on_close(self):
        # Không làm gì để tránh tắt bằng nút X
        pass

    # ---------- Quản lý từ vựng (UI) ----------

    def open_vocab_manager(self):
        """
        Mở màn hình quản lý từ vựng dưới dạng frame (không dùng popup).
        Ẩn main_frame / practice_frame, chỉ hiển thị vocab_frame.
        """
        # Tạo frame nếu chưa có
        if self.vocab_frame is None:
            self.vocab_frame = tk.Frame(self.root)

            left_frame = tk.Frame(self.vocab_frame)
            left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

            tk.Label(left_frame, text="Danh sách từ:", font=("Arial", 12, "bold")).pack(anchor="w")

            list_frame = tk.Frame(left_frame)
            list_frame.pack(fill=tk.BOTH, expand=True)

            self.vocab_listbox = tk.Listbox(list_frame, font=("Arial", 11))
            self.vocab_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            scrollbar = tk.Scrollbar(list_frame, command=self.vocab_listbox.yview)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            self.vocab_listbox.config(yscrollcommand=scrollbar.set)

            self.vocab_listbox.bind("<<ListboxSelect>>", self.on_vocab_select)

            right_frame = tk.Frame(self.vocab_frame)
            right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=10)

            tk.Label(right_frame, text="Tiếng Anh:", font=("Arial", 11)).grid(row=0, column=0, sticky="w")
            self.en_entry = tk.Entry(right_frame, font=("Arial", 11), width=25)
            self.en_entry.grid(row=0, column=1, pady=5)

            tk.Label(right_frame, text="Tiếng Việt:", font=("Arial", 11)).grid(row=1, column=0, sticky="w")
            self.vi_entry = tk.Entry(right_frame, font=("Arial", 11), width=25)
            self.vi_entry.grid(row=1, column=1, pady=5)

            btn_add = tk.Button(right_frame, text="Thêm mới", command=self.add_vocab)
            btn_add.grid(row=2, column=0, pady=5, sticky="ew")

            btn_update = tk.Button(right_frame, text="Cập nhật", command=self.update_vocab)
            btn_update.grid(row=2, column=1, pady=5, sticky="ew")

            btn_delete = tk.Button(right_frame, text="Xóa", command=self.delete_vocab)
            btn_delete.grid(row=3, column=0, pady=5, sticky="ew")

            btn_close = tk.Button(right_frame, text="Quay lại luyện từ", command=self.close_vocab_window)
            btn_close.grid(row=3, column=1, pady=5, sticky="ew")

            note_label = tk.Label(
                right_frame,
                text="Tip: Chọn 1 dòng bên trái để sửa.\nThêm/sửa sẽ tự lưu vào vocab.json.",
                font=("Arial", 9),
                fg="gray",
                justify="left",
            )
            note_label.grid(row=4, column=0, columnspan=2, pady=10, sticky="w")

        # Cập nhật danh sách mỗi lần mở
        self.refresh_vocab_listbox()

        # Hiện frame vocab, ẩn frame khác
        self._show_only(self.vocab_frame)

    def refresh_vocab_listbox(self):
        self.vocab_listbox.delete(0, tk.END)
        for item in self.store.all():
            en = item.get("en", "")
            vi = item.get("vi", "")
            self.vocab_listbox.insert(tk.END, f"{en} - {vi}")

    def on_vocab_select(self, event):
        selection = self.vocab_listbox.curselection()
        if not selection:
            return
        index = selection[0]
        vocab = self.store.all()
        if 0 <= index < len(vocab):
            item = vocab[index]
            self.en_entry.delete(0, tk.END)
            self.en_entry.insert(0, item.get("en", ""))
            self.vi_entry.delete(0, tk.END)
            self.vi_entry.insert(0, item.get("vi", ""))

    def add_vocab(self):
        en = self.en_entry.get().strip()
        vi = self.vi_entry.get().strip()
        if not en or not vi:
            messagebox.showwarning("Thiếu dữ liệu", "Vui lòng nhập đầy đủ Tiếng Anh và Tiếng Việt.")
            return
        self.store.add(en, vi)
        self.refresh_vocab_listbox()
        self.en_entry.delete(0, tk.END)
        self.vi_entry.delete(0, tk.END)
        self.last_index = None

    def update_vocab(self):
        selection = self.vocab_listbox.curselection()
        if not selection:
            messagebox.showwarning("Chưa chọn", "Hãy chọn một từ ở danh sách bên trái để cập nhật.")
            return
        index = selection[0]
        en = self.en_entry.get().strip()
        vi = self.vi_entry.get().strip()
        if not en or not vi:
            messagebox.showwarning("Thiếu dữ liệu", "Vui lòng nhập đầy đủ Tiếng Anh và Tiếng Việt.")
            return
        self.store.update(index, en, vi)
        self.refresh_vocab_listbox()
        self.last_index = None

    def delete_vocab(self):
        selection = self.vocab_listbox.curselection()
        if not selection:
            messagebox.showwarning("Chưa chọn", "Hãy chọn một từ để xóa.")
            return
        index = selection[0]
        if self.store.count() <= 1:
            messagebox.showwarning("Không thể xóa", "Không thể xóa hết tất cả từ. Hãy để lại ít nhất 1 từ.")
            return

        vocab = self.store.all()
        item = vocab[index]
        ok = messagebox.askyesno(
            "Xóa từ",
            f"Bạn có chắc muốn xóa từ:\n{item.get('en', '')} - {item.get('vi', '')} ?",
        )
        if ok:
            self.store.delete(index)
            self.refresh_vocab_listbox()
            self.en_entry.delete(0, tk.END)
            self.vi_entry.delete(0, tk.END)
            self.last_index = None

    def close_vocab_window(self):
        # Quay lại màn quiz chính
        self._show_only(self.main_frame)

        if self.store.count() == 0:
            messagebox.showerror("Lỗi", "Không còn từ vựng nào. Hãy thêm từ trước khi tiếp tục.")
        else:
            self.next_question()
            self.answer_entry.focus()
