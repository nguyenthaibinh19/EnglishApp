"""langstudyguard — mỗi lần mở máy, học các ngôn ngữ đã chọn.

Từ vựng luôn bắt buộc. Bài đọc và các phần sau này chỉ bắt khi người dùng tick.
Xong hết các phần đang bật mới đóng được app.
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
        ui_common.reset_window(root)
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
        self.reading_unavailable = False
        self._menu_hidden = False
        self.row_status = {}
        self.row_buttons = {}

        ui_common.apply_theme(root)
        self.root.resizable(True, True)
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
        self.intro_label = ttk.Label(
            card,
            text="",
            style="Muted.TLabel",
            wraplength=760,
            justify="left",
        )
        self.intro_label.pack(anchor="w", pady=(8, 14))

        activities = ttk.LabelFrame(
            card, text=config.ui("Phần cần làm", "Parts to study"), padding=8
        )
        activities.pack(anchor="w", fill=tk.X, pady=(0, 12))
        self.vocab_required = tk.IntVar(value=1)
        ttk.Checkbutton(
            activities,
            text=config.ui("Từ vựng (bắt buộc)", "Vocabulary (required)"),
            variable=self.vocab_required,
            state="disabled",
        ).pack(anchor="w")
        self.activity_vars = {}
        for activity in config.OPTIONAL_ACTIVITIES:
            variable = tk.BooleanVar(value=config.activity_enabled(activity["id"]))
            self.activity_vars[activity["id"]] = variable
            ttk.Checkbutton(
                activities,
                text=config.ui(activity["vi"], activity["en"]),
                variable=variable,
                command=lambda activity_id=activity["id"]: self._on_activity_toggled(activity_id),
            ).pack(anchor="w", pady=(4, 0))

        self.early_button = ttk.Button(
            card,
            text=config.ui(
                "Bài đọc không kết nối được. Kết thúc sớm",
                "Reading couldn't connect. Finish early",
            ),
            command=self._finish_without_reading,
        )

        pickers = ttk.Frame(card)
        pickers.pack(anchor="w", fill=tk.X, pady=(0, 8))
        self.native_caption = ttk.Label(pickers, text="")
        self.native_caption.pack(side=tk.LEFT)
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

        self.add_caption = ttk.Label(pickers, text="")
        self.add_caption.pack(side=tk.LEFT)
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

        self.emergency_button = ttk.Button(
            backdrop, text="",
            style="Small.TButton", command=self.emergency_exit_all,
        )
        self.emergency_button.place(relx=1.0, rely=1.0, x=-24, y=-24, anchor="se")

    def _code_for_label(self, label: str):
        return next(
            (code for code in languages.codes() if config.language_name(code) == label),
            None,
        )

    def _refresh_add_box(self):
        selected = set(config.study_codes())
        labels = [config.language_name(code) for code in languages.codes() if code not in selected]
        self.add_box.configure(values=labels or [config.ui("(đã chọn hết)", "(all selected)")])
        self.add_var.set("")

    def _build_language_rows(self):
        for child in self.lang_list.winfo_children():
            child.destroy()
        self.row_status = {}
        self.row_buttons = {}
        self._refresh_add_box()
        for code in config.study_codes():
            row = ttk.Frame(self.lang_list)
            row.pack(fill=tk.X, pady=3)
            ttk.Label(row, text=config.language_name(code), width=22).pack(side=tk.LEFT)

            status = ttk.Label(row, text="", style="Muted.TLabel", width=36)
            status.pack(side=tk.LEFT, padx=(8, 12))
            self.row_status[code] = status

            vocab_button = ttk.Button(
                row, text=config.ui("Từ vựng", "Vocabulary"), style="Small.TButton",
                command=lambda c=code: self.open_vocab_section(c),
            )
            vocab_button.pack(side=tk.LEFT, padx=4)
            reading_button = ttk.Button(
                row,
                text=config.ui("Đọc", "Reading"),
                style="Small.TButton",
                width=10,
                command=lambda c=code: self.open_reading_section(c),
            )
            reading_button.pack(side=tk.LEFT, padx=(0, 4))
            remove_button = ttk.Button(
                row, text=config.ui("Bỏ", "Remove"), style="Small.TButton",
                command=lambda c=code: self._remove_language(c),
            )
            remove_button.pack(side=tk.LEFT)
            self.row_buttons[code] = (vocab_button, reading_button)
            self._sync_reading_button(reading_button)

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
        dialog.title(config.ui("Tải từ điển", "Download dictionary"))
        dialog.resizable(False, False)
        try:
            dialog.attributes("-topmost", True)
        except tk.TclError:
            pass
        frame = ttk.Frame(dialog, padding=16)
        frame.pack()
        label = ttk.Label(frame, text=config.ui("Đang tải từ điển…", "Downloading the dictionary…"), wraplength=420)
        label.pack(anchor="w")
        bar = ttk.Progressbar(frame, mode="determinate", length=420, maximum=1)
        bar.pack(anchor="w", pady=8)

        def work():
            count = len(pairs)
            for index, (source, native) in enumerate(pairs):
                name = config.language_name(source)

                def report(fraction, index=index, name=name):
                    overall = (index + fraction) / max(count, 1)
                    self.root.after(
                        0,
                        lambda name=name, overall=overall: (
                            label.config(text=config.ui(
                                f"Đang tải từ điển {name}…",
                                f"Downloading the {name} dictionary…",
                            )),
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
            self.guard.show_error(config.ui("Không tải được từ điển", "Dictionary download failed"), str(error))

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
        self._build_language_rows()
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
                config.ui("Cần ít nhất một ngôn ngữ", "Keep at least one language"),
                config.ui(
                    "Hãy giữ lại ít nhất một ngôn ngữ. Bỏ khỏi danh sách nghĩa là lần mở máy này không phải học ngôn ngữ đó.",
                    "Keep at least one language. Removing a language means you don't study it this launch.",
                ),
            )
            return
        config.set_study_codes(chosen)
        dictionary.remove_language(code)
        self._build_language_rows()
        self._refresh_status()

    def _sync_reading_button(self, button: ttk.Button):
        if config.activity_enabled("reading"):
            button.state(["!disabled"])
        else:
            button.state(["disabled"])

    def _sync_reading_buttons(self):
        for buttons in self.row_buttons.values():
            reading_button = buttons[1] if len(buttons) > 1 else None
            if reading_button is not None:
                self._sync_reading_button(reading_button)

    def _on_activity_toggled(self, activity_id: str):
        variable = self.activity_vars.get(activity_id)
        if variable is None:
            return
        config.set_activity_enabled(activity_id, bool(variable.get()))
        if activity_id == "reading" and variable.get():
            self.reading_unavailable = False
        if activity_id == "reading":
            self._sync_reading_buttons()
        self._refresh_status()
        if self._all_done():
            self.root.after(200, self._finish_if_all_done)

    def _vocab_all_done(self) -> bool:
        return all(
            self.session.get(code, {}).get("vocab") for code in config.study_codes()
        )

    def _language_pending(self, code: str) -> list:
        state = self.session[code]
        missing = []
        if not state["vocab"]:
            missing.append("từ vựng")
        for activity in config.OPTIONAL_ACTIVITIES:
            if config.activity_enabled(activity["id"]) and not state.get(activity["id"]):
                missing.append(activity["id"])
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
            names = {"từ vựng": config.ui("từ vựng", "vocabulary")}
            for activity in config.OPTIONAL_ACTIVITIES:
                names[activity["id"]] = config.ui(activity["vi"].lower(), activity["en"].lower())
            if not missing:
                done_count += 1
                label.config(text=config.ui("xong lần này", "done this launch"))
            else:
                shown = [names.get(item, item) for item in missing]
                label.config(text=config.ui("còn " + " và ".join(shown), "still " + " and ".join(shown)))

        target = config.QUIZ_TARGET_CORRECT
        self.intro_label.config(text=config.ui(
            f"Mỗi lần mở máy, mỗi ngôn ngữ trong danh sách cần "
            f"{target} câu từ vựng đúng. Tick thêm phần ở khung "
            "“Phần cần làm” nếu bạn muốn làm thêm trong lần này.",
            f"Each time the computer starts, every language in the list needs "
            f"{target} correct vocabulary answers. Tick extra parts under "
            "“Parts to study” if you want them this launch.",
        ))
        if (
            self.reading_unavailable
            and config.activity_enabled("reading")
            and self._vocab_all_done()
            and not self._all_done()
        ):
            self.early_button.pack(anchor="w", pady=(0, 8))
        else:
            self.early_button.pack_forget()
        self.native_caption.config(text=config.ui("Ngôn ngữ gốc", "Your language"))
        self.add_caption.config(text=config.ui("Thêm ngôn ngữ", "Add a language"))
        self.emergency_button.config(text=config.ui("Thoát khẩn cấp", "Emergency exit"))

        self.status_label.config(
            text=config.ui(
                f"Đã xong {done_count}/{len(required)} ngôn ngữ trong lần mở máy này.",
                f"{done_count}/{len(required)} languages done this launch.",
            )
        )
        self.detail_label.config(
            text=config.ui(
                "Thêm tiếng bằng danh sách phía trên. Bỏ một tiếng thì lần này không phải học tiếng đó, và gói từ điển của nó được xóa.",
                "Add a language from the list above. Removing one skips it this launch and deletes its dictionary.",
            )
        )

        warnings = []
        native = config.native_code()
        for code in required:
            if code != native and not dictionary.is_ready(code, native):
                name = config.language_name(code)
                warnings.append(config.ui(
                    f"Chưa có từ điển {name}. Hãy bỏ rồi thêm lại để tải.",
                    f"No {name} dictionary yet. Remove it and add it again to download.",
                ))
            count = VocabStore(config.vocab_path(code)).count()
            if count == 0:
                name = config.language_name(code)
                warnings.append(config.ui(
                    f"Chưa có từ {name}. Hãy thêm trong phần Quản lý từ vựng.",
                    f"No {name} words yet. Add some in Manage vocabulary.",
                ))
        if not config.ai_is_configured():
            if config.is_frozen():
                warnings.append(config.ui(
                    "Chưa đăng nhập. Hãy đăng nhập để AI chấm câu và viết bài đọc.",
                    "Not signed in. Sign in so the AI can grade sentences and write readings.",
                ))
            else:
                warnings.append(config.ui(
                    "Chưa có OPENAI_API_KEY trong file .env nên AI sẽ không chấm câu và "
                    "không tự viết bài đọc được.",
                    "OPENAI_API_KEY is missing from .env, so the AI cannot grade sentences or write readings.",
                ))
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
            on_request_switch=self._switch_to_reading if config.activity_enabled("reading") else None,
            on_emergency=self.quit_all,
            required=not self.session[config.active_code()]["vocab"],
            locked=True,
        )

    def open_reading_section(self, code=None):
        if not config.activity_enabled("reading"):
            return
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
            on_failed=self._mark_reading_unavailable,
            on_skip=self._finish_without_reading if self._vocab_all_done() else None,
            required=not self.session[config.active_code()]["reading"],
            locked=True,
        )

    def _hide_menu(self):
        """Nhường màn hình cho cửa sổ luyện tập, menu fullscreen không che lên trên."""
        if self._menu_hidden:
            return
        self._menu_hidden = True
        self.guard.suspend(leave_fullscreen=False)
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
        self.root.after(50, self._refresh_status)

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
        code = config.active_code()
        self.session[code]["vocab"] = True
        self._refresh_status()
        if not config.activity_enabled("reading"):
            self.root.after(200, self._finish_if_all_done)
            return
        # Chỉ mở đúng một bài đọc của ngôn ngữ vừa học xong.
        self.root.after(200, lambda: self._open_one_reading(code))

    def _open_one_reading(self, code: str):
        if self._child_open():
            return
        if self.session.get(code, {}).get("reading"):
            self._finish_if_all_done()
            return
        self.open_reading_section(code)

    def _mark_reading_unavailable(self):
        self.reading_unavailable = True
        self._refresh_status()

    def _finish_without_reading(self):
        """Bỏ phần đọc của lần mở máy này khi không gọi được AI."""
        if not self._vocab_all_done():
            self._close_window(self.reading_window)
            return
        for code in config.study_codes():
            state = self.session.setdefault(code, {"vocab": False, "reading": False})
            state["reading"] = True
        self.reading_unavailable = False
        self._close_window(self.reading_window)
        self._refresh_status()
        self.root.after(200, self._finish_if_all_done)

    def _on_reading_completed(self):
        self.session[config.active_code()]["reading"] = True
        self.reading_unavailable = False
        self._refresh_status()
        self.root.after(200, self._finish_if_all_done)

    def _finish_if_all_done(self):
        if self._child_open() or not self._all_done():
            return

        if self._menu_hidden and not self._child_open():
            self._show_menu()

        names = ", ".join(config.language_name(code) for code in config.study_codes())
        self.guard.show_info(
            config.ui("Xong lần này", "Done for this launch"),
            config.ui(
                f"Đã học: {names}.\n\n"
                "Lần mở máy sau, các ngôn ngữ đang được tick sẽ cần làm lại.",
                f"Studied: {names}.\n\n"
                "The next time you open the app, the selected languages start again.",
            ),
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
                names = {"từ vựng": config.ui("từ vựng", "vocabulary")}
                for activity in config.OPTIONAL_ACTIVITIES:
                    names[activity["id"]] = config.ui(activity["vi"].lower(), activity["en"].lower())
                shown = ", ".join(names.get(item, item) for item in missing)
                lines.append(f"• {config.language_name(code)}: {shown}")
        with self.guard.suspended():
            messagebox.showwarning(
                config.ui("Chưa hoàn thành", "Not finished"),
                config.ui(
                    "Mỗi lần mở máy cần xong các phần đang được tick.\n\n",
                    "Each launch needs every ticked part for the selected languages.\n\n",
                )
                + "\n".join(lines)
                + config.ui(
                    "\n\nNếu app bị lỗi, hãy dùng nút “Thoát khẩn cấp”.",
                    "\n\nIf the app is stuck, use Emergency exit.",
                ),
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
    print("Học    : " + ", ".join(languages.resolve_language(code).label for code in config.study_codes()))
    print(f"Hôm nay : đã ôn {summary['asked_today']} từ, "
          f"bài đọc {'xong' if summary['reading_done'] else 'chưa xong'}")


class FreeHome:
    """Cửa sổ nhỏ khi người dùng tự mở app: chỉ làm bài hoặc thêm từ."""

    def __init__(self, root: tk.Tk):
        ui_common.reset_window(root)
        self.root = root
        self.bank_window = None
        self.root.title(config.APP_NAME)
        self.root.geometry("440x280")
        self.root.minsize(400, 240)
        self.root.resizable(False, False)
        ui_common.apply_theme(root)
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)

        card = ttk.Frame(root, padding=28)
        card.pack(fill=tk.BOTH, expand=True)
        ttk.Label(card, text=config.APP_NAME, style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            card,
            text=config.ui(
                "Thêm từ thì đóng được ngay. Làm bài sẽ vào màn hình khóa.",
                "Adding words can be closed anytime. Study opens the locked screen.",
            ),
            style="Muted.TLabel",
            wraplength=360,
        ).pack(anchor="w", pady=(10, 22))

        ttk.Button(
            card, text=config.ui("Làm bài", "Study"), command=self._start_study
        ).pack(fill=tk.X, pady=4)
        ttk.Button(
            card, text=config.ui("Thêm từ", "Add words"), command=self._add_words
        ).pack(fill=tk.X, pady=4)

    def _start_study(self):
        self._close_bank()
        for child in self.root.winfo_children():
            child.destroy()
        self.root.resizable(True, True)
        StudyMasterApp(self.root)

    def _add_words(self):
        codes = config.study_codes()
        if len(codes) == 1:
            self._open_bank(codes[0])
            return
        self._choose_language(codes)

    def _choose_language(self, codes):
        dialog = tk.Toplevel(self.root)
        dialog.title(config.ui("Chọn ngôn ngữ", "Choose a language"))
        dialog.resizable(False, False)
        dialog.transient(self.root)
        frame = ttk.Frame(dialog, padding=16)
        frame.pack()
        ttk.Label(
            frame, text=config.ui("Thêm từ cho ngôn ngữ nào?", "Add words for which language?")
        ).pack(anchor="w", pady=(0, 8))
        for code in codes:
            ttk.Button(
                frame,
                text=config.language_name(code),
                command=lambda c=code, dialog=dialog: (dialog.destroy(), self._open_bank(c)),
            ).pack(fill=tk.X, pady=2)
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.geometry("+%d+%d" % (self.root.winfo_rootx() + 40, self.root.winfo_rooty() + 40))

    def _open_bank(self, code):
        config.set_language(code)
        if self.bank_window is not None and self.bank_window.winfo_exists():
            self.bank_window.lift()
            return
        self.bank_window = tk.Toplevel(self.root)
        VocabQuizApp(
            self.bank_window,
            store=VocabStore(),
            progress=Progress(),
            required=False,
            manage_only=True,
            locked=False,
        )

    def _close_bank(self):
        if self.bank_window is not None and self.bank_window.winfo_exists():
            self.bank_window.destroy()


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
        messagebox.showerror(config.APP_NAME, f"Không cài được ứng dụng:\n{error}")
        root.destroy()
        return
    if not stay:
        return

    if config.is_frozen() and config.account_token():
        import account_client
        account_client.session_still_valid()

    root = tk.Tk()
    if config.is_frozen() and not config.is_ready():
        if not setup_wizard.run(root):
            root.destroy()
            return

    if not config.language_setup_done():
        if not language_setup.run(root):
            root.destroy()
            return

    if "--lock" in sys.argv:
        StudyMasterApp(root)
    else:
        FreeHome(root)
    if config.is_frozen():
        import updater
        # Chờ desktop ổn định rồi mới hỏi cập nhật — tránh tranh focus lúc login.
        delay = 3500 if "--lock" in sys.argv else 800
        root.after(delay, lambda: updater.prompt_if_needed(root))
    root.mainloop()


if __name__ == "__main__":
    main()
