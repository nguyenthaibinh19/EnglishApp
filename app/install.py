"""Cài bản .exe lần đầu và từ chối ghi đè bản đã cài.

Chạy từ source (`python main.py`) thì prepare() không làm gì.
Bản đã cài mở bình thường và không tạo lại shortcut Startup.
Một file .exe khác không được ghi đè bản đã cài, không mở bản đó
và không tạo Startup. Shortcut Startup chỉ được ghi khi cài lần đầu.
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
    """Tạo thư mục từng ngôn ngữ và chép bộ từ mẫu nếu chưa có."""
    config.ensure_language_data()


def _startup_dir() -> str:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return ""
    return os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup")


def register_startup(exe_path: str):
    """Tạo shortcut Startup khi chưa có. Không sửa shortcut đã có hoặc shortcut khác."""
    startup = _startup_dir()
    if not startup:
        raise OSError("Không tìm thấy thư mục APPDATA.")

    os.makedirs(startup, exist_ok=True)
    link = os.path.join(startup, "langstudyguard.lnk")
    if os.path.isfile(link):
        raise OSError(
            config.ui(
                "Shortcut Startup đã có sẵn nên không thay đổi.",
                "A Startup shortcut already exists, so it was not changed.",
            )
        )
    try:
        descriptor = os.open(link, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError:
        raise OSError(
            config.ui(
                "Shortcut Startup đã có sẵn nên không thay đổi.",
                "A Startup shortcut already exists, so it was not changed.",
            )
        ) from None
    os.close(descriptor)
    script = (
        "$shell = New-Object -ComObject WScript.Shell; "
        f"$sc = $shell.CreateShortcut({_ps_quote(link)}); "
        f"$sc.TargetPath = {_ps_quote(exe_path)}; "
        f"$sc.Arguments = '--lock'; "
        f"$sc.WorkingDirectory = {_ps_quote(os.path.dirname(exe_path))}; "
        "$sc.Description = 'langstudyguard'; "
        "$sc.WindowStyle = 1; "
        "$sc.Save()"
    )
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            check=True,
            creationflags=flags,
        )
    except Exception:
        try:
            os.remove(link)
        except OSError:
            pass
        raise


def _startup_link_path() -> str:
    startup = _startup_dir()
    if not startup:
        return ""
    return os.path.join(startup, "langstudyguard.lnk")


def _startup_link_exists() -> bool:
    link = _startup_link_path()
    return bool(link) and os.path.isfile(link)


def _notify_existing_installation() -> None:
    """Báo cho người dùng, không nêu mật khẩu hay dữ liệu cài đặt."""
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.withdraw()
    try:
        messagebox.showinfo(
            config.APP_NAME,
            config.ui(
                "langstudyguard đã được cài trên máy này.\n\n"
                "Bản đang mở sẽ không thay thế bản đã cài, không mở bản đó "
                "và không tạo shortcut Startup. Hãy mở bản đã cài.",
                "langstudyguard is already installed on this computer.\n\n"
                "This copy will not replace the installed application, "
                "will not open it, and will not create a Startup shortcut. "
                "Open the installed application instead.",
            ),
        )
    finally:
        root.destroy()


def _notify_existing_startup() -> None:
    """Dừng khi shortcut đã có. Không ghi đè và không nêu dữ liệu nhạy cảm."""
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.withdraw()
    try:
        messagebox.showinfo(
            config.APP_NAME,
            config.ui(
                "Shortcut Startup của langstudyguard đã có sẵn.\n\n"
                "Bản đang mở sẽ không cài, không thay thế bản đã cài "
                "và không sửa shortcut đó.",
                "A langstudyguard Startup shortcut already exists.\n\n"
                "This copy will not install, will not replace an installed "
                "application, and will not change that shortcut.",
            ),
        )
    finally:
        root.destroy()


def _copy_new_install(source: str, dest: str) -> None:
    """Tạo đúng một file mới. File đã có sẵn không bị xóa hay ghi đè."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    descriptor = None
    created = False
    committed = False
    try:
        descriptor = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        created = True
        with os.fdopen(descriptor, "wb") as target:
            descriptor = None
            with open(source, "rb") as incoming:
                shutil.copyfileobj(incoming, target)
            target.flush()
            os.fsync(target.fileno())
        source_size = os.path.getsize(source)
        if source_size <= 0 or os.path.getsize(dest) != source_size:
            raise OSError(
                config.ui(
                    "Bản cài vừa chép chưa đầy đủ.",
                    "The installed copy is incomplete.",
                )
            )
        committed = True
    except FileExistsError:
        raise
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if created and not committed:
            try:
                os.remove(dest)
            except OSError:
                pass


def _discard_incomplete_install(dest: str, *, remove_startup_link: bool) -> None:
    try:
        os.remove(dest)
    except OSError:
        pass
    if not remove_startup_link:
        return
    startup = _startup_dir()
    if not startup:
        return
    try:
        os.remove(os.path.join(startup, "langstudyguard.lnk"))
    except OSError:
        pass


def prepare() -> bool:
    """Chuẩn bị bản .exe.

    Trả về False khi tiến trình này phải thoát: đã có bản cài,
    hoặc vừa cài lần đầu và đã mở bản đó.
    """
    if not config.is_frozen():
        return True

    dest = config.installed_exe()
    current = os.path.abspath(sys.executable)

    if _same_path(current, dest):
        seed_vocab()
        return True

    if os.path.lexists(dest):
        if os.path.isfile(dest):
            _notify_existing_installation()
            return False
        raise OSError(
            config.ui(
                "Đường dẫn bản đã cài tồn tại nhưng không phải file ứng dụng.",
                "The installed application path already exists and is not a file.",
            )
        )

    if not _startup_dir():
        raise OSError("Không tìm thấy thư mục APPDATA.")
    shortcut_existed = _startup_link_exists()
    if shortcut_existed:
        _notify_existing_startup()
        return False

    try:
        _copy_new_install(current, dest)
    except FileExistsError:
        _notify_existing_installation()
        return False

    if _startup_link_exists():
        _discard_incomplete_install(dest, remove_startup_link=False)
        _notify_existing_startup()
        return False

    try:
        register_startup(dest)
    except Exception:
        # register_startup removes only a shortcut it reserved. A pre-existing one stays.
        _discard_incomplete_install(dest, remove_startup_link=False)
        raise

    try:
        subprocess.Popen([dest], cwd=os.path.dirname(dest), close_fds=True)
    except OSError as error:
        _discard_incomplete_install(dest, remove_startup_link=not shortcut_existed)
        raise OSError(
            config.ui(
                "Chưa cài xong vì ứng dụng không mở được.",
                "Installation did not finish because the application could not be started.",
            )
        ) from error
    return False
