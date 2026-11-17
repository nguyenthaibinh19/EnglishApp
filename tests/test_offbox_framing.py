"""Test group B — framing behavior (synthetic in-memory only)."""

from __future__ import annotations

import hashlib
import struct

import pytest

from offbox_support import MemSock, ensure_offbox_on_path

ensure_offbox_on_path()
import framing  # noqa: E402


def test_valid_frame_verified() -> None:
    payload = b"synthetic-snapshot-bytes"
    status, body = framing.receive(MemSock(framing.encode_frame(payload)))
    assert status == "verified"
    assert body == payload


def test_incomplete_magic_only_truncated() -> None:
    status, body = framing.receive(MemSock(b"LGS1"))
    assert status == "truncated"
    assert body == b""


def test_partial_body_truncated() -> None:
    frame = framing.encode_frame(b"x" * 100)
    status, body = framing.receive(MemSock(frame[: 4 + 4 + 50]))
    assert status == "truncated"
    assert body == b""


def test_missing_trailer_truncated() -> None:
    payload = b"y" * 32
    # magic + size + body, no digest trailer
    blob = framing.MAGIC + struct.pack(">I", len(payload)) + payload
    status, body = framing.receive(MemSock(blob))
    assert status == "truncated"
    assert body == b""


def test_invalid_digest_hash_failure() -> None:
    payload = b"z" * 16
    frame = bytearray(framing.encode_frame(payload))
    frame[-1] ^= 0xFF
    status, body = framing.receive(MemSock(bytes(frame)))
    assert status == "hash"
    assert body == b""


def test_oversized_declared_frame_rejected() -> None:
    too_big = framing.MAX_SNAPSHOT_BYTES + 1
    blob = framing.MAGIC + struct.pack(">I", too_big)
    status, body = framing.receive(MemSock(blob))
    assert status == "too-large"
    assert body == b""


def test_injected_send_failure_raises_oserror() -> None:
    sock = MemSock()
    sock.fail_after = 0
    with pytest.raises(OSError):
        framing.send_all(sock, framing.encode_frame(b"abc"))


def test_encode_frame_digest_matches_payload() -> None:
    payload = b"digest-check"
    frame = framing.encode_frame(payload)
    assert frame.startswith(framing.MAGIC)
    size = struct.unpack(">I", frame[4:8])[0]
    assert size == len(payload)
    assert frame[8 : 8 + size] == payload
    assert frame[8 + size :] == hashlib.sha256(payload).digest()
