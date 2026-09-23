"""Cài bản .exe vào máy người dùng và đăng ký khởi động cùng Windows.

Chạy từ source (`python main.py`) thì các hàm này không làm gì.
"""

import os
import shutil
import subprocess
import sys

import config


def _same_path(a: str, b: str) -> bool:
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def seed_vocab():
    """Chép bộ từ mẫu vào AppData nếu người dùng chưa có file riêng."""
    os.makedirs(config.data_dir(), exist_ok=True)
    if os.path.exists(config.VOCAB_FILE):
        return
    if os.path.exists(config.STARTER_VOCAB_FILE):
        shutil.copy2(config.STARTER_VOCAB_FILE, config.VOCAB_FILE)


def register_startup(exe_path: str):
    """Tạo (hoặc ghi đè) shortcut trong thư mục Startup của user hiện tại."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise OSError("Không tìm thấy thư mục APPDATA.")

    startup = os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
    os.makedirs(startup, exist_ok=True)
    link = os.path.join(startup, "Dutch Guard.lnk")
    script = (
        "$shell = New-Object -ComObject WScript.Shell; "
        f"$sc = $shell.CreateShortcut({_ps_quote(link)}); "
        f"$sc.TargetPath = {_ps_quote(exe_path)}; "
        f"$sc.WorkingDirectory = {_ps_quote(os.path.dirname(exe_path))}; "
        "$sc.Description = 'Dutch Guard'; "
        "$sc.WindowStyle = 1; "
        "$sc.Save()"
    )
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        check=True,
        creationflags=flags,
    )


def prepare() -> bool:
    """Chuẩn bị bản .exe. Trả về False nếu tiến trình này phải thoát (đã mở bản đã cài)."""
    if not config.is_frozen():
        return True

    dest = config.installed_exe()
    current = os.path.abspath(sys.executable)
    os.makedirs(os.path.dirname(dest), exist_ok=True)

    if not _same_path(current, dest):
        shutil.copy2(current, dest)
        subprocess.Popen([dest], cwd=os.path.dirname(dest), close_fds=True)
        return False

    seed_vocab()
    register_startup(dest)
    return True
