"""Shared helpers for offbox regression tests. Not a test module."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OFFBOX = ROOT / "deploy" / "hetzner" / "offbox"

EXPECTED_MODULES = (
    "age_encrypt.py",
    "attempt_store.py",
    "backup_worker.py",
    "credential.py",
    "drive_upload.py",
    "framing.py",
    "https_transport.py",
    "logutil.py",
    "monitoring.py",
    "oauth_exchange.py",
    "peer_auth.py",
    "provenance.py",
    "restore_check.py",
    "snapshot_copy.py",
    "snapshot_helper.py",
)

EXPECTED_META = ("SHA256SUMS", "SOURCE_AUTHORITY.md")
EXPECTED_ALLOWLIST = EXPECTED_MODULES + EXPECTED_META

# Accepted D5A2D0-P1 / import commit 98b590e inventory (pinned; do not derive at runtime).
ACCEPTED_D5A2D0_P1_SHA256: dict[str, str] = {
    "age_encrypt.py": "91b6d8c1adb58ade6695634d00bcbd5f5063bb07a8ab878ef831bceb1292ccff",
    "attempt_store.py": "d00f2cca51142cb91b2accff504d0674373d42372cad45d6e1f5a852f7deaef6",
    "backup_worker.py": "79455d0ac99a2d77c478f3e6d5ad38a3243cb66bc7763165424d46c8c5395d14",
    "credential.py": "87cecf4fa928d93ff93e7cf4b090df48cd8a8a83a3ddf2a67e3846aee683ee0f",
    "drive_upload.py": "3895c9ca2bfbe3d0e89b5b89f6926c0b420bed8da8c5f204af52802178ae0a08",
    "framing.py": "afae4d2a666723bcfa29d22824c3ed33bfeabda3902483676e787d67bfbae19d",
    "https_transport.py": "c03268768c39bc2ec2f246d9b22b07098fdbc017801837e8815ce31879be0660",
    "logutil.py": "6afc6548f01798e2bd8858a4c490af1616877b82a1bfe2f31f3c3213fa1e6aa8",
    "monitoring.py": "8b55d9f0824938e213ec767708dd237249248854013fea233e8d074d4bf12456",
    "oauth_exchange.py": "c2b11ce1e0729dd0f9c66752c89c5ce049c806e95693080ff79d8c813224a752",
    "peer_auth.py": "bfa236afa5169310c25fff5e26c06b0d99efd878d6905b45c42ff7facadd777f",
    "provenance.py": "26e77e915ad1acb769752047e6976b1e40180dc29fa5956c96eaec589d5b3baa",
    "restore_check.py": "d767326183d176a9b004893653d68cb3699993faf43e7edf3e0b64b79d8ea76f",
    "snapshot_copy.py": "6aeb40810068fdee23b7580bdb060375c0521d28172f84116830dafda4df8973",
    "snapshot_helper.py": "7eb388a6a322d3e03e63d8b66b978b012611efa86f0a713b5ba6595a040f7098",
}

IGNORED_OFFBOX_DIR_NAMES = frozenset({"__pycache__"})


def ensure_offbox_on_path() -> Path:
    path = str(OFFBOX)
    if path not in sys.path:
        sys.path.insert(0, path)
    return OFFBOX


class MemSock:
    """In-memory socket stand-in for deterministic recv/send faults."""

    def __init__(self, inbound: bytes = b"") -> None:
        self._in = bytearray(inbound)
        self._out = bytearray()
        self.closed = False
        self.fail_after: int | None = None
        self._sent = 0

    def recv(self, n: int) -> bytes:
        if not self._in:
            return b""
        out = bytes(self._in[:n])
        del self._in[:n]
        return out

    def send(self, data: bytes) -> int:
        if self.fail_after is not None and self._sent >= self.fail_after:
            raise OSError("injected-send-failure")
        chunk = bytes(data)
        if self.fail_after is not None:
            remain = self.fail_after - self._sent
            if remain <= 0:
                raise OSError("injected-send-failure")
            if len(chunk) > remain:
                self._out.extend(chunk[:remain])
                self._sent += remain
                raise OSError("injected-send-failure")
        self._out.extend(chunk)
        self._sent += len(chunk)
        return len(chunk)

    def getsockopt(self, *a, **k):
        return 0

    def close(self) -> None:
        self.closed = True


def latest_state(attempt_dir: Path) -> tuple[str, str]:
    files = sorted(attempt_dir.glob("*.json"))
    if not files:
        return "", ""
    data = json.loads(files[-1].read_text(encoding="utf-8"))
    return str(data.get("state", "")), str(data.get("detail", ""))


def exclusive_write(path: Path, text: str) -> None:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    fd = os.open(str(path), flags, 0o600)
    try:
        os.write(fd, text.encode("utf-8"))
    finally:
        os.close(fd)
