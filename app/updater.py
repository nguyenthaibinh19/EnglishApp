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

# Bản onefile thường ~28 MB. Nhỏ hơn mức này gần như chắc là HTML lỗi / tải dở.
_MIN_EXE_BYTES = 8 * 1024 * 1024
# Zip chứa exe; nhỏ hơn mức này gần như không phải bản phát hành thật.
_MIN_ZIP_BYTES = 5 * 1024 * 1024


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


def _pick_asset(release: dict) -> tuple:
    """Trả về (download_url, expected_size, kind) — ưu tiên zip, rồi exe."""
    assets = release.get("assets") or []
    zip_preferred = None
    zip_fallback = None
    exe_preferred = None
    exe_fallback = None
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = str(asset.get("name") or "").lower()
        url = str(asset.get("browser_download_url") or "")
        if not url:
            continue
        size = int(asset.get("size") or 0)
        item = (url, size)
        if name.endswith(".zip"):
            if name == "langstudyguard.zip":
                zip_preferred = item
            elif zip_fallback is None:
                zip_fallback = item
        elif name.endswith(".exe"):
            if name == "langstudyguard.exe":
                exe_preferred = item
            elif exe_fallback is None:
                exe_fallback = item
    if zip_preferred or zip_fallback:
        url, size = zip_preferred or zip_fallback
        return url, size, "zip"
    if exe_preferred or exe_fallback:
        url, size = exe_preferred or exe_fallback
        return url, size, "exe"
    return "", 0, ""


def prompt_if_needed(window: tk.Misc):
    """Hỏi cập nhật nếu GitHub có bản mới hơn bản đang chạy."""

    def work():
        release = _latest_release()
        tag = str(release.get("tag_name") or "")
        if not is_newer(tag, config.APP_VERSION):
            return None
        url, size, kind = _pick_asset(release)
        if not url:
            return None
        return tag, url, size, kind

    def show(found):
        if not found:
            return
        try:
            if not window.winfo_exists():
                return
        except tk.TclError:
            return
        tag, url, size, kind = found
        _offer(window, tag, url, size, kind)

    def failed(_error):
        return

    ui_common.run_async(window, work, show, failed)


def _set_topmost(window, enabled: bool):
    try:
        window.attributes("-topmost", enabled)
    except tk.TclError:
        pass


def _active_guard(window: tk.Misc):
    guard = getattr(window, "_screen_guard", None)
    if guard is not None and getattr(guard, "enabled", False):
        return guard
    return None


def _offer(window, tag: str, url: str, expected_size: int = 0, kind: str = "exe"):
    guard = _active_guard(window)
    if guard is not None:
        guard.suspend(leave_fullscreen=True)
    else:
        _set_topmost(window, False)

    agreed = False
    try:
        agreed = bool(
            messagebox.askyesno(
                config.APP_NAME,
                config.ui(
                    f"Đã có bản {tag}.\n\nBấm Có để tải và thay bản đang chạy. App sẽ mở lại sau khi cài xong.",
                    f"Version {tag} is available.\n\nChoose Yes to download it and replace this copy. The app restarts when the install finishes.",
                ),
                parent=window,
            )
        )
    except tk.TclError:
        agreed = False

    if not agreed:
        if guard is not None:
            guard.resume(refocus=False)
        else:
            _set_topmost(window, True)
        return
    # Giữ suspend trong lúc tải; app sẽ thoát sau khi cài xong.
    _download_and_restart(
        window, url, restore_topmost=(guard is None), expected_size=expected_size, kind=kind
    )


def _assert_exe(path: str) -> None:
    if not os.path.isfile(path) or os.path.getsize(path) < _MIN_EXE_BYTES:
        raise OSError(
            config.ui(
                "File .exe trong bản cập nhật bị thiếu hoặc quá nhỏ.",
                "The .exe inside the update is missing or too small.",
            )
        )
    with open(path, "rb") as handle:
        if handle.read(2) != b"MZ":
            raise OSError(
                config.ui(
                    "File tải về không phải file .exe hợp lệ.",
                    "The downloaded file is not a valid .exe.",
                )
            )


def _extract_exe_from_zip(zip_path: str, dest_exe: str) -> str:
    import zipfile

    with zipfile.ZipFile(zip_path, "r") as archive:
        names = [name for name in archive.namelist() if name.lower().endswith(".exe")]
        if not names:
            raise OSError(
                config.ui(
                    "File zip không chứa langstudyguard.exe.",
                    "The zip file does not contain langstudyguard.exe.",
                )
            )
        preferred = next(
            (name for name in names if os.path.basename(name).lower() == "langstudyguard.exe"),
            names[0],
        )
        if os.path.isfile(dest_exe):
            try:
                os.remove(dest_exe)
            except OSError:
                pass
        with archive.open(preferred) as source, open(dest_exe, "wb") as target:
            while True:
                chunk = source.read(1024 * 256)
                if not chunk:
                    break
                target.write(chunk)
            target.flush()
            os.fsync(target.fileno())
    _assert_exe(dest_exe)
    return dest_exe


def _download_release(url: str, expected_size: int = 0, kind: str = "exe") -> str:
    """Tải zip hoặc exe về thư mục tạm; luôn trả về đường dẫn file .exe sẵn sàng cài."""
    folder = tempfile.gettempdir()
    kind = (kind or "exe").lower()
    suffix = ".zip" if kind == "zip" else ".exe"
    final_path = os.path.join(folder, f"langstudyguard-update{suffix}")
    partial_path = final_path + ".partial"
    if os.path.isfile(partial_path):
        try:
            os.remove(partial_path)
        except OSError:
            pass

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "langstudyguard",
            "Accept": "application/octet-stream",
        },
    )
    with urllib.request.urlopen(request, timeout=180) as response, open(partial_path, "wb") as handle:
        header_size = response.headers.get("Content-Length")
        declared = expected_size or (int(header_size) if header_size and header_size.isdigit() else 0)
        written = 0
        while True:
            chunk = response.read(1024 * 256)
            if not chunk:
                break
            handle.write(chunk)
            written += len(chunk)
        handle.flush()
        os.fsync(handle.fileno())

    minimum = _MIN_ZIP_BYTES if kind == "zip" else _MIN_EXE_BYTES
    if written < minimum:
        try:
            os.remove(partial_path)
        except OSError:
            pass
        raise OSError(
            config.ui(
                f"File tải về quá nhỏ ({written} byte). Có thể mạng bị cắt hoặc GitHub trả trang lỗi.",
                f"Downloaded file is too small ({written} bytes). The network may have dropped or GitHub returned an error page.",
            )
        )
    if declared and abs(written - declared) > 1024:
        try:
            os.remove(partial_path)
        except OSError:
            pass
        raise OSError(
            config.ui(
                f"File tải về không đủ ({written}/{declared} byte). Hãy thử lại.",
                f"Download incomplete ({written}/{declared} bytes). Please try again.",
            )
        )

    if os.path.isfile(final_path):
        try:
            os.remove(final_path)
        except OSError:
            pass
    os.replace(partial_path, final_path)

    if kind == "zip":
        exe_path = os.path.join(folder, "langstudyguard-update.exe")
        return _extract_exe_from_zip(final_path, exe_path)

    _assert_exe(final_path)
    return final_path


def _download_and_restart(
    window, url: str, restore_topmost: bool, expected_size: int = 0, kind: str = "exe"
):
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
        return _download_release(url, expected_size, kind)

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
    if not os.path.isfile(downloaded) or os.path.getsize(downloaded) < _MIN_EXE_BYTES:
        raise OSError(
            config.ui(
                "File cập nhật bị thiếu hoặc quá nhỏ.",
                "The update file is missing or too small.",
            )
        )
    script = os.path.join(tempfile.gettempdir(), "langstudyguard-update.ps1")
    with open(script, "w", encoding="utf-8") as handle:
        handle.write(
            "$processId = [int]$args[0]\n"
            "$source = $args[1]\n"
            "$destination = $args[2]\n"
            "Wait-Process -Id $processId -ErrorAction SilentlyContinue\n"
            "Start-Sleep -Milliseconds 800\n"
            "$deadline = (Get-Date).AddSeconds(45)\n"
            "$copied = $false\n"
            "do {\n"
            "  try {\n"
            "    Copy-Item -LiteralPath $source -Destination $destination -Force -ErrorAction Stop\n"
            "    $copied = $true\n"
            "    break\n"
            "  } catch {\n"
            "    if ((Get-Date) -gt $deadline) { throw }\n"
            "    Start-Sleep -Milliseconds 500\n"
            "  }\n"
            "} while ($true)\n"
            "if (-not $copied) { throw 'Copy failed' }\n"
            "$destSize = (Get-Item -LiteralPath $destination).Length\n"
            "$srcSize = (Get-Item -LiteralPath $source).Length\n"
            "if ($destSize -ne $srcSize) { throw \"Size mismatch: $destSize vs $srcSize\" }\n"
            "Unblock-File -LiteralPath $destination -ErrorAction SilentlyContinue\n"
            "# Chờ Defender / antivirus nhả file trước khi mở.\n"
            "Start-Sleep -Seconds 2\n"
            "$started = $false\n"
            "foreach ($delay in 0, 1500, 3000) {\n"
            "  if ($delay -gt 0) { Start-Sleep -Milliseconds $delay }\n"
            "  try {\n"
            "    Start-Process -FilePath $destination -ErrorAction Stop\n"
            "    $started = $true\n"
            "    break\n"
            "  } catch {\n"
            "    continue\n"
            "  }\n"
            "}\n"
            "if (-not $started) { throw 'Could not start updated app' }\n"
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
