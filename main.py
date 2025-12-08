# main.py
import tkinter as tk
from tkinter import messagebox

from quiz_app import VocabGuardApp
from reading_app import ReadingApp


class StudyMasterApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Study English App")

        self.vocab_done = False
        self.reading_done = False

        self.vocab_window = None
        self.reading_window = None

        self.build_menu_ui()

        # Chặn đóng root nếu chưa xong cả 2
        self.root.protocol("WM_DELETE_WINDOW", self.on_close_root)
        # emergency exit
        self.status_label = tk.Label(
            self.menu_frame,
            text="Trạng thái: Chưa hoàn thành phần nào.",
            font=("Arial", 12),
            fg="blue"
        )
        self.status_label.pack(pady=10)

        # ===== NÚT THOÁT KHẨN CẤP CHO MAIN =====
        emergency_btn = tk.Button(
            self.menu_frame,
            text="Thoát khẩn cấp (tắt toàn bộ ứng dụng)",
            font=("Arial", 11),
            command=self.emergency_exit_all
        )
        emergency_btn.pack(pady=5)


    # ---------- UI menu chính ----------

    def build_menu_ui(self):
        self.menu_frame = tk.Frame(self.root)
        self.menu_frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=40)

        title = tk.Label(
            self.menu_frame,
            text="Chọn chế độ luyện tập",
            font=("Arial", 24, "bold")
        )
        title.pack(pady=10)

        desc = tk.Label(
            self.menu_frame,
            text=(
                "Bạn cần hoàn thành cả 2 phần:\n"
                "- Luyện từ vựng (đúng đủ số câu)\n"
                "- Luyện Reading (hoàn thành bài đọc)\n"
                "→ Sau đó ứng dụng mới cho phép thoát."
            ),
            font=("Arial", 13),
            justify="left"
        )
        desc.pack(pady=10)

        btn_frame = tk.Frame(self.menu_frame)
        btn_frame.pack(pady=10)

        vocab_btn = tk.Button(
            btn_frame,
            text="Luyện từ vựng",
            font=("Arial", 14),
            width=18,
            command=self.open_vocab_section
        )
        vocab_btn.pack(side=tk.LEFT, padx=10)

        reading_btn = tk.Button(
            btn_frame,
            text="Luyện Reading",
            font=("Arial", 14),
            width=18,
            command=self.open_reading_section
        )
        reading_btn.pack(side=tk.LEFT, padx=10)

        self.status_label = tk.Label(
            self.menu_frame,
            text="Trạng thái: Chưa hoàn thành phần nào.",
            font=("Arial", 12),
            fg="blue"
        )
        self.status_label.pack(pady=10)

    def update_status_label(self):
        status_parts = []
        if self.vocab_done:
            status_parts.append("✔ Từ vựng đã hoàn thành")
        else:
            status_parts.append("✗ Từ vựng CHƯA xong")

        if self.reading_done:
            status_parts.append("✔ Reading đã hoàn thành")
        else:
            status_parts.append("✗ Reading CHƯA xong")

        self.status_label.config(text=" | ".join(status_parts))

    # ---------- Vocab section ----------

    def open_vocab_section(self):
        # Nếu đã mở rồi, chỉ bring to front
        if self.vocab_window and self.vocab_window.winfo_exists():
            self.vocab_window.lift()
            return

        self.vocab_window = tk.Toplevel(self.root)
        VocabGuardApp(
            self.vocab_window,
            on_completed=self.on_vocab_completed,
            on_request_switch=self.switch_to_reading_from_vocab
        )

    def on_vocab_completed(self):
        self.vocab_done = True
        self.update_status_label()
        self.check_all_completed()

    def switch_to_reading_from_vocab(self):
        # Đóng cửa sổ vocab rồi mở reading
        if self.vocab_window and self.vocab_window.winfo_exists():
            self.vocab_window.destroy()
        self.open_reading_section()

    # ---------- Reading section ----------

    def open_reading_section(self):
        if self.reading_window and self.reading_window.winfo_exists():
            self.reading_window.lift()
            return

        self.reading_window = tk.Toplevel(self.root)
        ReadingApp(
            self.reading_window,
            on_completed=self.on_reading_completed,
            on_request_switch=self.switch_to_vocab_from_reading
        )

    def on_reading_completed(self):
        self.reading_done = True
        self.update_status_label()
        self.check_all_completed()

    def switch_to_vocab_from_reading(self):
        if self.reading_window and self.reading_window.winfo_exists():
            self.reading_window.destroy()
        self.open_vocab_section()

    # ---------- Điều kiện thoát app ----------

    def check_all_completed(self):
        if self.vocab_done and self.reading_done:
            messagebox.showinfo(
                "Hoàn thành",
                "Bạn đã hoàn thành cả Luyện Từ Vựng và Luyện Reading.\nỨng dụng sẽ thoát."
            )
            self.root.destroy()

    def on_close_root(self):
        if self.vocab_done and self.reading_done:
            self.root.destroy()
        else:
            messagebox.showwarning(
                "Chưa hoàn thành",
                "Bạn cần hoàn thành cả Luyện Từ Vựng và Luyện Reading trước khi thoát.\n"
                "Nếu gặp lỗi, hãy dùng nút 'Thoát khẩn cấp' trong từng chế độ."
            )
    # ---------- Emergency exit toàn bộ app ----------
    def emergency_exit_all(self):
        """
        Thoát khẩn cấp toàn bộ app:
        - Bỏ qua điều kiện phải hoàn thành đủ 2 phần
        - Đóng mọi cửa sổ con
        - Destroy root
        """
        ok = messagebox.askyesno(
            "Thoát khẩn cấp",
            "Nút này sẽ đóng TOÀN BỘ ứng dụng ngay lập tức,\n"
            "kể cả khi bạn chưa hoàn thành đủ cả Từ vựng và Reading.\n\n"
            "Bạn có chắc chắn muốn thoát không?"
        )
        if not ok:
            return

        # Thử đóng các cửa sổ con nếu còn tồn tại
        for win in (self.vocab_window, self.reading_window):
            try:
                if win is not None and win.winfo_exists():
                    win.destroy()
            except Exception:
                pass

        # Đóng cửa sổ chính
        try:
            self.root.destroy()
        except Exception:
            pass


if __name__ == "__main__":
    root = tk.Tk()
    app = StudyMasterApp(root)
    root.mainloop()
