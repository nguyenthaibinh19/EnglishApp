"""Language Guard — mỗi lần mở máy, học các ngôn ngữ đã chọn.

Mỗi ngôn ngữ được tick cần đủ số câu từ vựng đúng và một bài đọc.
Ngôn ngữ không tick thì không phải làm. Xong hết mới đóng được app.
"""

import tkinter as tk
from tkinter import messagebox, ttk

import config
import dictionary
import install
import language_setup
import languages
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

        # Mỗi lần mở app tính lại từ đầu, không cộng dồn các lần mở trong ngày.
        self.session = {
            code: {"vocab": False, "reading": False} for code in languages.codes()
        }

        self.vocab_window = None
        self.reading_window = None
        self._menu_hidden = False
        self.row_status = {}
        self.row_buttons = {}

        ui_common.apply_theme(root)
        self.guard = ui_common.ScreenGuard(root, on_close_attempt=self._on_close_root)

        self._build_ui()
        self._refresh_status()
        self.root.after(300, self._ensure_missing_dictionaries)

    # ============================================================
    # Giao diện
    # ============================================================

    def _build_ui(self):
        backdrop = ttk.Frame(self.root)
        backdrop.pack(fill=tk.BOTH, expand=True)

        card = ttk.Frame(backdrop, padding=8)
        card.place(relx=0.5, rely=0.5, anchor="center")

        ttk.Label(card, text=config.APP_NAME, style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            card,
            text=(
                f"Mỗi lần mở máy, mỗi ngôn ngữ trong danh sách cần "
                f"{config.QUIZ_TARGET_CORRECT} câu từ vựng đúng và một bài đọc. "
                "Tiếng không có trong danh sách thì không phải làm."
            ),
            style="Muted.TLabel",
            wraplength=760,
            justify="left",
        ).pack(anchor="w", pady=(8, 14))

        pickers = ttk.Frame(card)
        pickers.pack(anchor="w", fill=tk.X, pady=(0, 8))
        ttk.Label(pickers, text="Ngôn ngữ gốc").pack(side=tk.LEFT)
        self.native_var = tk.StringVar(value=config.native_label())
        self.native_box = ttk.Combobox(
            pickers,
            textvariable=self.native_var,
            values=["Tiếng Việt", "English"],
            state="readonly",
            width=16,
        )
        self.native_box.pack(side=tk.LEFT, padx=(8, 18))
        self.guard.track_combobox(self.native_box)
        self.native_box.bind("<<ComboboxSelected>>", self._on_native_selected)

        ttk.Label(pickers, text="Thêm ngôn ngữ").pack(side=tk.LEFT)
        self.add_var = tk.StringVar()
        self.add_box = ttk.Combobox(pickers, textvariable=self.add_var, state="readonly", width=22)
        self.add_box.pack(side=tk.LEFT, padx=(8, 0))
        self.guard.track_combobox(self.add_box)
        self.add_box.bind("<<ComboboxSelected>>", self._on_add_language)

        self.lang_list = ttk.Frame(card)
        self.lang_list.pack(anchor="w", fill=tk.X)
        self._build_language_rows()

        self.status_label = ttk.Label(card, text="", style="H2.TLabel", justify="left")
        self.status_label.pack(anchor="w", pady=(22, 6))

        self.detail_label = ttk.Label(
            card, text="", style="Muted.TLabel", justify="left", wraplength=760
        )
        self.detail_label.pack(anchor="w")

        self.warning_label = ttk.Label(
            card, text="", style="Muted.TLabel", foreground=ui_common.COLOR_WARN,
            wraplength=760, justify="left",
        )
        self.warning_label.pack(anchor="w", pady=8)

        ttk.Button(
            backdrop, text="Thoát khẩn cấp",
            style="Small.TButton", command=self.emergency_exit_all,
        ).place(relx=1.0, rely=1.0, x=-24, y=-24, anchor="se")

    def _code_for_label(self, label: str):
        return next(
            (code for code, profile in languages.LANGUAGES.items() if profile["label"] == label),
            None,
        )

    def _refresh_add_box(self):
        selected = set(config.study_codes())
        labels = [languages.LANGUAGES[code]["label"] for code in languages.codes() if code not in selected]
        self.add_box.configure(values=labels or ["(đã chọn hết)"])
        self.add_var.set("")

    def _build_language_rows(self):
        for child in self.lang_list.winfo_children():
            child.destroy()
        self.row_status = {}
        self.row_buttons = {}
        self._refresh_add_box()
        for code in config.study_codes():
            profile = languages.LANGUAGES[code]
            row = ttk.Frame(self.lang_list)
            row.pack(fill=tk.X, pady=3)
            ttk.Label(row, text=profile["label"], width=22).pack(side=tk.LEFT)

            status = ttk.Label(row, text="", style="Muted.TLabel", width=28)
            status.pack(side=tk.LEFT, padx=(8, 12))
            self.row_status[code] = status

            vocab_button = ttk.Button(
                row, text="Từ vựng", style="Small.TButton",
                command=lambda c=code: self.open_vocab_section(c),
            )
            vocab_button.pack(side=tk.LEFT, padx=4)
            reading_button = ttk.Button(
                row, text="Đọc", style="Small.TButton",
                command=lambda c=code: self.open_reading_section(c),
            )
            reading_button.pack(side=tk.LEFT, padx=(0, 4))
            remove_button = ttk.Button(
                row, text="Bỏ", style="Small.TButton",
                command=lambda c=code: self._remove_language(c),
            )
            remove_button.pack(side=tk.LEFT)
            self.row_buttons[code] = (vocab_button, reading_button)

    def _ensure_missing_dictionaries(self):
        try:
            if not self.root.winfo_exists():
                return
        except tk.TclError:
            return
        pairs = [(code, config.native_code()) for code in config.study_codes()]
        if self._ensure_dictionary(pairs):
            self._refresh_status()

    def _ensure_dictionary(self, pairs) -> bool:
        missing = [pair for pair in pairs if pair[0] != pair[1] and not dictionary.is_ready(*pair)]
        if not missing:
            return True
        return self._download_pairs(missing)

    def _download_pairs(self, pairs) -> bool:
        result = {"ok": False, "error": ""}
        self.guard.suspend()
        dialog = tk.Toplevel(self.root)
        dialog.title("Tải từ điển")
        dialog.resizable(False, False)
        try:
            dialog.attributes("-topmost", True)
        except tk.TclError:
            pass
        frame = ttk.Frame(dialog, padding=16)
        frame.pack()
        label = ttk.Label(frame, text="Đang tải từ điển…", wraplength=420)
        label.pack(anchor="w")
        bar = ttk.Progressbar(frame, mode="determinate", length=420, maximum=1)
        bar.pack(anchor="w", pady=8)

        def work():
            count = len(pairs)
            for index, (source, native) in enumerate(pairs):
                name = languages.LANGUAGES[source]["label"]

                def report(fraction, index=index, name=name):
                    overall = (index + fraction) / max(count, 1)
                    self.root.after(
                        0,
                        lambda name=name, overall=overall: (
                            label.config(text=f"Đang tải từ điển {name}…"),
                            bar.config(value=overall),
                        ),
                    )

                dictionary.install(source, native, report)
            result["ok"] = True

        def finish(_value):
            try:
                dialog.destroy()
            except tk.TclError:
                pass
            self.guard.resume(refocus=False)

        def fail(error):
            result["error"] = str(error)
            try:
                dialog.destroy()
            except tk.TclError:
                pass
            self.guard.resume(refocus=False)
            self.guard.show_error("Không tải được từ điển", str(error))

        ui_common.run_async(dialog, work, finish, fail)
        dialog.wait_window()
        return result["ok"]

    def _on_native_selected(self, _event=None):
        native = "en" if self.native_var.get() == "English" else "vi"
        if native == config.native_code():
            return
        pairs = [(code, native) for code in config.study_codes()]
        if not self._ensure_dictionary(pairs):
            self.native_var.set(config.native_label())
            return
        config.set_native(native)
        self._refresh_status()

    def _on_add_language(self, _event=None):
        code = self._code_for_label(self.add_var.get())
        self.add_var.set("")
        if not code or code in config.study_codes():
            return
        if not self._ensure_dictionary([(code, config.native_code())]):
            return
        config.set_study_codes(list(config.study_codes()) + [code])
        self.session.setdefault(code, {"vocab": False, "reading": False})
        self._build_language_rows()
        self._refresh_status()

    def _remove_language(self, code: str):
        chosen = [item for item in config.study_codes() if item != code]
        if not chosen:
            self.guard.show_info(
                "Cần ít nhất một ngôn ngữ",
                "Hãy giữ lại ít nhất một ngôn ngữ. Bỏ khỏi danh sách nghĩa là lần mở máy này không phải học ngôn ngữ đó.",
            )
            return
        config.set_study_codes(chosen)
        dictionary.remove_language(code)
        self._build_language_rows()
        self._refresh_status()

    def _language_pending(self, code: str) -> list:
        state = self.session[code]
        missing = []
        if not state["vocab"]:
            missing.append("từ vựng")
        if not state["reading"]:
            missing.append("bài đọc")
        return missing

    def _all_done(self) -> bool:
        return all(not self._language_pending(code) for code in config.study_codes())

    def _activate(self, code: str):
        if code not in config.study_codes():
            config.set_study_codes(list(config.study_codes()) + [code])
            self._build_language_rows()
        config.set_language(code)
        self.store = VocabStore()
        self.progress = Progress()

    def _refresh_status(self):
        required = config.study_codes()
        done_count = 0
        for code in required:
            label = self.row_status.get(code)
            if label is None:
                continue
            missing = self._language_pending(code)
            if not missing:
                done_count += 1
                label.config(text="xong lần này")
            else:
                label.config(text="còn " + " và ".join(missing))

        self.status_label.config(
            text=f"Đã xong {done_count}/{len(required)} ngôn ngữ trong lần mở máy này."
        )
        self.detail_label.config(
            text="Thêm tiếng bằng danh sách phía trên. Bỏ một tiếng thì lần này không phải học tiếng đó, và gói từ điển của nó được xóa."
        )

        warnings = []
        native = config.native_code()
        for code in required:
            if code != native and not dictionary.is_ready(code, native):
                warnings.append(
                    f"Chưa có từ điển {languages.LANGUAGES[code]['label']}. "
                    "Hãy bỏ rồi thêm lại để tải."
                )
            count = VocabStore(config.vocab_path(code)).count()
            if count == 0:
                warnings.append(
                    f"Chưa có từ {languages.LANGUAGES[code]['name_vi']}. "
                    "Hãy thêm trong phần Quản lý từ vựng."
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

    def open_vocab_section(self, code=None):
        if code is not None:
            self._activate(code)
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
            required=not self.session[config.active_code()]["vocab"],
        )

    def open_reading_section(self, code=None):
        if code is not None:
            self._activate(code)
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
            required=not self.session[config.active_code()]["reading"],
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
        self.session[config.active_code()]["vocab"] = True
        self._refresh_status()
        self.root.after(200, self._check_all_completed)

    def _on_reading_completed(self):
        self.session[config.active_code()]["reading"] = True
        self._refresh_status()
        self.root.after(200, self._check_all_completed)

    def _check_all_completed(self):
        pending = self._language_pending(config.active_code())
        if pending == ["bài đọc"]:
            self.open_reading_section()
            return
        if pending == ["từ vựng"]:
            self.open_vocab_section()
            return
        if not self._all_done():
            return

        if self._menu_hidden and not self._child_open():
            self._show_menu()

        names = ", ".join(languages.LANGUAGES[code]["label"] for code in config.study_codes())
        self.guard.show_info(
            "Xong lần này",
            f"Đã học: {names}.\n\n"
            "Lần mở máy sau, các ngôn ngữ đang được tick sẽ cần làm lại.",
        )
        self.quit_all()

    # ============================================================
    # Thoát
    # ============================================================

    def _on_close_root(self):
        if self._all_done():
            self.quit_all()
            return
        lines = []
        for code in config.study_codes():
            missing = self._language_pending(code)
            if missing:
                lines.append(f"• {languages.LANGUAGES[code]['label']}: {', '.join(missing)}")
        with self.guard.suspended():
            messagebox.showwarning(
                "Chưa hoàn thành",
                "Mỗi lần mở máy cần xong từ vựng và bài đọc của các ngôn ngữ đã tick.\n\n"
                + "\n".join(lines)
                + "\n\nNếu app bị lỗi, hãy dùng nút “Thoát khẩn cấp”.",
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
    print(
        f"Mục tiêu: {config.QUIZ_TARGET_CORRECT} câu đúng mỗi lần mở máy, "
        f"bài đọc trình độ {config.READING_LEVEL}"
    )
    print("Gốc    : " + config.native_label())
    print("Học    : " + ", ".join(languages.LANGUAGES[code]["label"] for code in config.study_codes()))
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

    if not config.language_setup_done():
        if not language_setup.run(root):
            root.destroy()
            return

    StudyMasterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
