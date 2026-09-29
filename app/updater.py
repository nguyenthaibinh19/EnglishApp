"""Báo và cài bản mới từ GitHub Releases khi người dùng mở app.

Chỉ chạy trong file .exe. Máy dev (`python main.py`) không tự thay file.
"""

import json
import os
import subprocess
import sys
import tempfile
import urllib.request

import tkinter as tk
from tkinter import messagebox, ttk

import config
import ui_common


def parse_version(value: str) -> tuple:
    numbers = []
    for piece in str(value or "").strip().lstrip("vV").split("."):
        digits = ""
        for char in piece:
            if char.isdigit():
                digits += char
            else:
                break
        if digits:
            numbers.append(int(digits))
    return tuple(numbers)


def is_newer(remote: str, local: str) -> bool:
    left = parse_version(remote)
    right = parse_version(local)
    width = max(len(left), len(right))
    left = left + (0,) * (width - len(left))
    right = right + (0,) * (width - len(right))
    return left > right


def _latest_release() -> dict:
    url = f"https://api.github.com/repos/{config.UPDATE_REPO}/releases/latest"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "langstudyguard",
        },
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Phản hồi không hợp lệ.")
    return payload


def _asset_url(release: dict) -> str:
    assets = release.get("assets") or []
    preferred = ""
    fallback = ""
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = str(asset.get("name") or "")
        url = str(asset.get("browser_download_url") or "")
        if not name.lower().endswith(".exe") or not url:
            continue
        if name.lower() == "langstudyguard.exe":
            preferred = url
        elif not fallback:
            fallback = url
    return preferred or fallback


def prompt_if_needed(window: tk.Misc):
    """Hỏi cập nhật nếu GitHub có bản mới hơn bản đang chạy."""

    def work():
        release = _latest_release()
        tag = str(release.get("tag_name") or "")
        if not is_newer(tag, config.APP_VERSION):
            return None
        url = _asset_url(release)
        if not url:
            return None
        return tag, url

    def show(found):
        if not found:
            return
        try:
            if not window.winfo_exists():
                return
        except tk.TclError:
            return
        tag, url = found
        _offer(window, tag, url)

    def failed(_error):
        return

    ui_common.run_async(window, work, show, failed)


def _set_topmost(window, enabled: bool):
    try:
        window.attributes("-topmost", enabled)
    except tk.TclError:
        pass


def _offer(window, tag: str, url: str):
    was_topmost = False
    try:
        was_topmost = bool(window.attributes("-topmost"))
    except tk.TclError:
        pass
    _set_topmost(window, False)
    agreed = messagebox.askyesno(
        config.APP_NAME,
        config.ui(
            f"Đã có bản {tag}.\n\nBấm Có để tải và thay bản đang chạy. App sẽ mở lại sau khi cài xong.",
            f"Version {tag} is available.\n\nChoose Yes to download it and replace this copy. The app restarts when the install finishes.",
        ),
        parent=window,
    )
    if not agreed:
        if was_topmost:
            _set_topmost(window, True)
        return
    _download_and_restart(window, url, was_topmost)


def _download_and_restart(window, url: str, restore_topmost: bool):
    dialog = tk.Toplevel(window)
    dialog.title(config.APP_NAME)
    dialog.resizable(False, False)
    dialog.transient(window)
    try:
        dialog.attributes("-topmost", True)
    except tk.TclError:
        pass
    frame = ttk.Frame(dialog, padding=16)
    frame.pack()
    label = ttk.Label(frame, text=config.ui("Đang tải bản mới…", "Downloading the new version…"))
    label.pack(anchor="w")
    bar = ttk.Progressbar(frame, mode="indeterminate", length=320)
    bar.pack(fill=tk.X, pady=(8, 0))
    bar.start(12)
    dialog.update_idletasks()

    def work():
        path = os.path.join(tempfile.gettempdir(), "langstudyguard-update.exe")
        request = urllib.request.Request(url, headers={"User-Agent": "langstudyguard"})
        with urllib.request.urlopen(request, timeout=120) as response, open(path, "wb") as handle:
            while True:
                chunk = response.read(1024 * 256)
                if not chunk:
                    break
                handle.write(chunk)
        return path

    def ok(path):
        try:
            dialog.destroy()
        except tk.TclError:
            pass
        try:
            _swap_and_restart(path)
        except OSError as error:
            messagebox.showerror(
                config.APP_NAME,
                config.ui(f"Không cài được bản mới:\n{error}", f"Couldn't install the update:\n{error}"),
                parent=window,
            )
            if restore_topmost:
                _set_topmost(window, True)
            return
        window.destroy()

    def failed(error):
        try:
            dialog.destroy()
        except tk.TclError:
            pass
        messagebox.showerror(
            config.APP_NAME,
            config.ui(f"Không tải được bản mới:\n{error}", f"Couldn't download the update:\n{error}"),
            parent=window,
        )
        if restore_topmost:
            _set_topmost(window, True)

    ui_common.run_async(dialog, work, ok, failed)


def _swap_and_restart(downloaded: str):
    """Thoát app, rồi để PowerShell ghi đè file exe đang chạy và mở lại."""
    destination = config.installed_exe() if config.is_frozen() else os.path.abspath(sys.executable)
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    script = os.path.join(tempfile.gettempdir(), "langstudyguard-update.ps1")
    with open(script, "w", encoding="utf-8") as handle:
        handle.write(
            "$processId = [int]$args[0]\n"
            "$source = $args[1]\n"
            "$destination = $args[2]\n"
            "Wait-Process -Id $processId -ErrorAction SilentlyContinue\n"
            "$deadline = (Get-Date).AddSeconds(30)\n"
            "do {\n"
            "  try {\n"
            "    Copy-Item -LiteralPath $source -Destination $destination -Force -ErrorAction Stop\n"
            "    break\n"
            "  } catch {\n"
            "    if ((Get-Date) -gt $deadline) { throw }\n"
            "    Start-Sleep -Milliseconds 400\n"
            "  }\n"
            "} while ($true)\n"
            "Start-Process -FilePath $destination\n"
            "Remove-Item -LiteralPath $source -Force -ErrorAction SilentlyContinue\n"
            "Remove-Item -LiteralPath $MyInvocation.MyCommand.Path -Force -ErrorAction SilentlyContinue\n"
        )
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            script,
            str(os.getpid()),
            downloaded,
            destination,
        ],
        creationflags=flags,
        close_fds=True,
    )
