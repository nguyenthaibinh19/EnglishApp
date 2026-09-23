"""Lần đầu mở app: chọn ngôn ngữ gốc, ngôn ngữ cần học, rồi tải đúng từ điển đó."""

import tkinter as tk
from tkinter import ttk

import config
import dictionary
import languages
import ui_common


def run(root: tk.Tk) -> bool:
    """Hỏi ngôn ngữ và tải từ điển. Trả về True khi đã lưu lựa chọn."""
    root.title(config.APP_NAME)
    ui_common.apply_theme(root)
    guard = ui_common.ScreenGuard(root, on_close_attempt=lambda: None)

    done = {"ok": False}
    chosen = []

    backdrop = ttk.Frame(root)
    backdrop.pack(fill=tk.BOTH, expand=True)
    card = ttk.Frame(backdrop, padding=28)
    card.place(relx=0.5, rely=0.5, anchor="center")

    ttk.Label(card, text="Chọn ngôn ngữ", style="Title.TLabel").pack(anchor="w")
    ttk.Label(
        card,
        text=(
            "Chọn ngôn ngữ gốc để dịch nghĩa, rồi chọn những tiếng muốn học. "
            "App chỉ tải từ điển của các tiếng đó, không tải hết mọi ngôn ngữ."
        ),
        style="Muted.TLabel",
        wraplength=560,
        justify="left",
    ).pack(anchor="w", pady=(8, 16))

    native_row = ttk.Frame(card)
    native_row.pack(anchor="w", fill=tk.X)
    ttk.Label(native_row, text="Ngôn ngữ gốc").pack(side=tk.LEFT)
    native_var = tk.StringVar(value="Tiếng Việt")
    native_box = ttk.Combobox(
        native_row,
        textvariable=native_var,
        values=["Tiếng Việt", "English"],
        state="readonly",
        width=24,
    )
    native_box.pack(side=tk.LEFT, padx=(10, 0))
    guard.track_combobox(native_box)

    add_row = ttk.Frame(card)
    add_row.pack(anchor="w", fill=tk.X, pady=(14, 6))
    ttk.Label(add_row, text="Thêm ngôn ngữ học").pack(side=tk.LEFT)
    add_var = tk.StringVar()
    add_box = ttk.Combobox(add_row, textvariable=add_var, state="readonly", width=24)
    add_box.pack(side=tk.LEFT, padx=(10, 0))
    guard.track_combobox(add_box)

    chosen_frame = ttk.Frame(card)
    chosen_frame.pack(anchor="w", fill=tk.X, pady=(8, 8))

    status = ttk.Label(card, text="", style="Muted.TLabel", wraplength=560, justify="left")
    status.pack(anchor="w", pady=(4, 8))
    bar = ttk.Progressbar(card, mode="determinate", length=420, maximum=1)
    bar.pack(anchor="w")

    def native_code():
        return "en" if native_var.get() == "English" else "vi"

    def refresh_add_box():
        labels = [
            languages.LANGUAGES[code]["label"]
            for code in languages.codes()
            if code not in chosen
        ]
        add_box.configure(values=labels or ["(đã chọn hết)"])
        add_var.set("")

    def redraw_chosen():
        for child in chosen_frame.winfo_children():
            child.destroy()
        if not chosen:
            ttk.Label(
                chosen_frame, text="Chưa chọn tiếng nào.", style="Muted.TLabel"
            ).pack(anchor="w")
            return
        for code in chosen:
            row = ttk.Frame(chosen_frame)
            row.pack(anchor="w", fill=tk.X, pady=2)
            ttk.Label(row, text=languages.LANGUAGES[code]["label"], width=24).pack(side=tk.LEFT)

            def remove(code=code):
                if code in chosen:
                    chosen.remove(code)
                redraw_chosen()
                refresh_add_box()

            ttk.Button(row, text="Bỏ", style="Small.TButton", command=remove).pack(side=tk.LEFT)

    def on_add(_event=None):
        label = add_var.get()
        code = next(
            (item for item, profile in languages.LANGUAGES.items() if profile["label"] == label),
            None,
        )
        if code and code not in chosen:
            chosen.append(code)
            redraw_chosen()
            refresh_add_box()

    add_box.bind("<<ComboboxSelected>>", on_add)
    refresh_add_box()
    redraw_chosen()

    busy = {"value": False}

    def finish_ok():
        config.save_language_choices(native_code(), chosen)
        done["ok"] = True
        root.quit()

    def on_downloaded(_value):
        busy["value"] = False
        status.config(text="Đã tải và kiểm tra từ điển.")
        bar.config(value=1)
        finish_ok()

    def on_failed(error):
        busy["value"] = False
        status.config(text=str(error))
        bar.config(value=0)

    def start():
        if busy["value"]:
            return
        if not chosen:
            status.config(text="Hãy thêm ít nhất một ngôn ngữ để học.")
            return
        pairs = [(code, native_code()) for code in chosen if code != native_code()]
        missing = [pair for pair in pairs if not dictionary.is_ready(*pair)]
        if not missing:
            finish_ok()
            return
        busy["value"] = True
        status.config(text="Đang tải từ điển…")

        def work():
            count = len(missing)
            for index, (source, native) in enumerate(missing):
                label = languages.LANGUAGES[source]["label"]

                def report(fraction, index=index, label=label):
                    overall = (index + fraction) / count
                    root.after(
                        0, lambda label=label, overall=overall: _show_progress(label, overall)
                    )

                dictionary.install(source, native, report)

        def _show_progress(label, overall):
            status.config(text=f"Đang tải từ điển {label}…")
            bar.config(value=overall)

        ui_common.run_async(root, work, on_downloaded, on_failed)

    ttk.Button(card, text="Tải từ điển và bắt đầu", command=start).pack(anchor="w", pady=(14, 0))

    def emergency():
        if guard.confirm_emergency_exit():
            done["ok"] = False
            root.quit()

    ttk.Button(
        backdrop, text="Thoát khẩn cấp", style="Small.TButton", command=emergency
    ).place(relx=1.0, rely=1.0, x=-24, y=-24, anchor="se")

    root.mainloop()
    backdrop.destroy()
    root.unbind("<FocusOut>")
    root.unbind("<Alt-F4>")
    return done["ok"]
