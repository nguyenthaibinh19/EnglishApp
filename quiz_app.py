# quiz_app.py
import tkinter as tk
from tkinter import messagebox
import random

from vocab_store import VocabStore

NUM_CORRECT_TO_EXIT = 3  # số câu đúng cần để thoát


class VocabGuardApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Vocab Guard")

        # full screen
        self.root.attributes("-fullscreen", True)

        # chặn đóng cửa sổ bằng nút X
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # store quản lý vocab.json
        self.store = VocabStore()

        if self.store.count() == 0:
            messagebox.showerror("Lỗi", "Không tìm thấy hoặc không có dữ liệu trong vocab.json")
            self.root.destroy()
            return

        self.correct_count = 0
        self.current_index = None
        self.last_index = None  # để tránh lặp lại đúng câu trước đó

        # quản lý cửa sổ từ vựng
        self.vocab_window = None

        self.build_ui()
        self.update_progress_label()
        self.next_question()

    # ---------- UI chính ----------

    def build_ui(self):
        frame = tk.Frame(self.root)
        frame.pack(expand=True)

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

    def update_progress_label(self):
        self.progress_label.config(
            text=f"Đúng: {self.correct_count} / Mục tiêu: {NUM_CORRECT_TO_EXIT}"
        )

    # ---------- Logic chọn câu hỏi, KHÔNG lặp lại câu trước ----------

    def next_question(self):
        vocab = self.store.all()
        if not vocab:
            messagebox.showerror("Lỗi", "Không còn từ vựng nào. Hãy thêm từ vựng trước.")
            return

        # chọn index mới khác với last_index (nếu có đủ 2 từ trở lên)
        if len(vocab) == 1:
            idx = 0
        else:
            while True:
                idx = random.randrange(len(vocab))
                if idx != self.last_index:
                    break

        self.current_index = idx
        self.last_index = idx

        item = vocab[self.current_index]
        vi = item.get("vi", "")

        self.question_label.config(
            text=f"Từ TIẾNG ANH nào có nghĩa là:\n\n\"{vi}\"\n\n(Hãy gõ tiếng Anh, ví dụ: apple, improve...)"
        )
        self.answer_entry.delete(0, tk.END)
        self.answer_entry.focus()
        self.feedback_label.config(text="")

    @staticmethod
    def normalize(s: str) -> str:
        return s.strip().lower()

    def check_answer(self, event=None):
        vocab = self.store.all()
        if self.current_index is None or not vocab:
            return

        item = vocab[self.current_index]

        user_answer = self.normalize(self.answer_entry.get())
        correct_answer = self.normalize(item.get("en", ""))

        if not user_answer:
            self.feedback_label.config(text="Bạn chưa nhập gì cả!", fg="red")
            return

        if user_answer == correct_answer:
            self.correct_count += 1
            self.update_progress_label()
            remaining = NUM_CORRECT_TO_EXIT - self.correct_count

            if remaining <= 0:
                self.feedback_label.config(
                    text=f"ĐÚNG! Bạn đã hoàn thành {self.correct_count} / {NUM_CORRECT_TO_EXIT} câu. Mở khóa thành công!",
                    fg="green",
                )
                messagebox.showinfo("Hoàn thành", "Quá giỏi! Bạn đã trả lời đủ số câu.")
                self.root.destroy()
            else:
                self.feedback_label.config(
                    text=f"ĐÚNG! Bạn đã đúng {self.correct_count} câu. Còn {remaining} câu nữa.",
                    fg="green",
                )
                self.next_question()
        else:
            self.feedback_label.config(
                text=f"SAI. Đáp án đúng là: {item.get('en', '')}",
                fg="red",
            )
            # hỏi câu khác (vẫn tránh lặp câu vừa sai)
            self.next_question()

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
        if self.vocab_window is not None and tk.Toplevel.winfo_exists(self.vocab_window):
            self.vocab_window.lift()
            return

        self.vocab_window = tk.Toplevel(self.root)
        self.vocab_window.title("Quản lý từ vựng")
        self.vocab_window.geometry("700x400")
        self.vocab_window.grab_set()

        left_frame = tk.Frame(self.vocab_window)
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

        right_frame = tk.Frame(self.vocab_window)
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

        btn_close = tk.Button(right_frame, text="Đóng", command=self.close_vocab_window)
        btn_close.grid(row=3, column=1, pady=5, sticky="ew")

        note_label = tk.Label(
            right_frame,
            text="Tip: Chọn 1 dòng bên trái để sửa.\nThêm/sửa sẽ tự lưu vào vocab.json.",
            font=("Arial", 9),
            fg="gray",
            justify="left",
        )
        note_label.grid(row=4, column=0, columnspan=2, pady=10, sticky="w")

        self.refresh_vocab_listbox()

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
        # thay đổi dữ liệu → reset last_index để tránh lỗi index
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
        if self.vocab_window is not None:
            self.vocab_window.destroy()
            self.vocab_window = None

        if self.store.count() == 0:
            messagebox.showerror("Lỗi", "Không còn từ vựng nào. Hãy thêm từ trước khi tiếp tục.")
        else:
            self.next_question()
            self.answer_entry.focus()
