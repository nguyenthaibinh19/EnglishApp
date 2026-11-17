"""Refresh-token exchange through the restricted transport.

The request body is not logged. invalid_grant does not echo the token.
"""

from __future__ import annotations

import json
import urllib.parse

import credential
import drive_upload

TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = drive_upload.DRIVE_FILE_SCOPE


class GoogleRefreshExchanger:
    def __init__(self, transport, client_id: str, client_secret: str = "") -> None:
        self.transport = transport
        self.client_id = client_id
        self.client_secret = client_secret

    def exchange(self, refresh_token: str) -> str:
        if not self.client_id or any(char.isspace() for char in self.client_id):
            raise credential.TokenError("client-rejected")
        fields = {
            "client_id": self.client_id,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "scope": SCOPE,
        }
        if self.client_secret:
            fields["client_secret"] = self.client_secret
        body = urllib.parse.urlencode(fields).encode("ascii")
        request = drive_upload.HttpRequest(
            "POST",
            TOKEN_URL,
            {"Content-Length": str(len(body)), "Content-Type": "application/x-www-form-urlencoded"},
            body,
        )
        try:
            response = self.transport.send(request)
        except credential.TokenError:
            raise
        except Exception:
            raise credential.TokenError("token-exchange-failed")
        if response.status_code == 400 and b"invalid_grant" in response.body and refresh_token.encode("ascii") not in response.body:
            raise credential.TokenError("invalid-grant")
        if response.status_code != 200:
            raise credential.TokenError("token-rejected")
        try:
            parsed = json.loads(response.body.decode("utf-8"))
            token = parsed["access_token"]
        except (UnicodeError, json.JSONDecodeError, KeyError, TypeError):
            raise credential.TokenError("token-rejected")
        if not isinstance(token, str) or not token or any(char.isspace() for char in token) or token == refresh_token:
            raise credential.TokenError("token-rejected")
        return token
