"""Length-and-hash frame used on the connected snapshot socket.

The helper writes this to the socket it was given. It does not listen.
A short read is an incomplete transfer, not a snapshot.
"""

from __future__ import annotations

import hashlib
import struct

MAGIC = b"LGS1"
REFUSED = b"REFUSED"
FAILED = b"FAILED"
MAX_SNAPSHOT_BYTES = 64 * 1024 * 1024


def encode_frame(payload: bytes) -> bytes:
    digest = hashlib.sha256(payload).digest()
    return MAGIC + struct.pack(">I", len(payload)) + payload + digest


def send_all(sock, blob: bytes) -> None:
    view = memoryview(blob)
    sent = 0
    while sent < len(view):
        count = sock.send(view[sent:])
        if count <= 0:
            raise OSError("short-write")
        sent += count


class _Reader:
    def __init__(self, sock) -> None:
        self.sock = sock
        self.buf = bytearray()

    def exact(self, count: int):
        while len(self.buf) < count:
            chunk = self.sock.recv(min(65536, count - len(self.buf)))
            if not chunk:
                return None
            self.buf.extend(chunk)
        out = bytes(self.buf[:count])
        del self.buf[:count]
        return out


def receive(sock, max_bytes: int = MAX_SNAPSHOT_BYTES):
    """Return (status, payload). Payload is empty unless status is verified."""
    reader = _Reader(sock)
    prefix = reader.exact(4)
    if prefix is None:
        return "truncated", b""
    if prefix == REFUSED[:4]:
        rest = reader.exact(len(REFUSED) - 4)
        if rest != REFUSED[4:]:
            return "truncated", b""
        return "refused", b""
    if prefix == FAILED[:4]:
        rest = reader.exact(len(FAILED) - 4)
        if rest != FAILED[4:]:
            return "truncated", b""
        return "helper-failed", b""
    if prefix != MAGIC:
        return "magic", b""
    size_raw = reader.exact(4)
    if size_raw is None:
        return "truncated", b""
    (size,) = struct.unpack(">I", size_raw)
    if size > max_bytes:
        return "too-large", b""
    body = reader.exact(size)
    trailer = reader.exact(32)
    if body is None or trailer is None:
        return "truncated", b""
    if hashlib.sha256(body).digest() != trailer:
        return "hash", b""
    return "verified", body
