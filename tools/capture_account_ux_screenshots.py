"""Capture Guest vs Signed-in Account panel screenshots for acceptance evidence.

Runs headless-friendly Tk windows and grabs PNGs via ImageGrab when available.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

os.environ.setdefault("LG_APP_ENVIRONMENT", "development")
os.environ.setdefault("LOCK_SCREEN", "0")
os.environ.setdefault("ACCOUNT_SERVER_URL", "http://127.0.0.1:8765")

import tkinter as tk
from tkinter import ttk

import config
import ui_common
from account_panel import AccountPanel


OUT = ROOT / "qa-evidence" / "account-ux-release" / "screenshots"


def _grab(path: Path, root: tk.Tk) -> bool:
    root.update_idletasks()
    root.update()
    try:
        from PIL import ImageGrab
    except ImportError:
        path.write_text("ImageGrab unavailable — text evidence only.\n", encoding="utf-8")
        return False
    x = root.winfo_rootx()
    y = root.winfo_rooty()
    w = root.winfo_width()
    h = root.winfo_height()
    image = ImageGrab.grab(bbox=(x, y, x + w, y + h))
    image.save(path)
    return True


def _window(title: str) -> tuple[tk.Tk, AccountPanel]:
    root = tk.Tk()
    root.title(title)
    ui_common.apply_theme(root)
    frame = ttk.Frame(root, padding=16)
    frame.pack(fill=tk.BOTH, expand=True)
    ttk.Label(frame, text=title, style="Title.TLabel").pack(anchor="w")
    panel = AccountPanel(frame, allow_logout=True)
    panel.pack(fill=tk.X, pady=12)
    root.geometry("520x280+80+80")
    return root, panel


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    lab = Path(tempfile.mkdtemp(prefix="account-ux-shot-"))
    os.environ["LG_DATA_DIR"] = str(lab)
    config.SETTINGS_FILE = str(lab / "settings.json")
    config.reload()

    # Guest
    root, panel = _window("Language Guard — DEVELOPMENT (Guest)")
    panel.refresh()
    root.lift()
    root.attributes("-topmost", True)
    root.update()
    root.after(600, root.quit)
    root.mainloop()
    guest_png = OUT / "01_guest_account_panel.png"
    guest_ok = _grab(guest_png, root)
    guest_text = OUT / "01_guest_account_panel.txt"
    guest_text.write_text(
        f"status={panel.status_label.cget('text')}\n"
        f"detail={panel.detail_label.cget('text')}\n"
        f"sync={panel.sync_label.cget('text')}\n",
        encoding="utf-8",
    )
    root.destroy()

    # Signed-in (synthetic settings only — no network required for UI chrome)
    (lab / "settings.json").write_text(
        json.dumps(
            {
                "account_username": "devtest",
                "account_token": "synthetic-token-not-a-secret-for-ui",
                "account_user_id": 1,
                "environment": "development",
            }
        ),
        encoding="utf-8",
    )
    config.reload()
    # Force signed-in appearance for chrome capture even if token validation would fail.
    import account_session

    account_session.is_signed_in = lambda: True  # type: ignore
    config.account_user_id = lambda: 1  # type: ignore

    root, panel = _window("Language Guard — DEVELOPMENT (Signed in)")
    panel.refresh()
    root.lift()
    root.attributes("-topmost", True)
    root.update()
    root.after(600, root.quit)
    root.mainloop()
    signed_png = OUT / "02_signed_in_account_panel.png"
    signed_ok = _grab(signed_png, root)
    signed_text = OUT / "02_signed_in_account_panel.txt"
    signed_text.write_text(
        f"status={panel.status_label.cget('text')}\n"
        f"detail={panel.detail_label.cget('text')}\n"
        f"sync={panel.sync_label.cget('text')}\n",
        encoding="utf-8",
    )
    root.destroy()

    report = {
        "guest_png": str(guest_png) if guest_ok else None,
        "signed_png": str(signed_png) if signed_ok else None,
        "guest_text": str(guest_text),
        "signed_text": str(signed_text),
    }
    (OUT.parent / "SCREENSHOT_REPORT.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
