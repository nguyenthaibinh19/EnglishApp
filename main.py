"""Dutch Guard — ép bản thân học tiếng Hà Lan mỗi ngày.

Mỗi buổi gồm hai phần: luyện từ vựng và luyện đọc. Chỉ khi xong cả hai thì
ứng dụng mới cho đóng.
"""

import tkinter as tk
from tkinter import messagebox, ttk

import config
import install
import setup_wizard
import ui_common
from progress import Progress
from quiz_app import VocabQuizApp
from reading_app import ReadingApp
from vocab_store import VocabStore


class StudyMasterApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(config.APP_NAME)

        self.store = VocabStore()
        self.progress = Progress()

        today = self.progress.today()
        # Học xong rồi thì trong ngày không bị bắt làm lại.
        self.vocab_done = len(today.get("correct", [])) >= config.QUIZ_TARGET_CORRECT
        self.reading_done = bool(today.get("reading_done"))

        self.vocab_window = None
        self.reading_window = None
        self._menu_hidden = False

        ui_common.apply_theme(root)
        self.guard = ui_common.ScreenGuard(root, on_close_attempt=self._on_close_root)

        self._build_ui()
        self._refresh_status()

    # ============================================================
    # Giao diện
    # ============================================================

    def _build_ui(self):
        backdrop = ttk.Frame(self.root)
        backdrop.pack(fill=tk.BOTH, expand=True)

        card = ttk.Frame(backdrop, padding=8)
        card.place(relx=0.5, rely=0.42, anchor="center")

        ttk.Label(card, text="Nederlands leren", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            card,
            text="Hoàn thành cả hai phần dưới đây thì ứng dụng mới cho phép thoát.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(4, 20))

        buttons = ttk.Frame(card)
        buttons.pack(anchor="w")

        self.vocab_button = ttk.Button(
            buttons, text="1. Luyện từ vựng", command=self.open_vocab_section
        )
        self.vocab_button.pack(side=tk.LEFT, ipadx=18, ipady=12)

        self.reading_button = ttk.Button(
            buttons, text="2. Luyện đọc", command=self.open_reading_section
        )
        self.reading_button.pack(side=tk.LEFT, padx=14, ipadx=18, ipady=12)

        self.status_label = ttk.Label(card, text="", style="H2.TLabel", justify="left")
        self.status_label.pack(anchor="w", pady=(28, 6))

        self.detail_label = ttk.Label(card, text="", style="Muted.TLabel", justify="left")
        self.detail_label.pack(anchor="w")

        ttk.Separator(card).pack(fill=tk.X, pady=20)

        ttk.Label(
            card,
            text=(
                f"Mục tiêu mỗi ngày: {config.QUIZ_TARGET_CORRECT} câu từ vựng đúng, "
                f"rồi một bài đọc trình độ {config.READING_LEVEL} do AI viết từ chính "
                "những từ bạn vừa ôn."
            ),
            style="Muted.TLabel",
            wraplength=640,
            justify="left",
        ).pack(anchor="w")

        self.warning_label = ttk.Label(
            card, text="", style="Muted.TLabel", foreground=ui_common.COLOR_WARN,
            wraplength=640, justify="left",
        )
        self.warning_label.pack(anchor="w", pady=8)

        ttk.Button(
            backdrop, text="Thoát khẩn cấp",
            style="Small.TButton", command=self.emergency_exit_all,
        ).place(relx=1.0, rely=1.0, x=-24, y=-24, anchor="se")

    def _refresh_status(self):
        summary = self.progress.summary()

        vocab_mark = "✔" if self.vocab_done else "✗"
        reading_mark = "✔" if self.reading_done else "✗"
        self.status_label.config(
            text=f"{vocab_mark} Từ vựng   •   {reading_mark} Bài đọc"
        )
        self.detail_label.config(
            text=(
                f"Hôm nay đã ôn {summary['asked_today']} từ "
                f"({summary['correct_today']} đúng, {summary['wrong_today']} cần ôn lại).\n"
                f"Kho từ vựng: {self.store.count()} từ • đã thuộc {summary['known_words']} từ."
            )
        )

        warnings = []
        if self.store.count() == 0:
            warnings.append(
                'vocab.json đang trống. Hãy thêm từ theo mẫu {"nl": "de fiets", "vi": "xe đạp"} '
                "hoặc dùng nút “Quản lý từ vựng” trong phần luyện từ."
            )
        if not config.ai_is_configured():
            if config.is_frozen():
                warnings.append("Chưa có API key. Hãy nhập key ở màn hình cài đặt để AI chấm câu và viết bài đọc.")
            else:
                warnings.append(
                    "Chưa có OPENAI_API_KEY trong file .env nên AI sẽ không chấm câu và "
                    "không tự viết bài đọc được."
                )
        self.warning_label.config(text="\n".join(warnings))

    # ============================================================
    # Mở từng phần
    # ============================================================

    def open_vocab_section(self):
        if self.vocab_window is not None and self.vocab_window.winfo_exists():
            self.vocab_window.lift()
            return

        self._hide_menu()
        self.vocab_window = tk.Toplevel(self.root)
        self.vocab_window.bind("<Destroy>", self._on_child_destroy, add="+")
        VocabQuizApp(
            self.vocab_window,
            store=self.store,
            progress=self.progress,
            on_completed=self._on_vocab_completed,
            on_request_switch=self._switch_to_reading,
            on_emergency=self.quit_all,
        )

    def open_reading_section(self):
        if self.reading_window is not None and self.reading_window.winfo_exists():
            self.reading_window.lift()
            return

        self._hide_menu()
        self.reading_window = tk.Toplevel(self.root)
        self.reading_window.bind("<Destroy>", self._on_child_destroy, add="+")
        ReadingApp(
            self.reading_window,
            store=self.store,
            progress=self.progress,
            on_completed=self._on_reading_completed,
            on_request_switch=self._switch_to_vocab,
            on_emergency=self.quit_all,
        )

    def _hide_menu(self):
        """Nhường màn hình cho cửa sổ luyện tập, menu fullscreen không che lên trên."""
        if self._menu_hidden:
            return
        self._menu_hidden = True
        self.guard.suspend()
        try:
            self.root.attributes("-fullscreen", False)
        except tk.TclError:
            pass
        self.root.withdraw()

    def _child_open(self) -> bool:
        for window in (self.vocab_window, self.reading_window):
            try:
                if window is not None and window.winfo_exists():
                    return True
            except tk.TclError:
                continue
        return False

    def _show_menu(self):
        if self._child_open() or not self._menu_hidden:
            return
        self._menu_hidden = False
        self.root.deiconify()
        if self.guard.enabled:
            try:
                self.root.attributes("-fullscreen", True)
            except tk.TclError:
                pass
        self.guard.resume()

    def _on_child_destroy(self, event):
        if event.widget not in (self.vocab_window, self.reading_window):
            return
        self.root.after(50, self._show_menu)

    def _close_window(self, window):
        if window is not None and window.winfo_exists():
            window.destroy()

    def _switch_to_reading(self):
        self._close_window(self.vocab_window)
        self.open_reading_section()

    def _switch_to_vocab(self):
        self._close_window(self.reading_window)
        self.open_vocab_section()

    # ============================================================
    # Hoàn thành
    # ============================================================

    def _on_vocab_completed(self):
        self.vocab_done = True
        self._refresh_status()
        self.root.after(200, self._check_all_completed)

    def _on_reading_completed(self):
        self.reading_done = True
        self._refresh_status()
        self.root.after(200, self._check_all_completed)

    def _check_all_completed(self):
        if not (self.vocab_done and self.reading_done):
            # Xong một phần thì mở luôn phần còn lại cho đỡ phải bấm.
            if self.vocab_done and not self.reading_done:
                self.open_reading_section()
            elif self.reading_done and not self.vocab_done:
                self.open_vocab_section()
            return

        summary = self.progress.summary()
        with self.guard.suspended():
            messagebox.showinfo(
                "Klaar voor vandaag!",
                f"Bạn đã xong cả từ vựng và bài đọc hôm nay.\n\n"
                f"Số từ đã ôn: {summary['asked_today']}\n"
                f"Tổng số từ đã thuộc: {summary['known_words']}\n\nTot morgen!",
                parent=self.root,
            )
        self.quit_all()

    # ============================================================
    # Thoát
    # ============================================================

    def _on_close_root(self):
        if self.vocab_done and self.reading_done:
            self.quit_all()
            return
        with self.guard.suspended():
            messagebox.showwarning(
                "Chưa hoàn thành",
                "Cần xong cả phần từ vựng và phần đọc trước khi thoát.\n"
                "Nếu app bị lỗi, hãy dùng nút “Thoát khẩn cấp”.",
                parent=self.root,
            )

    def emergency_exit_all(self):
        if self.guard.confirm_emergency_exit():
            self.quit_all()

    def quit_all(self):
        self.progress.save()
        for window in (self.vocab_window, self.reading_window):
            try:
                self._close_window(window)
            except tk.TclError:
                pass
        try:
            self.root.destroy()
        except tk.TclError:
            pass


def run_diagnostics():
    """`python main.py --check` — xem môi trường đã sẵn sàng chưa, không mở cửa sổ."""
    import importlib
    import sys

    print(f"{config.APP_NAME} — kiểm tra môi trường\n")
    print(f"Python  : {sys.version.split()[0]}")
    print(f"Đường dẫn: {sys.executable}")
    print(f"Dữ liệu : {config.data_dir()}")
    print(f"Bản đóng gói: {'có' if config.is_frozen() else 'không'}\n")

    for module, needed_for in (
        ("tkinter", "giao diện"),
        ("dotenv", "đọc file .env"),
        ("openai", "chấm câu và viết bài đọc"),
        ("PyPDF2", "đọc bài tự soạn dạng PDF"),
    ):
        try:
            importlib.import_module(module)
            print(f"  [ok] {module}")
        except ImportError:
            print(f"  [thiếu] {module} — cần cho {needed_for}")

    store = VocabStore()
    summary = Progress().summary()
    print(f"\nTừ vựng : {store.count()} từ trong vocab.json")
    duplicates = store.find_duplicates()
    if duplicates:
        print(f"  Trùng lặp: {', '.join(duplicates[:5])}")
    if config.ai_is_configured():
        key_status = "đã cấu hình"
    elif config.OPENAI_API_KEY:
        key_status = "đang là giá trị mẫu, hãy điền key thật vào .env"
    else:
        key_status = "chưa có — xem .env.example"
    print(f"API key : {key_status}")
    print(f"Model   : {config.OPENAI_MODEL}")
    print(f"Mục tiêu: {config.QUIZ_TARGET_CORRECT} câu đúng/ngày, bài đọc trình độ {config.READING_LEVEL}")
    print(f"Hôm nay : đã ôn {summary['asked_today']} từ, "
          f"bài đọc {'xong' if summary['reading_done'] else 'chưa xong'}")


def main():
    import sys

    if "--check" in sys.argv:
        run_diagnostics()
        return

    try:
        stay = install.prepare()
    except Exception as error:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Dutch Guard", f"Không cài được ứng dụng:\n{error}")
        root.destroy()
        return
    if not stay:
        return

    root = tk.Tk()
    if config.is_frozen() and not config.is_ready():
        if not setup_wizard.run(root):
            root.destroy()
            return

    StudyMasterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
