"""langstudyguard — mỗi lần mở máy, học các ngôn ngữ đã chọn.

Từ vựng luôn bắt buộc. Bài đọc và các phần sau này chỉ bắt khi người dùng tick.
Xong hết các phần đang bật mới đóng được app.
"""

import traceback
import tkinter as tk
from tkinter import messagebox, ttk

import config
import dictionary
import install
import language_setup
import languages
import setup_wizard
import ui_common
from daily_study import plan_for_language
from progress import Progress
from quiz_app import VocabQuizApp
from listening import resolve_listening_audio_provider
from listening_app import ListeningApp
from reading_app import ReadingApp
from study_session import (
    KIND_LISTENING,
    KIND_READING,
    KIND_VOCABULARY,
    STATUS_UNAVAILABLE,
    StudySession,
    build_study_session,
)
from vocab_store import VocabStore


class StudyMasterApp:
    def __init__(self, root: tk.Tk, on_finished=None):
        ui_common.reset_window(root)
        self.root = root
        self.root.title(config.APP_NAME)
        self.on_finished = on_finished
        self._force_exit = False

        self.store = VocabStore()
        self.progress = Progress()

        # Session Runner v1: one StudySession per study language (from DailyStudyPlan).
        self.sessions: dict[str, StudySession] = {}
        self._rebuild_sessions()

        self.vocab_window = None
        self.reading_window = None
        self.listening_window = None
        self.reading_unavailable = False
        self.listening_unavailable = False
        # Lazy TTS: never discover Windows voices during StudyMaster construction.
        # Listening-off users must not pay PowerShell enumeration cost.
        self._listening_audio_provider = None
        self._listening_provider_resolved = False
        self._listening_provider_resolving = False
        self._listening_resolve_code = None
        self._menu_hidden = False
        self.row_status = {}
        self.row_buttons = {}

        ui_common.apply_theme(root)
        self.root.resizable(True, True)
        self.guard = ui_common.ScreenGuard(root, on_close_attempt=self._on_close_root)

        self._build_ui()
        self._refresh_status()
        self.root.after(300, self._ensure_missing_dictionaries)

    def _rebuild_sessions(self):
        """(Re)build StudySession objects for current study languages from plans."""
        next_sessions: dict[str, StudySession] = {}
        for code in config.study_codes():
            previous = self.sessions.get(code)
            plan = plan_for_language(code)
            session = build_study_session(plan)
            if previous is not None:
                # Preserve completed vocabulary across optional-activity rebuilds.
                if previous.vocabulary_complete() and session.has_activity(KIND_VOCABULARY):
                    session.complete(KIND_VOCABULARY)
                for kind in (KIND_READING, KIND_LISTENING):
                    if previous.has_activity(kind) and session.has_activity(kind):
                        prior = previous.status(kind)
                        if prior == "completed":
                            session.complete(kind)
                        elif prior == "skipped":
                            session.skip(kind)
                        elif prior == STATUS_UNAVAILABLE:
                            session.mark_unavailable(kind)
            next_sessions[code] = session
        self.sessions = next_sessions

    def _session_for(self, code: str = None) -> StudySession:
        code = code or config.active_code()
        session = self.sessions.get(code)
        if session is None:
            session = build_study_session(plan_for_language(code))
            self.sessions[code] = session
        return session

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
        self.listening_check_label = ttk.Label(
            card,
            text="",
            style="Muted.TLabel",
            wraplength=760,
            justify="left",
        )
        self.listening_check_label.pack(anchor="w", pady=(0, 4))

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
            command=self._skip_reading,
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
            listening_button = ttk.Button(
                row,
                text=config.ui("Nghe", "Listen"),
                style="Small.TButton",
                width=10,
                command=lambda c=code: self.open_listening_section(c),
            )
            listening_button.pack(side=tk.LEFT, padx=(0, 4))
            remove_button = ttk.Button(
                row, text=config.ui("Bỏ", "Remove"), style="Small.TButton",
                command=lambda c=code: self._remove_language(c),
            )
            remove_button.pack(side=tk.LEFT)
            self.row_buttons[code] = (vocab_button, reading_button, listening_button)
            self._sync_reading_button(reading_button)
            self._sync_listening_button(listening_button)

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
        self.guard.pause_enforcement()
        dialog = ui_common.open_owned_popup(
            self.root,
            title=config.ui("Tải từ điển", "Download dictionary"),
            modal=True,
            topmost=True,
        )
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
            self.guard.resume_enforcement(refocus=False)

        def fail(error):
            result["error"] = str(error)
            try:
                dialog.destroy()
            except tk.TclError:
                pass
            self.guard.resume_enforcement(refocus=False)
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
        self.sessions[code] = build_study_session(plan_for_language(code))
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
        self.sessions.pop(code, None)
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

    def _sync_listening_button(self, button: ttk.Button):
        if config.activity_enabled("listening"):
            button.state(["!disabled"])
        else:
            button.state(["disabled"])

    def _sync_listening_buttons(self):
        for buttons in self.row_buttons.values():
            listening_button = buttons[2] if len(buttons) > 2 else None
            if listening_button is not None:
                self._sync_listening_button(listening_button)

    def _on_activity_toggled(self, activity_id: str):
        variable = self.activity_vars.get(activity_id)
        if variable is None:
            return
        enabled = bool(variable.get())
        config.set_activity_enabled(activity_id, enabled)
        if activity_id == "reading":
            self.reading_unavailable = False
            for session in self.sessions.values():
                session.set_optional_enabled(KIND_READING, enabled)
            self._sync_reading_buttons()
        elif activity_id == "listening":
            self.listening_unavailable = False
            for session in self.sessions.values():
                session.set_optional_enabled(KIND_LISTENING, enabled)
            self._sync_listening_buttons()
        self._refresh_status()
        if self._all_done():
            self.root.after(200, self._finish_if_all_done)

    def _vocab_all_done(self) -> bool:
        return all(
            self._session_for(code).vocabulary_complete()
            for code in config.study_codes()
        )

    def _language_pending(self, code: str) -> list:
        session = self._session_for(code)
        missing = []
        if session.has_activity(KIND_VOCABULARY) and not session.vocabulary_complete():
            missing.append("từ vựng")
        if session.has_activity(KIND_READING) and not session.is_resolved(KIND_READING):
            missing.append("reading")
        if session.has_activity(KIND_LISTENING) and not session.is_resolved(KIND_LISTENING):
            missing.append("listening")
        return missing

    def _all_done(self) -> bool:
        return all(
            self._session_for(code).can_finish for code in config.study_codes()
        )

    def _activate(self, code: str):
        if code not in config.study_codes():
            config.set_study_codes(list(config.study_codes()) + [code])
            self.sessions[code] = build_study_session(plan_for_language(code))
            self._build_language_rows()
        config.set_language(code)
        self.store = VocabStore()
        self.progress = Progress()
        self._session_for(code)

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
            (
                self.reading_unavailable
                or any(
                    self._session_for(code).status(KIND_READING) == STATUS_UNAVAILABLE
                    for code in config.study_codes()
                )
            )
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
        else:
            code = config.active_code()
            self._activate(code)
        session = self._session_for(code)
        if not session.has_activity(KIND_VOCABULARY):
            self.guard.show_info(
                config.ui("Chưa có từ vựng", "No vocabulary yet"),
                config.ui(
                    "Ngôn ngữ này chưa có từ để luyện trong lần này.",
                    "This language has no vocabulary to practice this launch.",
                ),
            )
            return
        if session.vocabulary_complete():
            # Already done — allow review with required=False.
            pass
        if self.vocab_window is not None and self.vocab_window.winfo_exists():
            self.vocab_window.lift()
            return

        self._suspend_for_activity()
        started = False

        def build(window):
            nonlocal started
            window.bind("<Destroy>", self._on_child_destroy, add="+")
            if not session.vocabulary_complete():
                session.start(KIND_VOCABULARY)
                started = True
            VocabQuizApp(
                window,
                store=self.store,
                progress=self.progress,
                on_completed=self._on_vocab_completed,
                on_request_switch=(
                    self._switch_to_reading
                    if config.activity_enabled("reading")
                    else None
                ),
                on_emergency=self.quit_all,
                required=not session.vocabulary_complete(),
                locked=True,
                target=session.planned_vocab_count,
                language_code=code,
            )

        def failed(error):
            self._report_activity_launch_error("Vocabulary", error)
            self._resume_after_activity()

        self.vocab_window = ui_common.launch_toplevel_app(
            self.root, build, on_error=failed
        )
        if self.vocab_window is None and started:
            # Constructor failed after start — leave vocab pending for retry.
            pass

    def open_reading_section(self, code=None):
        if not config.activity_enabled("reading"):
            return
        if code is not None:
            self._activate(code)
        else:
            code = config.active_code()
            self._activate(code)
        session = self._session_for(code)
        if not session.has_activity(KIND_READING):
            return
        if self.reading_window is not None and self.reading_window.winfo_exists():
            self.reading_window.lift()
            return

        self._suspend_for_activity()
        started = False

        def build(window):
            nonlocal started
            window.bind("<Destroy>", self._on_child_destroy, add="+")
            if not session.is_resolved(KIND_READING):
                session.start(KIND_READING)
                started = True
            # Reading is optional in StudySession — unresolved ≠ required.
            ReadingApp(
                window,
                store=self.store,
                progress=self.progress,
                on_completed=self._on_reading_completed,
                on_request_switch=self._switch_to_vocab,
                on_emergency=self.quit_all,
                on_failed=self._mark_reading_unavailable,
                on_skip=self._skip_reading,
                required=False,
                locked=True,
            )

        def failed(error):
            self._report_activity_launch_error("Reading", error)
            if started or session.has_activity(KIND_READING):
                try:
                    session.mark_unavailable(KIND_READING)
                except Exception:
                    pass
            self.reading_unavailable = True
            self._resume_after_activity()
            self._refresh_status()
            self.root.after(200, self._finish_if_all_done)

        self.reading_window = ui_common.launch_toplevel_app(
            self.root, build, on_error=failed
        )

    def open_listening_section(self, code=None):
        if not config.activity_enabled("listening"):
            return
        if code is not None:
            self._activate(code)
        else:
            code = config.active_code()
            self._activate(code)
        session = self._session_for(code)
        if not session.has_activity(KIND_LISTENING):
            return
        if self.listening_window is not None and self.listening_window.winfo_exists():
            self.listening_window.lift()
            return

        # First Listening open: resolve/discover off the Tk thread.
        if not self._listening_provider_resolved:
            self._begin_listening_provider_resolve(code)
            return

        self._open_listening_with_resolved_provider(code)

    def _blocking_resolve_listening_provider(self):
        """Resolve + voice discovery. Call only from a background worker."""
        provider = resolve_listening_audio_provider()
        if provider is None:
            return None
        if not provider.is_available():
            return None
        return provider

    def _show_listening_check_status(self):
        try:
            self.listening_check_label.config(
                text=config.ui(
                    "Đang kiểm tra giọng đọc Windows…",
                    "Checking Windows speech voices…",
                )
            )
        except tk.TclError:
            pass

    def _clear_listening_check_status(self):
        try:
            self.listening_check_label.config(text="")
        except tk.TclError:
            pass

    def _begin_listening_provider_resolve(self, code: str):
        """Kick off one background discovery; keep StudyMaster responsive."""
        self._listening_resolve_code = code
        self._show_listening_check_status()
        if self._listening_provider_resolving:
            return
        self._listening_provider_resolving = True

        def work():
            return self._blocking_resolve_listening_provider()

        def on_success(provider):
            self._listening_audio_provider = provider
            self._listening_provider_resolved = True
            self._listening_provider_resolving = False
            self._clear_listening_check_status()
            pending = self._listening_resolve_code or code
            self._listening_resolve_code = None
            if not config.activity_enabled("listening"):
                return
            self._open_listening_with_resolved_provider(pending)

        def on_error(_error):
            self._listening_audio_provider = None
            self._listening_provider_resolved = True
            self._listening_provider_resolving = False
            self._clear_listening_check_status()
            pending = self._listening_resolve_code or code
            self._listening_resolve_code = None
            if not config.activity_enabled("listening"):
                return
            self._open_listening_with_resolved_provider(pending)

        ui_common.run_async(self.root, work, on_success, on_error)

    def _open_listening_with_resolved_provider(self, code: str):
        """Open Listening using the cached provider (or mark unavailable)."""
        session = self._session_for(code)
        if not session.has_activity(KIND_LISTENING):
            return
        if self.listening_window is not None and self.listening_window.winfo_exists():
            self.listening_window.lift()
            return

        provider = self._listening_audio_provider
        # Provider / per-language voice support → unavailable (never trap lock).
        if provider is None or not provider.is_available():
            try:
                session.mark_unavailable(KIND_LISTENING)
            except Exception:
                pass
            self.listening_unavailable = True
            self._refresh_status()
            self.guard.show_info(
                config.ui("Nghe", "Listening"),
                config.ui(
                    "Phần nghe chưa dùng được vì chưa có nguồn phát âm thanh. "
                    "Bạn vẫn có thể kết thúc phiên học.",
                    "Listening is unavailable because no audio provider is configured. "
                    "You can still finish the study session.",
                ),
            )
            self.root.after(200, self._finish_if_all_done)
            return
        if not provider.supports(code):
            try:
                session.mark_unavailable(KIND_LISTENING)
            except Exception:
                pass
            self.listening_unavailable = True
            self._refresh_status()
            missing = getattr(provider, "missing_voice_message", None)
            detail = (
                missing(code)
                if callable(missing)
                else config.ui(
                    f"Chưa cài giọng đọc Windows cho {config.language_name(code)}.",
                    f"No Windows text-to-speech voice is installed for "
                    f"{config.language_name(code)}.",
                )
            )
            self.guard.show_info(
                config.ui("Nghe", "Listening"),
                detail
                + "\n\n"
                + config.ui(
                    "Bạn vẫn có thể kết thúc phiên học.",
                    "You can still finish the study session.",
                ),
            )
            self.root.after(200, self._finish_if_all_done)
            return

        self._suspend_for_activity()
        started = False

        def build(window):
            nonlocal started
            window.bind("<Destroy>", self._on_child_destroy, add="+")
            if not session.is_resolved(KIND_LISTENING):
                session.start(KIND_LISTENING)
                started = True
            # Listening is optional — unresolved ≠ required at the Tk layer.
            ListeningApp(
                window,
                language_code=code,
                audio_provider=provider,
                on_completed=self._on_listening_completed,
                on_failed=self._mark_listening_unavailable,
                on_skip=self._skip_listening,
                on_emergency=self.quit_all,
                required=False,
                locked=True,
            )

        def failed(error):
            self._report_activity_launch_error("Listening", error)
            if started or session.has_activity(KIND_LISTENING):
                try:
                    session.mark_unavailable(KIND_LISTENING)
                except Exception:
                    pass
            self.listening_unavailable = True
            self._resume_after_activity()
            self._refresh_status()
            self.root.after(200, self._finish_if_all_done)

        self.listening_window = ui_common.launch_toplevel_app(
            self.root, build, on_error=failed
        )

    def _report_activity_launch_error(self, label: str, error: BaseException):
        """Log full traceback for developers; show a safe message to the learner."""
        traceback.print_exc()
        detail = f"{type(error).__name__}: {error}"
        print(f"[StudyMaster] {label} launch failed: {detail}", flush=True)
        try:
            self.guard.show_error(
                config.ui(f"Không mở được {label}", f"Could not open {label}"),
                config.ui(
                    f"Có lỗi khi mở {label}.\n\n{detail}\n\n"
                    "Phần tùy chọn sẽ được bỏ qua nếu cần để bạn vẫn kết thúc được.",
                    f"Failed to open {label}.\n\n{detail}\n\n"
                    "Optional activities can be skipped so you can still finish.",
                ),
            )
        except Exception:
            pass

    def _suspend_for_activity(self):
        """Pause parent enforcement; keep StudyMaster mapped and fullscreen stable."""
        if self._menu_hidden:
            return
        self._menu_hidden = True
        # Child activity owns its own ScreenGuard. Do not zoom/unfullscreen parent.
        self.guard.pause_enforcement()

    def _child_open(self) -> bool:
        for window in (self.vocab_window, self.reading_window, self.listening_window):
            try:
                if window is not None and window.winfo_exists():
                    return True
            except tk.TclError:
                continue
        return False

    def _resume_after_activity(self):
        """Resume parent guard after a failed launch or when no child remains."""
        if self._child_open() or not self._menu_hidden:
            return
        self._menu_hidden = False
        self.guard.resume_enforcement()

    def _show_menu(self):
        self._resume_after_activity()

    def _on_child_destroy(self, event):
        if event.widget not in (
            self.vocab_window,
            self.reading_window,
            self.listening_window,
        ):
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
        session = self._session_for(code)
        session.complete(KIND_VOCABULARY)
        self._refresh_status()
        nxt = session.next_activity()
        if nxt is not None and nxt.kind == KIND_READING:
            self.root.after(200, lambda: self._open_one_reading(code))
            return
        if nxt is not None and nxt.kind == KIND_LISTENING:
            self.root.after(200, lambda: self._open_one_listening(code))
            return
        self.root.after(200, self._finish_if_all_done)

    def _open_one_reading(self, code: str):
        if self._child_open():
            return
        session = self._session_for(code)
        if session.is_resolved(KIND_READING):
            self._advance_after_reading(code)
            return
        if not session.has_activity(KIND_READING):
            self._advance_after_reading(code)
            return
        self.open_reading_section(code)

    def _open_one_listening(self, code: str):
        if self._child_open():
            return
        session = self._session_for(code)
        if session.is_resolved(KIND_LISTENING) or not session.has_activity(KIND_LISTENING):
            self._finish_if_all_done()
            return
        self.open_listening_section(code)

    def _advance_after_reading(self, code: str):
        session = self._session_for(code)
        nxt = session.next_activity()
        if nxt is not None and nxt.kind == KIND_LISTENING:
            self.root.after(200, lambda: self._open_one_listening(code))
            return
        self.root.after(200, self._finish_if_all_done)

    def _mark_reading_unavailable(self):
        """Mark Reading unavailable for the active study language only."""
        code = config.active_code()
        session = self._session_for(code)
        if session.has_activity(KIND_READING):
            try:
                session.mark_unavailable(KIND_READING)
            except Exception:
                pass
        self.reading_unavailable = True
        self._refresh_status()
        self._advance_after_reading(code)

    def _skip_reading(self):
        """Skip Reading for the active study language only."""
        code = config.active_code()
        session = self._session_for(code)
        if session.has_activity(KIND_READING) and not session.is_resolved(KIND_READING):
            try:
                session.skip(KIND_READING)
            except Exception:
                try:
                    session.mark_unavailable(KIND_READING)
                except Exception:
                    pass
        self.reading_unavailable = False
        self._close_window(self.reading_window)
        self._refresh_status()
        self._advance_after_reading(code)

    def _on_reading_completed(self):
        code = config.active_code()
        session = self._session_for(code)
        if session.has_activity(KIND_READING):
            session.complete(KIND_READING)
        self.reading_unavailable = False
        self._refresh_status()
        self._advance_after_reading(code)

    def _on_listening_completed(self):
        session = self._session_for(config.active_code())
        if session.has_activity(KIND_LISTENING):
            session.complete(KIND_LISTENING)
        self.listening_unavailable = False
        self._refresh_status()
        self.root.after(200, self._finish_if_all_done)

    def _mark_listening_unavailable(self):
        session = self._session_for(config.active_code())
        if session.has_activity(KIND_LISTENING):
            try:
                session.mark_unavailable(KIND_LISTENING)
            except Exception:
                pass
        self.listening_unavailable = True
        self._refresh_status()
        if self._all_done():
            self.root.after(200, self._finish_if_all_done)

    def _skip_listening(self):
        """Skip Listening for the active study language only (like Reading)."""
        code = config.active_code()
        session = self._session_for(code)
        if session.has_activity(KIND_LISTENING) and not session.is_resolved(
            KIND_LISTENING
        ):
            try:
                session.skip(KIND_LISTENING)
            except Exception:
                try:
                    session.mark_unavailable(KIND_LISTENING)
                except Exception:
                    pass
        self.listening_unavailable = False
        self._close_window(self.listening_window)
        self._refresh_status()
        self.root.after(200, self._finish_if_all_done)

    def _finish_if_all_done(self):
        if self._child_open() or not self._all_done():
            return

        if self._menu_hidden and not self._child_open():
            self._show_menu()

        names = ", ".join(config.language_name(code) for code in config.study_codes())
        lines = []
        for code in config.study_codes():
            session = self._session_for(code)
            parts = []
            if session.has_activity(KIND_VOCABULARY):
                parts.append(config.ui("Từ vựng ✓", "Vocabulary ✓"))
            if session.has_activity(KIND_READING):
                st = session.status(KIND_READING)
                if st == "completed":
                    parts.append(config.ui("Đọc ✓", "Reading ✓"))
                elif st == "skipped":
                    parts.append(config.ui("Đọc: bỏ qua", "Reading: skipped"))
                elif st == STATUS_UNAVAILABLE:
                    parts.append(config.ui("Đọc: không dùng được", "Reading: unavailable"))
            if session.has_activity(KIND_LISTENING):
                st = session.status(KIND_LISTENING)
                if st == "completed":
                    parts.append(config.ui("Nghe ✓", "Listening ✓"))
                elif st == "skipped":
                    parts.append(config.ui("Nghe: bỏ qua", "Listening: skipped"))
                elif st == STATUS_UNAVAILABLE:
                    parts.append(
                        config.ui("Nghe: không dùng được", "Listening: unavailable")
                    )
            if parts:
                lines.append(f"{config.language_name(code)} — " + ", ".join(parts))
        detail = "\n".join(lines) if lines else names
        self.guard.show_info(
            config.ui("Xong lần này", "Done for this launch"),
            config.ui(
                f"Đã học hôm nay:\n{detail}\n\n"
                "Lần mở máy sau, các ngôn ngữ đang được tick sẽ cần làm lại.",
                f"Today's study:\n{detail}\n\n"
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
            self._force_exit = True
            self.quit_all()

    def quit_all(self):
        self.progress.save()
        for window in (self.vocab_window, self.reading_window, self.listening_window):
            try:
                self._close_window(window)
            except tk.TclError:
                pass
        # FreeHome dashboard: return and refresh plan. Lock/boot mode: exit app.
        if callable(self.on_finished) and not self._force_exit:
            try:
                self.guard.enabled = False
            except Exception:
                pass
            try:
                ui_common.reset_window(self.root)
            except tk.TclError:
                pass
            self.on_finished()
            return
        try:
            self.root.destroy()
        except tk.TclError:
            pass


def run_diagnostics():
    """`python main.py --check` — xem môi trường đã sẵn sàng chưa, không mở cửa sổ."""
    import importlib
    import os
    import sys

    lines: list[str] = []

    def out(message: str = "") -> None:
        print(message)
        lines.append(message)

    out(f"{config.APP_NAME} — kiểm tra môi trường\n")
    out(f"Python  : {sys.version.split()[0]}")
    out(f"Đường dẫn: {sys.executable}")
    out(f"Dữ liệu : {config.data_dir()}")
    out(f"Bản đóng gói: {'có' if config.is_frozen() else 'không'}\n")

    for module, needed_for in (
        ("tkinter", "giao diện"),
        ("dotenv", "đọc file .env"),
        ("openai", "chấm câu và viết bài đọc"),
        ("PyPDF2", "đọc bài tự soạn dạng PDF"),
    ):
        try:
            importlib.import_module(module)
            out(f"  [ok] {module}")
        except ImportError:
            out(f"  [thiếu] {module} — cần cho {needed_for}")

    store = VocabStore()
    summary = Progress().summary()
    out(f"\nTừ vựng : {store.count()} từ trong vocab.json")
    duplicates = store.find_duplicates()
    if duplicates:
        out(f"  Trùng lặp: {', '.join(duplicates[:5])}")
    if config.ai_is_configured():
        key_status = "đã cấu hình"
    elif config.OPENAI_API_KEY:
        key_status = "đang là giá trị mẫu, hãy điền key thật vào .env"
    else:
        key_status = "chưa có — xem .env.example"
    out(f"API key : {key_status}")
    out(f"Model   : {config.OPENAI_MODEL}")
    out(
        f"Mục tiêu: {config.QUIZ_TARGET_CORRECT} câu đúng mỗi lần mở máy, "
        f"bài đọc trình độ {config.READING_LEVEL}"
    )
    out("Gốc    : " + config.native_label())
    out("Học    : " + ", ".join(languages.resolve_language(code).label for code in config.study_codes()))
    out(f"Hôm nay : đã ôn {summary['asked_today']} từ, "
          f"bài đọc {'xong' if summary['reading_done'] else 'chưa xong'}")

    # Phase 17B: Listening / Windows local TTS capability (no console flash).
    out("\nListening TTS:")
    try:
        from listening import resolve_listening_audio_provider

        provider = resolve_listening_audio_provider()
        if provider is None or not provider.is_available():
            out("  provider: unavailable")
        else:
            out(f"  provider: {type(provider).__name__}")
            for lang in languages.SUPPORTED_LANGUAGES:
                if provider.supports(lang.code):
                    out(f"  {lang.code} ({lang.label}): available")
                else:
                    out(f"  {lang.code} ({lang.label}): missing voice")
            # Optional audible self-test for frozen/source packaging QA.
            if os.environ.get("STUDYGUARD_TTS_SELFTEST", "").strip() == "1":
                speak_code = next(
                    (lang.code for lang in languages.SUPPORTED_LANGUAGES if provider.supports(lang.code)),
                    None,
                )
                if speak_code is None:
                    out("  selftest: skipped (no supported voice)")
                else:
                    provider.play(
                        "StudyGuard listening self test.",
                        speak_code,
                    )
                    out(f"  selftest: played ({speak_code})")
    except Exception as error:
        out(f"  provider error: {type(error).__name__}")

    # Windowed frozen exe has no console; persist output for packaging QA.
    try:
        report = os.path.join(config.data_dir(), "diagnostics_last.txt")
        with open(report, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
        out(f"\nĐã ghi: {report}")
    except Exception:
        pass


def main():
    import sys

    from home_app import FreeHome

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
