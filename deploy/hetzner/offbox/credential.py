"""OAuth credential handoff for the backup worker.

The refresh token is read from a systemd LoadCredential directory. A caller
supplies the token exchange. This module does not open a network connection,
and it does not log the refresh token or the access token.
"""

from __future__ import annotations

import os
import sys
from typing import Protocol

sys.dont_write_bytecode = True

REFRESH_NAME = "oauth-refresh"


class TokenError(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class TokenExchanger(Protocol):
    def exchange(self, refresh_token: str) -> str:
        """Return a short-lived access token or raise TokenError."""


def read_refresh(directory: str) -> str:
    if not directory or os.path.islink(directory):
        raise TokenError("credential-absent")
    path = os.path.join(directory, REFRESH_NAME)
    if os.path.islink(path):
        raise TokenError("credential-absent")
    try:
        handle = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0))
    except OSError:
        raise TokenError("credential-absent")
    try:
        data = os.read(handle, 4096)
        extra = os.read(handle, 1)
    finally:
        os.close(handle)
    if extra or not data or len(data) > 4096:
        raise TokenError("credential-rejected")
    try:
        text = data.decode("ascii")
    except UnicodeError:
        raise TokenError("credential-rejected")
    if text != text.strip() or any(char.isspace() for char in text):
        raise TokenError("credential-rejected")
    return text


def access_token(directory: str, exchanger: TokenExchanger) -> str:
    refresh = read_refresh(directory)
    try:
        token = exchanger.exchange(refresh)
    except TokenError:
        raise
    except Exception:
        raise TokenError("token-exchange-failed")
    if not isinstance(token, str) or not token or any(char.isspace() for char in token):
        raise TokenError("token-rejected")
    if token == refresh or "AGE-SECRET" in token:
        raise TokenError("token-rejected")
    return token
