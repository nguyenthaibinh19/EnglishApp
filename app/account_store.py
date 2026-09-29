"""Tài khoản người dùng. API key không lưu ở đây và không gửi cho người học."""

import hashlib
import hmac
import os
import secrets
import sqlite3
import time

DB_FILE = "accounts.db"
TOKEN_DAYS = 30


def db_path(folder: str = None) -> str:
    root = folder or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(root, DB_FILE)


def connect(folder: str = None) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path(folder))
    connection.row_factory = sqlite3.Row
    connection.execute(
        """CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        )"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            expires_at INTEGER NOT NULL
        )"""
    )
    connection.commit()
    return connection


def _hash_password(password: str, salt: str) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000)
    return digest.hex()


def add_user(username: str, password: str, folder: str = None) -> None:
    name = username.strip().lower()
    if len(name) < 3 or len(password) < 6:
        raise ValueError("Tên tài khoản cần ít nhất 3 ký tự và mật khẩu ít nhất 6 ký tự.")
    salt = secrets.token_hex(16)
    connection = connect(folder)
    try:
        connection.execute(
            "INSERT INTO users (username, password_hash, salt, active, created_at) VALUES (?, ?, ?, 1, ?)",
            (name, _hash_password(password, salt), salt, time.strftime("%Y-%m-%d %H:%M:%S")),
        )
        connection.commit()
    except sqlite3.IntegrityError as error:
        raise ValueError(f"Tài khoản “{name}” đã có.") from error
    finally:
        connection.close()


def list_users(folder: str = None) -> list:
    connection = connect(folder)
    try:
        rows = connection.execute(
            "SELECT username, active, created_at FROM users ORDER BY username"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def set_password(username: str, password: str, folder: str = None) -> None:
    """Đặt mật khẩu mới. Mật khẩu cũ không đọc lại được vì chỉ lưu dạng băm."""
    name = username.strip().lower()
    if len(password) < 6:
        raise ValueError("Mật khẩu cần ít nhất 6 ký tự.")
    salt = secrets.token_hex(16)
    connection = connect(folder)
    try:
        cursor = connection.execute(
            "UPDATE users SET password_hash = ?, salt = ? WHERE username = ?",
            (_hash_password(password, salt), salt, name),
        )
        if cursor.rowcount == 0:
            raise ValueError("Không thấy tài khoản này.")
        connection.execute(
            "DELETE FROM sessions WHERE user_id = (SELECT id FROM users WHERE username = ?)",
            (name,),
        )
        connection.commit()
    finally:
        connection.close()


def set_active(username: str, active: bool, folder: str = None) -> None:
    connection = connect(folder)
    try:
        cursor = connection.execute(
            "UPDATE users SET active = ? WHERE username = ?",
            (1 if active else 0, username.strip().lower()),
        )
        if cursor.rowcount == 0:
            raise ValueError("Không thấy tài khoản này.")
        if not active:
            connection.execute(
                "DELETE FROM sessions WHERE user_id = (SELECT id FROM users WHERE username = ?)",
                (username.strip().lower(),),
            )
        connection.commit()
    finally:
        connection.close()


def login(username: str, password: str, folder: str = None) -> str:
    name = username.strip().lower()
    connection = connect(folder)
    try:
        row = connection.execute(
            "SELECT id, password_hash, salt, active FROM users WHERE username = ?",
            (name,),
        ).fetchone()
        if row is None or not row["active"]:
            raise ValueError("Sai tên tài khoản hoặc mật khẩu.")
        expected = row["password_hash"]
        actual = _hash_password(password, row["salt"])
        if len(actual) != len(expected) or not hmac.compare_digest(actual, expected):
            raise ValueError("Sai tên tài khoản hoặc mật khẩu.")
        token = secrets.token_urlsafe(32)
        expires = int(time.time()) + TOKEN_DAYS * 24 * 3600
        connection.execute(
            "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
            (token, row["id"], expires),
        )
        connection.commit()
        return token
    finally:
        connection.close()


def user_for_token(token: str, folder: str = None):
    if not token:
        return None
    connection = connect(folder)
    try:
        row = connection.execute(
            """SELECT users.id, users.username FROM sessions
               JOIN users ON users.id = sessions.user_id
               WHERE sessions.token = ? AND sessions.expires_at > ? AND users.active = 1""",
            (token, int(time.time())),
        ).fetchone()
        return dict(row) if row else None
    finally:
        connection.close()
