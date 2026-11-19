"""Capture actual FreeHome and StudyMaster windows (Guest + Signed-in).

Full-window acceptance evidence — not the isolated AccountPanel component alone.
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
os.environ.setdefault("STUDY_SYNC_ENABLED", "0")

import tkinter as tk

import config
import ui_common


OUT = ROOT / "qa-evidence" / "account-ux-release" / "screenshots"


def _grab(path: Path, root: tk.Misc) -> bool:
    root.update_idletasks()
    root.update()
    try:
        from PIL import ImageGrab
    except ImportError:
        path.write_text("ImageGrab unavailable — text evidence only.\n", encoding="utf-8")
        return False
    x = int(root.winfo_rootx())
    y = int(root.winfo_rooty())
    w = max(int(root.winfo_width()), 1)
    h = max(int(root.winfo_height()), 1)
    image = ImageGrab.grab(bbox=(x, y, x + w, y + h))
    image.save(path)
    return True


def _evidence_text(path: Path, *, title: str, account_panel) -> None:
    status = detail = sync = ""
    try:
        status = account_panel.status_label.cget("text")
        detail = account_panel.detail_label.cget("text")
        sync = account_panel.sync_label.cget("text")
    except Exception as exc:
        status = f"<unavailable: {exc}>"
    path.write_text(
        f"window={title}\nstatus={status}\ndetail={detail}\nsync={sync}\n",
        encoding="utf-8",
    )


def _show_and_grab(root: tk.Tk, png: Path, settle_ms: int = 700) -> bool:
    root.lift()
    try:
        root.attributes("-topmost", True)
    except tk.TclError:
        pass
    root.update_idletasks()
    root.update()
    root.after(settle_ms, root.quit)
    root.mainloop()
    return _grab(png, root)


def _signed_in_settings(lab: Path) -> None:
    (lab / "settings.json").write_text(
        json.dumps(
            {
                "account_username": "devtest",
                "account_token": "synthetic-token-ui-only",
                "account_user_id": 1,
                "environment": "development",
                "language": "nl",
                "native": "en",
                "study_languages": ["nl"],
            }
        ),
        encoding="utf-8",
    )
    config.reload()
    import account_session

    account_session.is_signed_in = lambda: True  # type: ignore
    config.account_user_id = lambda: 1  # type: ignore
    config.account_token = lambda: "synthetic-token-ui-only"  # type: ignore


def _guest_settings(lab: Path) -> None:
    (lab / "settings.json").write_text(
        json.dumps(
            {
                "environment": "development",
                "language": "nl",
                "native": "en",
                "study_languages": ["nl"],
            }
        ),
        encoding="utf-8",
    )
    config.reload()
    import account_session

    account_session.is_signed_in = lambda: False  # type: ignore
    config.account_user_id = lambda: None  # type: ignore
    config.account_token = lambda: ""  # type: ignore


def _capture_freehome(lab: Path, *, signed_in: bool, stem: str) -> dict:
    from home_app import FreeHome

    if signed_in:
        _signed_in_settings(lab)
    else:
        _guest_settings(lab)

    root = tk.Tk()
    ui_common.apply_theme(root)
    root.geometry("760x640+60+40")
    home = FreeHome(root)
    title = root.title() or ("FreeHome Signed-in" if signed_in else "FreeHome Guest")
    png = OUT / f"{stem}.png"
    txt = OUT / f"{stem}.txt"
    ok = _show_and_grab(root, png)
    _evidence_text(txt, title=title, account_panel=home.account_panel)
    root.destroy()
    return {"png": str(png) if ok else None, "txt": str(txt), "title": title}


def _capture_studymaster(lab: Path, *, signed_in: bool, stem: str) -> dict:
    from main import StudyMasterApp

    if signed_in:
        _signed_in_settings(lab)
    else:
        _guest_settings(lab)

    root = tk.Tk()
    ui_common.apply_theme(root)
    root.geometry("820x700+80+40")
    app = StudyMasterApp(root)
    title = root.title() or ("StudyMaster Signed-in" if signed_in else "StudyMaster Guest")
    png = OUT / f"{stem}.png"
    txt = OUT / f"{stem}.txt"
    ok = _show_and_grab(root, png)
    panel = getattr(app, "account_panel", None)
    _evidence_text(txt, title=title, account_panel=panel)
    try:
        root.destroy()
    except tk.TclError:
        pass
    return {"png": str(png) if ok else None, "txt": str(txt), "title": title}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    lab = Path(tempfile.mkdtemp(prefix="account-ux-fullwin-"))
    os.environ["LG_DATA_DIR"] = str(lab)
    config.SETTINGS_FILE = str(lab / "settings.json")

    report = {
        "freehome_guest": _capture_freehome(lab, signed_in=False, stem="03_freehome_guest"),
        "freehome_signed": _capture_freehome(lab, signed_in=True, stem="04_freehome_signed_in"),
        "studymaster_guest": _capture_studymaster(
            lab, signed_in=False, stem="05_studymaster_guest"
        ),
        "studymaster_signed": _capture_studymaster(
            lab, signed_in=True, stem="06_studymaster_signed_in"
        ),
    }
    (OUT.parent / "SCREENSHOT_REPORT.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
