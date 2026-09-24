"""Màn hình luyện đọc.

Bài đọc được AI viết mới dựa trên chính những từ bạn vừa kiểm tra hôm nay,
nên phần đọc luôn bám sát phần từ vựng.
"""

import re
import tkinter as tk
from tkinter import ttk

import config
import dictionary
import reading_source
import ui_common
from progress import Progress
from reading_schema import count_questions
from text_utils import sentence_around, strip_tags, without_article
from vocab_store import VocabStore


class ReadingApp:
    def __init__(
        self,
        window: tk.Misc,
        store: VocabStore = None,
        progress: Progress = None,
        on_completed=None,
        on_request_switch=None,
        on_emergency=None,
        required=True,
    ):
        self.window = window
        self.window.title(f"{config.APP_NAME} — {config.ui('Đọc', 'Reading')}")

        self.store = store or VocabStore()
        self.progress = progress or Progress()

        self.on_completed = on_completed
        self.on_request_switch = on_request_switch
        self.on_emergency = on_emergency
        self.required = required

        self.completed = False
        self.test = None
        self.group_states = []
        self.translation_visible = False
        self._loading = False

        ui_common.apply_theme(window)
        self.guard = ui_common.ScreenGuard(window, on_close_attempt=self._on_close_attempt)

        self.container = ttk.Frame(window, padding=16)
        self.container.pack(fill=tk.BOTH, expand=True)

        self.loading_view = self._build_loading_view()
        self.test_view = None
        self._show(self.loading_view)

        self._load_test(force_new=False)

    # ============================================================
    # Khung chờ
    # ============================================================

    def _build_loading_view(self) -> ttk.Frame:
        view = ttk.Frame(self.container)

        holder = ttk.Frame(view)
        holder.place(relx=0.5, rely=0.42, anchor="center")

        ttk.Label(
            holder,
            text=config.ui(
                f"Luyện đọc {config.current_language()['name_vi']}",
                f"{config.language_name(config.active_code())} reading",
            ),
            style="Title.TLabel",
        ).pack()
        self.loading_label = ttk.Label(holder, text="", style="H2.TLabel", justify="center")
        self.loading_label.pack(pady=14)

        self.loading_bar = ttk.Progressbar(holder, mode="indeterminate", length=340)
        self.loading_bar.pack(pady=6)

        self.loading_detail = ttk.Label(
            holder, text="", style="Muted.TLabel", justify="center", wraplength=620
        )
        self.loading_detail.pack(pady=10)

        self.loading_buttons = ttk.Frame(holder)
        self.loading_buttons.pack(pady=10)

        return view

    def _show(self, view: ttk.Frame):
        for other in (self.loading_view, self.test_view):
            if other is not None and other is not view:
                other.pack_forget()
        view.pack(fill=tk.BOTH, expand=True)

    # ============================================================
    # Nạp bài đọc
    # ============================================================

    def _load_test(self, force_new: bool):
        if self._loading:
            return
        self._loading = True

        for child in self.loading_buttons.winfo_children():
            child.destroy()
        self._show(self.loading_view)

        word_count = len(reading_source.select_words(self.store, self.progress))
        self.loading_label.config(
            text=config.ui(
                f"Đang soạn bài đọc từ {word_count} từ bạn vừa học…",
                f"Preparing a reading from {word_count} words you just studied…",
            )
        )
        self.loading_detail.config(
            text=config.ui(
                "AI viết bài mất khoảng 20–40 giây, bạn chờ một chút nhé.",
                "The AI needs about 20–40 seconds to write the passage.",
            )
        )
        self.loading_bar.start(12)

        ui_common.run_async(
            self.window,
            lambda: reading_source.build_test(self.store, self.progress, force_new=force_new),
            self._on_test_ready,
            self._on_test_error,
        )

    def _on_test_ready(self, test: dict):
        self._loading = False
        self.loading_bar.stop()
        self.test = test
        self.group_states = []

        if self.test_view is not None:
            self.test_view.destroy()
        self.test_view = self._build_test_view()
        self._show(self.test_view)

    def _on_test_error(self, error: Exception):
        self._loading = False
        self.loading_bar.stop()
        self.loading_label.config(text=config.ui("Chưa tạo được bài đọc", "Couldn't create a reading"))
        self.loading_detail.config(text=str(error))

        ttk.Button(
            self.loading_buttons,
            text=config.ui("Thử lại", "Try again"),
            command=lambda: self._load_test(True),
        ).pack(side=tk.LEFT, padx=6)
        if self.on_request_switch is not None:
            ttk.Button(
                self.loading_buttons,
                text=config.ui("Sang phần từ vựng", "Go to vocabulary"),
                command=self.on_request_switch,
            ).pack(side=tk.LEFT, padx=6)
        ttk.Button(
            self.loading_buttons,
            text=config.ui("Thoát khẩn cấp", "Emergency exit"),
            command=self._emergency_exit,
        ).pack(side=tk.LEFT, padx=6)

    # ============================================================
    # Khung làm bài
    # ============================================================

    def _build_test_view(self) -> ttk.Frame:
        view = ttk.Frame(self.container)

        header = ttk.Frame(view)
        header.pack(fill=tk.X)
        ttk.Label(header, text=self.test["title"], style="Title.TLabel").pack(side=tk.LEFT)

        badge = self.test.get("level") or config.READING_LEVEL
        source = config.ui(
            "AI soạn theo từ vừa học" if self.test.get("source") == "ai" else "bài có sẵn",
            "written from words you just studied" if self.test.get("source") == "ai" else "saved passage",
        )
        ttk.Label(
            header,
            text=config.ui(f"Trình độ {badge} • {source}", f"Level {badge} • {source}"),
            style="Muted.TLabel",
        ).pack(side=tk.RIGHT)

        if self.test.get("warning"):
            ttk.Label(
                view, text=self.test["warning"], style="Muted.TLabel",
                foreground=ui_common.COLOR_WARN, wraplength=1100,
            ).pack(fill=tk.X, pady=(6, 0))

        body = ttk.Frame(view)
        body.pack(fill=tk.BOTH, expand=True, pady=10)

        self._build_passage_panel(body)
        self._build_questions_panel(body)
        self._build_footer(view)
        return view

    # ---------- Bên trái: bài đọc ----------

    def _build_passage_panel(self, parent: ttk.Frame):
        left = ttk.Frame(parent)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 12))

        row = ttk.Frame(left)
        row.pack(fill=tk.X)
        ttk.Label(row, text=config.ui("Bài đọc", "Reading"), style="H2.TLabel").pack(side=tk.LEFT)
        ttk.Label(
            row,
            text=config.ui(
                "Bấm một từ trong bài hoặc trong câu hỏi để tô sáng, dịch hoặc lưu.",
                "Click a word in the passage or the questions to highlight, translate, or save.",
            ),
            style="Muted.TLabel",
        ).pack(side=tk.LEFT, padx=12)
        self.translation_button = ttk.Button(
            row,
            text=config.ui("Hiện bản dịch cả bài", "Show full translation"),
            style="Small.TButton",
            command=self._toggle_translation,
        )
        self.translation_button.pack(side=tk.RIGHT)

        passage_frame = ttk.Frame(left, relief=tk.GROOVE, borderwidth=1)
        passage_frame.pack(fill=tk.BOTH, expand=True, pady=6)
        self.passage_text = ui_common.make_text(
            passage_frame, font=("Georgia", 13), padx=14, pady=12, spacing2=4, spacing3=8
        )
        ui_common.set_text(self.passage_text, self.test["passage"])
        self.passage_text.config(state="normal")
        self.passage_text.bind("<Key>", self._block_passage_edit)
        self.passage_text.tag_configure("picked", background="#fff3bf")
        self.passage_text.bind("<Button-1>", self._on_word_click)
        self._highlight_target_words()
        self._word_popup = None

        self.translation_frame = ttk.Frame(left, relief=tk.GROOVE, borderwidth=1)
        self.translation_text = ui_common.make_text(
            self.translation_frame, font=ui_common.FONT_BODY, height=10, padx=14, pady=10
        )
        ui_common.set_text(self.translation_text, self._translation_content())

    def _translation_content(self) -> str:
        parts = []
        if self.test.get("translation_vi"):
            parts.append(self.test["translation_vi"])
        glossary = self.test.get("glossary") or []
        if glossary:
            lines = "\n".join(
                f"• {g.get('word') or g.get('nl')} — {g['vi']}"
                for g in glossary
                if g.get("word") or g.get("nl")
            )
            parts.append(config.ui(f"Từ khóa trong bài:\n{lines}", f"Key words:\n{lines}"))
        return "\n\n".join(parts) or config.ui(
            "Bài đọc này không kèm bản dịch.",
            "This passage has no full translation.",
        )

    def _toggle_translation(self):
        self.translation_visible = not self.translation_visible
        if self.translation_visible:
            self.translation_frame.pack(fill=tk.BOTH, expand=False, pady=(0, 4))
            self.translation_button.config(text=config.ui("Ẩn bản dịch cả bài", "Hide full translation"))
        else:
            self.translation_frame.pack_forget()
            self.translation_button.config(text=config.ui("Hiện bản dịch cả bài", "Show full translation"))

    def _block_passage_edit(self, event):
        if event.state & 0x4 and event.keysym.lower() in ("c", "a", "insert"):
            return None
        return "break"

    def _on_word_click(self, event):
        widget = event.widget
        index = widget.index(f"@{event.x},{event.y}")
        start = widget.index(f"{index} wordstart")
        end = widget.index(f"{index} wordend")
        raw = widget.get(start, end)
        word = raw.strip(".,;:!?\"'“”«»()[]{}…")
        if not re.search(r"[^\W\d_]", word, re.UNICODE):
            return
        self._open_word_popup(widget, word, start, end, index, event.x_root, event.y_root)

    def _sentence_at(self, widget, index) -> str:
        """Câu chứa chỗ bấm, cắt theo dấu chấm hoặc xuống dòng."""
        passage = widget.get("1.0", "end-1c")
        counted = widget.count("1.0", index, "chars")
        offset = int(counted[0]) if counted else 0
        return sentence_around(passage, offset)

    def _prepare_lookup_text(self, parent, content, font, foreground=None):
        """Ô chữ không sửa được. Bấm một từ thì hiện cùng bảng tô / dịch / lưu như bài đọc."""
        style = ttk.Style()
        background = style.lookup("TFrame", "background") or self.window.cget("bg")
        widget = tk.Text(
            parent,
            wrap="word",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            font=font,
            height=1,
            padx=2,
            pady=1,
            cursor="hand2",
            background=background,
            foreground=foreground or "#1a1a1a",
            insertwidth=0,
            takefocus=0,
        )
        widget.insert("1.0", content or "")
        widget.tag_configure("picked", background="#fff3bf")
        widget.bind("<Key>", self._block_passage_edit)
        widget.bind("<Button-1>", self._on_word_click)
        widget.bind("<MouseWheel>", self._scroll_questions)
        widget.bind("<Configure>", lambda _event, box=widget: self._fit_lookup_height(box))
        return widget

    def _set_lookup_text(self, widget, content):
        widget.config(state="normal")
        widget.delete("1.0", "end")
        if content:
            widget.insert("1.0", content)
        self._fit_lookup_height(widget)

    def _fit_lookup_height(self, widget):
        if widget.winfo_width() <= 20:
            return
        last = widget.dlineinfo("end-1c")
        first = widget.dlineinfo("1.0")
        if not last or not first or first[3] <= 0:
            return
        lines = max(1, int(round((last[1] - first[1]) / first[3])) + 1)
        if int(widget.cget("height")) != lines:
            widget.config(height=lines)

    def _scroll_questions(self, event):
        canvas = getattr(self, "_question_canvas", None)
        if canvas is not None:
            canvas.yview_scroll(int(-event.delta / 120), "units")
        return "break"

    def _open_word_popup(self, widget, word, start, end, index, x_root, y_root):
        if self._word_popup is not None:
            try:
                if self._word_popup.winfo_exists():
                    self._word_popup.destroy()
            except tk.TclError:
                pass

        self.guard.suspend()
        pop = tk.Toplevel(self.window)
        self._word_popup = pop
        pop.resizable(False, False)
        try:
            pop.attributes("-topmost", True)
        except tk.TclError:
            pass
        pop.geometry(f"+{int(x_root)}+{int(y_root)}")

        closed = {"done": False}

        def close(_event=None):
            if closed["done"]:
                return
            closed["done"] = True
            try:
                if pop.winfo_exists():
                    pop.destroy()
            except tk.TclError:
                pass
            self.guard.resume(refocus=False)

        pop.protocol("WM_DELETE_WINDOW", close)
        pop.bind("<Destroy>", lambda event: close() if event.widget is pop else None)
        pop.bind("<Escape>", close)

        body = ttk.Frame(pop, padding=12)
        body.pack()
        ttk.Label(body, text=word, style="H2.TLabel").pack(anchor="w")
        result_label = ttk.Label(body, text="", wraplength=420, justify="left")
        result_label.pack(anchor="w", pady=(6, 4))

        meaning_var = tk.StringVar()
        meaning_row = ttk.Frame(body)
        ttk.Entry(meaning_row, textvariable=meaning_var, width=48, font=ui_common.FONT_BODY).pack(anchor="w")

        def show_meaning_field():
            if not meaning_row.winfo_ismapped():
                meaning_row.pack(anchor="w", pady=(4, 0))

        def toggle_highlight():
            if "picked" in widget.tag_names(start):
                widget.tag_remove("picked", start, end)
            else:
                widget.tag_add("picked", start, end)

        source = config.active_code()
        native = config.native_code()

        def translate_word():
            result_label.config(text=config.ui("Đang dịch từ…", "Translating word…"))
            show_meaning_field()

            def show(glosses):
                if closed["done"]:
                    return
                self._show_word_glosses(result_label, meaning_var, glosses, source, native)

            def failed(error):
                if not closed["done"]:
                    result_label.config(text=str(error))

            ui_common.run_async(
                pop, lambda: dictionary.lookup(word, source, native), show, failed
            )

        def translate_sentence():
            sentence = self._sentence_at(widget, index)
            if not sentence:
                result_label.config(text=config.ui("Không thấy câu quanh từ này.", "No sentence around this word."))
                return
            result_label.config(text=config.ui("Đang dịch câu…", "Translating sentence…"))

            def show(text):
                if closed["done"]:
                    return
                if text:
                    result_label.config(text=f"{sentence}\n\n{text}")
                else:
                    result_label.config(text=config.ui(
                        f"Không dịch được câu:\n{sentence}",
                        f"Couldn't translate:\n{sentence}",
                    ))

            def failed(error):
                if not closed["done"]:
                    result_label.config(text=str(error))

            ui_common.run_async(
                pop,
                lambda: dictionary.translate_sentence(sentence, source, native),
                show,
                failed,
            )

        def add_word():
            show_meaning_field()
            if self.store.index_of(word) is not None:
                result_label.config(text=config.ui(
                    "Từ này đã có trong danh sách.",
                    "This word is already in your list.",
                ))
                return
            if not meaning_var.get().strip():
                result_label.config(text=config.ui(
                    "Hãy dịch từ hoặc tự gõ nghĩa, rồi bấm Lưu.",
                    "Translate the word or type a meaning, then press Save.",
                ))
                return
            if not self.store.add(word, meaning_var.get().strip()):
                result_label.config(text=config.ui(
                    "Chưa lưu được từ này.",
                    "Couldn't save this word.",
                ))
                return
            result_label.config(text=config.ui(
                "Đã thêm vào danh sách từ.",
                "Saved to your word list.",
            ))

        buttons = ttk.Frame(body)
        buttons.pack(anchor="w", pady=(8, 0))
        ttk.Button(buttons, text=config.ui("Tô sáng", "Highlight"), command=toggle_highlight).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(buttons, text=config.ui("Dịch từ", "Translate word"), command=translate_word).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(
            buttons, text=config.ui("Dịch câu", "Translate sentence"), command=translate_sentence
        ).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(buttons, text=config.ui("Lưu từ", "Save word"), command=add_word).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(buttons, text=config.ui("Đóng", "Close"), command=close).pack(side=tk.LEFT)

        pop.focus_set()
        pop.wait_window()

    def _show_word_glosses(self, label, meaning_var, glosses, source, native):
        native_name = "English" if native == "en" else "tiếng Việt"
        if source == native:
            label.config(text=config.ui(
                "Đây là ngôn ngữ gốc, không cần dịch.",
                "This is already your language.",
            ))
            return
        if not glosses:
            label.config(text=config.ui(
                f"Không thấy trong từ điển {native_name}.",
                f"Not in the {native_name} dictionary.",
            ))
            return
        label.config(text="\n".join(f"• {item}" for item in glosses))
        if not meaning_var.get():
            meaning_var.set(glosses[0])

    def _highlight_target_words(self):
        """Tô đậm các từ mục tiêu để dễ thấy chúng được dùng thế nào."""
        words = self.test.get("target_words") or []
        if not words:
            return

        self.passage_text.tag_configure(
            "target", font=("Georgia", 13, "bold"), foreground=ui_common.COLOR_ACCENT
        )
        for raw in words:
            needle = without_article(strip_tags(raw).lower())
            if len(needle) < 3:
                continue
            start = "1.0"
            while True:
                position = self.passage_text.search(
                    needle, start, stopindex="end", nocase=True
                )
                if not position:
                    break
                end = f"{position}+{len(needle)}c"
                self.passage_text.tag_add("target", position, end)
                start = end

    # ---------- Bên phải: câu hỏi ----------

    def _build_questions_panel(self, parent: ttk.Frame):
        right = ttk.Frame(parent, width=520)
        right.pack(side=tk.RIGHT, fill=tk.BOTH)
        right.pack_propagate(False)

        ttk.Label(right, text=config.ui("Câu hỏi", "Questions"), style="H2.TLabel").pack(anchor="w")
        ttk.Label(
            right,
            text=config.ui(
                "Bấm một từ ở đây cũng tô sáng, dịch hoặc lưu được.",
                "Click a word here to highlight, translate, or save it too.",
            ),
            style="Muted.TLabel",
            wraplength=480,
        ).pack(anchor="w")

        scroller = ui_common.ScrollableFrame(right)
        self._question_canvas = scroller.canvas
        scroller.pack(fill=tk.BOTH, expand=True, pady=6)

        for group in self.test["groups"]:
            if group["kind"] == "matching":
                self._build_matching_group(scroller.body, group)
            else:
                self._build_choice_group(scroller.body, group)

    def _build_matching_group(self, parent: ttk.Frame, group: dict):
        frame = ttk.LabelFrame(parent, text=group["title"], padding=8)
        frame.pack(fill=tk.X, pady=6, padx=4)

        if group["instructions"]:
            instructions = self._prepare_lookup_text(
                frame, group["instructions"], ui_common.FONT_SMALL, ui_common.COLOR_MUTED
            )
            instructions.pack(fill=tk.X, pady=(0, 6))

        options_frame = ttk.Frame(frame)
        options_frame.pack(fill=tk.X, pady=(0, 8))
        for option in group["options"]:
            option_row = ttk.Frame(options_frame)
            option_row.pack(fill=tk.X, pady=1)
            ttk.Label(option_row, text=f"{option['code']}.", width=4).pack(side=tk.LEFT, anchor="n")
            option_text = self._prepare_lookup_text(
                option_row, option["text"], ui_common.FONT_SMALL, ui_common.COLOR_MUTED
            )
            option_text.pack(side=tk.LEFT, fill=tk.X, expand=True)

        codes = [o["code"] for o in group["options"]]
        variables, marks = [], []

        for index, prompt in enumerate(group["prompts"]):
            row = ttk.Frame(frame)
            row.pack(fill=tk.X, pady=3)

            ttk.Label(row, text=str(prompt["number"]), width=3).pack(side=tk.LEFT)

            var = tk.StringVar()
            combo = ttk.Combobox(
                row, values=codes, textvariable=var, state="readonly", width=6
            )
            combo.pack(side=tk.LEFT, padx=6)
            self.guard.track_combobox(combo)
            variables.append(var)

            prompt_text = self._prepare_lookup_text(row, prompt["text"], ui_common.FONT_BODY)
            prompt_text.pack(side=tk.LEFT, fill=tk.X, expand=True)

            mark = ttk.Label(row, text="", width=2)
            mark.pack(side=tk.RIGHT)
            marks.append(mark)

        self.group_states.append(
            {
                "vars": variables,
                "answers": group["answers"],
                "marks": marks,
                "explanations": group.get("explanations") or [],
                "explain_labels": [],
            }
        )

    def _build_choice_group(self, parent: ttk.Frame, group: dict):
        frame = ttk.LabelFrame(parent, text=group["title"], padding=8)
        frame.pack(fill=tk.X, pady=6, padx=4)

        if group["instructions"]:
            instructions = self._prepare_lookup_text(
                frame, group["instructions"], ui_common.FONT_SMALL, ui_common.COLOR_MUTED
            )
            instructions.pack(fill=tk.X, pady=(0, 6))

        variables, answers, marks, explanations, explain_labels = [], [], [], [], []

        for question in group["questions"]:
            block = ttk.Frame(frame)
            block.pack(fill=tk.X, pady=(6, 2))

            title_row = ttk.Frame(block)
            title_row.pack(fill=tk.X)
            ttk.Label(title_row, text=f"{question['number']}.", width=4).pack(side=tk.LEFT, anchor="n")
            prompt_text = self._prepare_lookup_text(title_row, question["prompt"], ui_common.FONT_BODY)
            prompt_text.pack(side=tk.LEFT, fill=tk.X, expand=True)

            mark = ttk.Label(title_row, text="", width=2)
            mark.pack(side=tk.RIGHT)
            marks.append(mark)

            var = tk.StringVar()
            for option in question["options"]:
                option_row = ttk.Frame(block)
                option_row.pack(fill=tk.X, padx=12)
                ttk.Radiobutton(
                    option_row, text=option["key"], variable=var, value=option["key"],
                ).pack(side=tk.LEFT, anchor="n")
                option_text = self._prepare_lookup_text(option_row, option["text"], ui_common.FONT_BODY)
                option_text.pack(side=tk.LEFT, fill=tk.X, expand=True)

            explain = self._prepare_lookup_text(
                block, "", ui_common.FONT_SMALL, ui_common.COLOR_MUTED
            )
            explain_labels.append(explain)

            variables.append(var)
            answers.append(question["answer"])
            explanations.append(question.get("explanation", ""))

        self.group_states.append(
            {
                "vars": variables,
                "answers": answers,
                "marks": marks,
                "explanations": explanations,
                "explain_labels": explain_labels,
            }
        )

    # ---------- Thanh nút ----------

    def _build_footer(self, parent: ttk.Frame):
        footer = ttk.Frame(parent)
        footer.pack(fill=tk.X)

        ttk.Button(footer, text=config.ui("Chấm bài", "Check answers"), command=self._check_answers).pack(side=tk.LEFT)
        ttk.Button(
            footer, text=config.ui("Tạo bài đọc mới", "New passage"), style="Small.TButton",
            command=lambda: self._load_test(True),
        ).pack(side=tk.LEFT, padx=6)

        if self.on_request_switch is not None:
            ttk.Button(
                footer, text=config.ui("Sang phần từ vựng", "Go to vocabulary"), style="Small.TButton",
                command=self.on_request_switch,
            ).pack(side=tk.LEFT, padx=6)

        ttk.Button(
            footer, text=config.ui("Thoát khẩn cấp", "Emergency exit"), style="Small.TButton",
            command=self._emergency_exit,
        ).pack(side=tk.RIGHT)

        need = f"{config.READING_PASS_RATIO * 100:.0f}%"
        self.feedback_label = ttk.Label(
            parent,
            text=config.ui(
                f"Cần đúng ít nhất {need} số câu để qua phần này.",
                f"You need at least {need} correct to pass.",
            ),
            style="Muted.TLabel", wraplength=1100, justify="left",
        )
        self.feedback_label.pack(fill=tk.X, pady=(8, 0))

    # ============================================================
    # Chấm bài
    # ============================================================

    def _check_answers(self):
        total = correct = unanswered = 0

        for state in self.group_states:
            for index, var in enumerate(state["vars"]):
                total += 1
                expected = str(state["answers"][index]).strip().upper()
                given = (var.get() or "").strip().upper()
                mark = state["marks"][index]

                if not given:
                    unanswered += 1
                    mark.config(text="•", foreground=ui_common.COLOR_WARN)
                elif given == expected:
                    correct += 1
                    mark.config(text="✔", foreground=ui_common.COLOR_OK)
                else:
                    mark.config(text="✘", foreground=ui_common.COLOR_BAD)

                self._show_explanation(state, index, revealed=bool(given) and given != expected)

        if total == 0:
            return

        ratio = correct / total
        passed = ratio >= config.READING_PASS_RATIO and unanswered == 0

        if passed:
            self.completed = True
            self.progress.mark_reading_done(correct, total)
            self.feedback_label.config(
                text=config.ui(
                    f"Đúng {correct}/{total} câu. Qua phần đọc!",
                    f"{correct}/{total} correct. Reading complete!",
                ),
                foreground=ui_common.COLOR_OK,
            )
            self.guard.show_info(
                config.ui("Xong phần đọc", "Reading complete"),
                config.ui(
                    f"Bạn làm đúng {correct}/{total} câu ({ratio * 100:.0f}%).\n"
                    "Phần luyện đọc lần này đã hoàn thành.",
                    f"You got {correct}/{total} ({ratio * 100:.0f}%).\n"
                    "This reading session is complete.",
                ),
            )
            if callable(self.on_completed):
                self.on_completed()
            self.window.destroy()
            return

        missing = (
            config.ui(f", bỏ trống {unanswered} câu", f", {unanswered} left blank")
            if unanswered else ""
        )
        need = f"{config.READING_PASS_RATIO * 100:.0f}%"
        self.feedback_label.config(
            text=config.ui(
                f"Đúng {correct}/{total} câu ({ratio * 100:.0f}%){missing}. "
                f"Cần {need} để qua. "
                "Các câu sai đã được đánh dấu ✘ kèm giải thích, hãy đọc lại và sửa.",
                f"{correct}/{total} correct ({ratio * 100:.0f}%){missing}. "
                f"You need {need}. "
                "Wrong answers are marked ✘. Read the explanation and try again.",
            ),
            foreground=ui_common.COLOR_BAD,
        )

    def _show_explanation(self, state: dict, index: int, revealed: bool):
        labels = state.get("explain_labels") or []
        if index >= len(labels):
            return
        explanations = state.get("explanations") or []
        text = explanations[index] if index < len(explanations) else ""
        if revealed and text:
            self._set_lookup_text(labels[index], config.ui(f"Gợi ý: {text}", f"Hint: {text}"))
            labels[index].pack(fill=tk.X, padx=18, pady=(2, 0))

    # ============================================================
    # Thoát
    # ============================================================

    def _on_close_attempt(self):
        if self.completed or not self.required:
            self.window.destroy()
            return
        total = count_questions(self.test) if self.test else 0
        self.guard.show_info(
            config.ui("Chưa xong", "Not finished"),
            config.ui(
                f"Hãy hoàn thành bài đọc ({total} câu) trước khi đóng cửa sổ.\n\n"
                "Nếu app bị lỗi, hãy dùng nút “Thoát khẩn cấp”.",
                f"Finish the reading ({total} questions) before closing.\n\n"
                "If the app is stuck, use Emergency exit.",
            ),
        )

    def _emergency_exit(self):
        if not self.guard.confirm_emergency_exit():
            return
        if callable(self.on_emergency):
            self.on_emergency()
        else:
            self.window.destroy()
