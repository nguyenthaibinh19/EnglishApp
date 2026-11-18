"""HTTPS transport for the accepted Drive adapter.

The Google endpoints are fixed. Certificate verification stays on.
A loopback dial exists only for a localhost test and never accepts an
arbitrary host. Redirects are not followed. 308 remains a resumable status.
"""

from __future__ import annotations

import http.client
import socket
import ssl
import urllib.parse

import drive_upload

CONNECT_TIMEOUT = 20
READ_TIMEOUT = 60
MAX_RESPONSE_BYTES = 68 * 1024 * 1024
_HOSTS = {"www.googleapis.com", "oauth2.googleapis.com"}
_REDIRECTS = {301, 302, 303, 307}


class TransportError(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class HttpsTransport:
    scheme = "https"

    def __init__(self, *, loopback=None, connect_timeout: int = CONNECT_TIMEOUT, read_timeout: int = READ_TIMEOUT) -> None:
        self.loopback = _loopback(loopback)
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.ssl_context = ssl.create_default_context()

    def send(self, request: drive_upload.HttpRequest) -> drive_upload.HttpResponse:
        parsed = urllib.parse.urlsplit(request.url)
        detail = endpoint_problem(parsed)
        if detail:
            raise TransportError(detail)
        if any(key.lower() == "authorization" for key in request.headers) and parsed.hostname == "oauth2.googleapis.com":
            raise TransportError("authorization-on-token")
        try:
            connection = self._open(parsed.hostname)
            connection.timeout = self.connect_timeout
            connection.connect()
        except TransportError:
            raise
        except Exception:
            raise TransportError("connect-failed")
        try:
            if connection.sock is not None:
                connection.sock.settimeout(self.read_timeout)
            selector = parsed.path + (("?" + parsed.query) if parsed.query else "")
            connection.request(request.method, selector, body=request.body, headers=dict(request.headers))
            response = connection.getresponse()
            status = response.status
            headers = {key: value for key, value in response.getheaders()}
            if status in _REDIRECTS:
                response.read(1024)
                connection.close()
                raise TransportError("unsafe-redirect")
            length = response.getheader("Content-Length")
            if length is not None and int(length) > MAX_RESPONSE_BYTES:
                connection.close()
                raise TransportError("response-too-large")
            body = response.read(MAX_RESPONSE_BYTES + 1)
            connection.close()
        except TransportError:
            raise
        except (TimeoutError, socket.timeout):
            raise drive_upload.AmbiguousTransportError("timeout")
        except (ConnectionError, http.client.RemoteDisconnected, http.client.IncompleteRead, ssl.SSLError):
            raise drive_upload.AmbiguousTransportError("lost-final")
        except Exception:
            raise drive_upload.AmbiguousTransportError("ambiguous")
        if len(body) > MAX_RESPONSE_BYTES:
            raise TransportError("response-too-large")
        return drive_upload.HttpResponse(status, headers, body)

    def _open(self, hostname: str):
        if self.loopback is not None:
            host, port = self.loopback
            connection = http.client.HTTPConnection(host, port, timeout=self.connect_timeout)
        else:
            connection = http.client.HTTPSConnection(hostname, timeout=self.connect_timeout, context=self.ssl_context)
        connection.timeout = self.read_timeout
        return connection


def endpoint_problem(parsed) -> str:
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.fragment:
        return "https-required"
    host = parsed.hostname or ""
    if host not in _HOSTS or parsed.port not in (None, 443):
        return "host-rejected"
    path = urllib.parse.unquote(parsed.path)
    if path == "/token":
        return "" if host == "oauth2.googleapis.com" else "path-rejected"
    if host != "www.googleapis.com":
        return "path-rejected"
    if path != "/drive/v3/files/generateIds" and path != "/upload/drive/v3/files":
        prefix = "/drive/v3/files/"
        if not path.startswith(prefix):
            return "path-rejected"
        file_id = path[len(prefix):]
        if "/" in file_id or not drive_upload._file_id(file_id):
            return "path-rejected"
    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    if path == "/upload/drive/v3/files":
        upload_type = query.get("uploadType", [])
        if upload_type == ["resumable"] and not _upload_id(query.get("upload_id", [])):
            if "upload_id" in query:
                return "session-rejected"
        if upload_type not in ([], ["multipart"], ["resumable"]):
            return "path-rejected"
    return ""


def _upload_id(values) -> bool:
    if len(values) != 1:
        return False
    value = values[0]
    return 1 <= len(value) <= 128 and all(char.isalnum() or char in "_-" for char in value)


def _loopback(value):
    if value is None:
        return None
    if not isinstance(value, tuple) or len(value) != 2:
        raise TransportError("loopback-rejected")
    host, port = value
    if host != "127.0.0.1" or not isinstance(port, int) or not 1 <= port <= 65535:
        raise TransportError("loopback-rejected")
    return value
