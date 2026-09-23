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
from text_utils import strip_tags, without_article
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
        self.window.title(f"{config.APP_NAME} — Đọc")

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
            text=f"Luyện đọc {config.current_language()['name_vi']}",
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
            text=f"Đang soạn bài đọc từ {word_count} từ bạn vừa học…"
        )
        self.loading_detail.config(text="AI viết bài mất khoảng 20–40 giây, bạn chờ một chút nhé.")
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
        self.loading_label.config(text="Chưa tạo được bài đọc")
        self.loading_detail.config(text=str(error))

        ttk.Button(self.loading_buttons, text="Thử lại", command=lambda: self._load_test(True)).pack(
            side=tk.LEFT, padx=6
        )
        if self.on_request_switch is not None:
            ttk.Button(
                self.loading_buttons, text="Sang phần từ vựng", command=self.on_request_switch
            ).pack(side=tk.LEFT, padx=6)
        ttk.Button(
            self.loading_buttons, text="Thoát khẩn cấp", command=self._emergency_exit
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
        source = "AI soạn theo từ hôm nay" if self.test.get("source") == "ai" else "bài có sẵn"
        ttk.Label(header, text=f"Trình độ {badge} • {source}", style="Muted.TLabel").pack(side=tk.RIGHT)

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
        ttk.Label(row, text="Bài đọc", style="H2.TLabel").pack(side=tk.LEFT)
        ttk.Label(
            row, text="Bấm một từ để tô sáng, xem nghĩa hoặc thêm vào danh sách",
            style="Muted.TLabel",
        ).pack(side=tk.LEFT, padx=12)
        self.translation_button = ttk.Button(
            row, text="Hiện bản dịch & từ khóa", style="Small.TButton",
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
        self.passage_text.bind("<Button-1>", self._on_passage_click)
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
            parts.append(f"Từ khóa trong bài:\n{lines}")
        return "\n\n".join(parts) or "Bài đọc này không kèm bản dịch."

    def _toggle_translation(self):
        self.translation_visible = not self.translation_visible
        if self.translation_visible:
            self.translation_frame.pack(fill=tk.BOTH, expand=False, pady=(0, 4))
            self.translation_button.config(text="Ẩn bản dịch & từ khóa")
        else:
            self.translation_frame.pack_forget()
            self.translation_button.config(text="Hiện bản dịch & từ khóa")

    def _block_passage_edit(self, event):
        if event.state & 0x4 and event.keysym.lower() in ("c", "a", "insert"):
            return None
        return "break"

    def _on_passage_click(self, event):
        index = self.passage_text.index(f"@{event.x},{event.y}")
        start = self.passage_text.index(f"{index} wordstart")
        end = self.passage_text.index(f"{index} wordend")
        raw = self.passage_text.get(start, end)
        word = raw.strip(".,;:!?\"'“”«»()[]{}…")
        if not re.search(r"[^\W\d_]", word, re.UNICODE):
            return
        self._open_word_popup(word, start, end, event.x_root, event.y_root)

    def _open_word_popup(self, word, start, end, x_root, y_root):
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
        gloss_label = ttk.Label(
            body, text="Đang tra từ điển…", wraplength=380, justify="left"
        )
        gloss_label.pack(anchor="w", pady=(6, 8))
        meaning_var = tk.StringVar()
        ttk.Entry(body, textvariable=meaning_var, width=46, font=ui_common.FONT_BODY).pack(anchor="w")

        existing = self.store.index_of(word)
        saved = ""
        if existing is not None:
            entry = self.store.get(existing) or {}
            saved = (entry.get("vi") or "").strip()

        def toggle_highlight():
            if "picked" in self.passage_text.tag_names(start):
                self.passage_text.tag_remove("picked", start, end)
            else:
                self.passage_text.tag_add("picked", start, end)

        def add_word():
            if self.store.index_of(word) is not None:
                gloss_label.config(text="Từ này đã có trong danh sách.")
                return
            if not self.store.add(word, meaning_var.get().strip()):
                gloss_label.config(text="Cần nhập nghĩa trước khi thêm.")
                return
            gloss_label.config(text="Đã thêm vào danh sách từ.")

        buttons = ttk.Frame(body)
        buttons.pack(anchor="w", pady=(10, 0))
        ttk.Button(buttons, text="Tô sáng", command=toggle_highlight).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(buttons, text="Thêm vào danh sách từ", command=add_word).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(buttons, text="Đóng", command=close).pack(side=tk.LEFT)

        source = config.active_code()
        native = config.native_code()
        if source != native:
            ui_common.run_async(
                pop,
                lambda: dictionary.lookup(word, source, native),
                lambda glosses: None if closed["done"] else self._show_glosses(
                    gloss_label, meaning_var, glosses, source, native, saved
                ),
                lambda error: None if closed["done"] else gloss_label.config(text=str(error)),
            )
        else:
            self._show_glosses(gloss_label, meaning_var, [], source, native, saved)

        pop.focus_set()
        pop.wait_window()

    def _show_glosses(self, label, meaning_var, glosses, source, native, saved=""):
        lines = []
        native_name = "English" if native == "en" else "tiếng Việt"
        if glosses:
            lines.append(f"Từ điển ({native_name}):")
            lines.extend(f"• {item}" for item in glosses)
            if not meaning_var.get():
                meaning_var.set(glosses[0])
        elif source == native:
            lines.append("Đây là ngôn ngữ gốc, không cần dịch.")
        else:
            lines.append(f"Không thấy trong từ điển {native_name}.")
        if saved:
            lines.append(f"Trong danh sách của bạn: {saved}")
            if not meaning_var.get():
                meaning_var.set(saved)
        label.config(text="\n".join(lines))

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

        ttk.Label(right, text="Vragen", style="H2.TLabel").pack(anchor="w")

        scroller = ui_common.ScrollableFrame(right)
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
            ttk.Label(frame, text=group["instructions"], style="Muted.TLabel", wraplength=440).pack(
                anchor="w", pady=(0, 6)
            )

        options_frame = ttk.Frame(frame)
        options_frame.pack(fill=tk.X, pady=(0, 8))
        for option in group["options"]:
            ttk.Label(
                options_frame, text=f"{option['code']}. {option['text']}",
                style="Muted.TLabel", wraplength=430, justify="left",
            ).pack(anchor="w")

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

            ttk.Label(row, text=prompt["text"], wraplength=330, justify="left").pack(side=tk.LEFT)

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
            ttk.Label(frame, text=group["instructions"], style="Muted.TLabel", wraplength=440).pack(
                anchor="w", pady=(0, 6)
            )

        variables, answers, marks, explanations, explain_labels = [], [], [], [], []

        for question in group["questions"]:
            block = ttk.Frame(frame)
            block.pack(fill=tk.X, pady=(6, 2))

            title_row = ttk.Frame(block)
            title_row.pack(fill=tk.X)
            ttk.Label(
                title_row, text=f"{question['number']}. {question['prompt']}",
                wraplength=420, justify="left", font=ui_common.FONT_BODY,
            ).pack(side=tk.LEFT, anchor="w")

            mark = ttk.Label(title_row, text="", width=2)
            mark.pack(side=tk.RIGHT)
            marks.append(mark)

            var = tk.StringVar()
            for option in question["options"]:
                ttk.Radiobutton(
                    block, text=f"{option['key']}. {option['text']}",
                    variable=var, value=option["key"],
                ).pack(anchor="w", padx=18)

            explain = ttk.Label(
                block, text="", style="Muted.TLabel", wraplength=420,
                justify="left", foreground=ui_common.COLOR_MUTED,
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

        ttk.Button(footer, text="Chấm bài", command=self._check_answers).pack(side=tk.LEFT)
        ttk.Button(
            footer, text="Tạo bài đọc mới", style="Small.TButton",
            command=lambda: self._load_test(True),
        ).pack(side=tk.LEFT, padx=6)

        if self.on_request_switch is not None:
            ttk.Button(
                footer, text="Sang phần từ vựng", style="Small.TButton",
                command=self.on_request_switch,
            ).pack(side=tk.LEFT, padx=6)

        ttk.Button(
            footer, text="Thoát khẩn cấp", style="Small.TButton", command=self._emergency_exit
        ).pack(side=tk.RIGHT)

        self.feedback_label = ttk.Label(
            parent, text=f"Cần đúng ít nhất {config.READING_PASS_RATIO * 100:.0f}% số câu để qua phần này.",
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
                text=f"Đúng {correct}/{total} câu. Qua phần đọc!", foreground=ui_common.COLOR_OK
            )
            self.guard.show_info(
                "Goed gelezen!",
                f"Bạn làm đúng {correct}/{total} câu ({ratio * 100:.0f}%).\n"
                "Phần luyện đọc lần này đã hoàn thành.",
            )
            if callable(self.on_completed):
                self.on_completed()
            self.window.destroy()
            return

        missing = f", bỏ trống {unanswered} câu" if unanswered else ""
        self.feedback_label.config(
            text=f"Đúng {correct}/{total} câu ({ratio * 100:.0f}%){missing}. "
                 f"Cần {config.READING_PASS_RATIO * 100:.0f}% để qua. "
                 "Các câu sai đã được đánh dấu ✘ kèm giải thích, hãy đọc lại và sửa.",
            foreground=ui_common.COLOR_BAD,
        )

    def _show_explanation(self, state: dict, index: int, revealed: bool):
        labels = state.get("explain_labels") or []
        if index >= len(labels):
            return
        explanations = state.get("explanations") or []
        text = explanations[index] if index < len(explanations) else ""
        if revealed and text:
            labels[index].config(text=f"Gợi ý: {text}")
            labels[index].pack(anchor="w", padx=18, pady=(2, 0))

    # ============================================================
    # Thoát
    # ============================================================

    def _on_close_attempt(self):
        if self.completed or not self.required:
            self.window.destroy()
            return
        total = count_questions(self.test) if self.test else 0
        self.guard.show_info(
            "Chưa xong",
            f"Hãy hoàn thành bài đọc ({total} câu) trước khi đóng cửa sổ.\n\n"
            "Nếu app bị lỗi, hãy dùng nút “Thoát khẩn cấp”.",
        )

    def _emergency_exit(self):
        if not self.guard.confirm_emergency_exit():
            return
        if callable(self.on_emergency):
            self.on_emergency()
        else:
            self.window.destroy()
