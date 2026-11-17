"""Fail-closed peer check for the connected helper socket.

The expected uid, gid, and unit come from the helper process configuration.
They are not read from the connected socket. SO_PEERCRED supplies pid, uid,
and gid. It does not name a systemd unit. uid 0 and gid 0 are refused.
A matching uid is not enough. The cgroup leaf must be the configured unit,
and only after pidfd_open has pinned that pid.

pidfd_open does not close the race before it is called. A peer that exits
and whose pid is reused in that interval is not identified by this check.
If the pin or the cgroup read fails, the peer is refused.
"""

from __future__ import annotations

import os
import socket
import struct


def cgroup_matches(cgroup_text: str, expected_unit: str) -> bool:
    if not expected_unit:
        return False
    for line in cgroup_text.splitlines():
        path = line.strip().split(":")[-1].rstrip("/")
        if path and path.split("/")[-1] == expected_unit:
            return True
    return False


def decide(
    uid,
    gid,
    expected_uid,
    expected_gid,
    cgroup_text,
    cgroup_errno,
    pidfd_ok,
    expected_unit,
) -> str:
    if uid is None or uid == 0 or uid != expected_uid:
        return "refused-uid"
    if gid is None or gid <= 0 or gid != expected_gid:
        return "refused-gid"
    if not pidfd_ok:
        return "refused-pidfd"
    if cgroup_errno is not None or cgroup_text is None:
        return "refused-unit-unreadable"
    if not cgroup_matches(cgroup_text, expected_unit):
        return "refused-not-unit"
    return "accepted"


def self_cgroup_leaf() -> str:
    try:
        text = open("/proc/self/cgroup", encoding="utf-8", errors="replace").read()
    except OSError:
        return ""
    for line in text.splitlines():
        path = line.strip().split(":")[-1].rstrip("/")
        if path:
            return path.split("/")[-1]
    return ""


def _read_cgroup(pid: int):
    try:
        text = open("/proc/%d/cgroup" % pid, encoding="utf-8", errors="replace").read()
    except OSError as exc:
        return None, exc.errno
    return text, None


def authorize_socket(sock, expected_uid: int, expected_gid: int, expected_unit: str) -> str:
    """Authorize the connected peer. Socket payload is not an identity input."""
    if not hasattr(socket, "SO_PEERCRED"):
        return "refused-peercred"
    try:
        raw = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
        _pid, uid, gid = struct.unpack("3i", raw)
    except (AttributeError, OSError):
        return "refused-peercred"
    if uid == 0 or uid != expected_uid:
        return "refused-uid"
    if gid <= 0 or gid != expected_gid:
        return "refused-gid"
    opener = getattr(os, "pidfd_open", None)
    if opener is None or _pid <= 0:
        return "refused-pidfd"
    try:
        pidfd = opener(_pid)
    except OSError:
        return "refused-pidfd"
    try:
        cgroup_text, cgroup_errno = _read_cgroup(_pid)
    finally:
        os.close(pidfd)
    return decide(uid, gid, expected_uid, expected_gid, cgroup_text, cgroup_errno, True, expected_unit)
