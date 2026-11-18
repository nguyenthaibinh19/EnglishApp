#!/usr/bin/env python3
"""Reproduce and stage frozen offbox modules + unit templates.

Offline only. Never enables systemd units, never starts services, never
touches Google Drive/OAuth, and never modifies production hosts.

Usage examples (from repository root):

  python deploy/hetzner/install_offbox_packaging.py verify
  python deploy/hetzner/install_offbox_packaging.py stage --dest /tmp/offbox-stage

Exit codes:
  0 success
  1 verification or staging failure (fail-closed)
  2 bad usage
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OFFBOX_SRC = HERE / "offbox"
UNIT_NAMES = (
    "language-guard-offbox-handoff.socket",
    "language-guard-offbox-handoff@.service",
    "language-guard-offbox-worker.service",
    "language-guard-offbox.timer",
)
FORBIDDEN_UNIT_MARKERS = (
    "StateDirectory=language-guard-backup",
    "/mnt/d/Tools/",
    "LG_DRIVE_FOLDER=",
    "LG_UPLOAD_ENABLED=",
)
REQUIRED_HELPER_MARKERS = (
    "StandardError=journal",
    "StandardOutput=socket",
    "User=guard",
    "LG_EXPECTED_UNIT=language-guard-offbox-worker.service",
)
REQUIRED_WORKER_MARKERS = (
    "User=lg-backup",
    "LoadCredential=oauth-refresh:",
    "LG_SOCKET=/run/language-guard-offbox/handoff.sock",
)
REQUIRED_SOCKET_MARKERS = (
    "ListenStream=/run/language-guard-offbox/handoff.sock",
    "SocketUser=lg-backup",
    "SocketMode=0600",
    "Accept=yes",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_sums(path: Path) -> dict[str, str]:
    listed: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 2:
            raise ValueError(f"malformed SHA256SUMS line: {line!r}")
        digest, name = parts
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError(f"bad digest for {name}")
        if name in listed:
            raise ValueError(f"duplicate SHA256SUMS entry: {name}")
        listed[name] = digest
    return listed


def verify_modules(offbox: Path = OFFBOX_SRC) -> dict[str, str]:
    sums_path = offbox / "SHA256SUMS"
    if not sums_path.is_file():
        raise FileNotFoundError(f"missing {sums_path}")
    listed = _parse_sums(sums_path)
    if not listed:
        raise ValueError("SHA256SUMS is empty")
    for name, expected in listed.items():
        path = offbox / name
        if not path.is_file() or path.is_symlink():
            raise FileNotFoundError(f"missing module: {name}")
        got = _sha256(path)
        if got != expected:
            raise ValueError(f"hash mismatch for {name}: {got} != {expected}")
    # Reject unexpected Python modules in the frozen tree.
    py_files = sorted(p.name for p in offbox.iterdir() if p.is_file() and p.suffix == ".py")
    expected_py = sorted(listed)
    if py_files != expected_py:
        raise ValueError(f"unexpected python inventory: {py_files} != {expected_py}")
    return listed


def verify_units(unit_dir: Path = HERE) -> None:
    for name in UNIT_NAMES:
        path = unit_dir / name
        if not path.is_file():
            raise FileNotFoundError(f"missing unit template: {name}")
        text = path.read_text(encoding="utf-8")
        for marker in FORBIDDEN_UNIT_MARKERS:
            if marker in text:
                raise ValueError(f"{name} contains forbidden marker: {marker}")
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            lowered = line.lower()
            if "systemctl enable" in lowered or "systemctl start" in lowered:
                raise ValueError(f"{name} must not embed enable/start actions")
    helper = (unit_dir / "language-guard-offbox-handoff@.service").read_text(encoding="utf-8")
    for marker in REQUIRED_HELPER_MARKERS:
        if marker not in helper:
            raise ValueError(f"helper unit missing required marker: {marker}")
    worker = (unit_dir / "language-guard-offbox-worker.service").read_text(encoding="utf-8")
    for marker in REQUIRED_WORKER_MARKERS:
        if marker not in worker:
            raise ValueError(f"worker unit missing required marker: {marker}")
    for raw_line in worker.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("StateDirectory="):
            raise ValueError("worker unit must not set StateDirectory=")
    sock = (unit_dir / "language-guard-offbox-handoff.socket").read_text(encoding="utf-8")
    for marker in REQUIRED_SOCKET_MARKERS:
        if marker not in sock:
            raise ValueError(f"socket unit missing required marker: {marker}")
    timer = (unit_dir / "language-guard-offbox.timer").read_text(encoding="utf-8")
    if "Unit=language-guard-offbox-worker.service" not in timer:
        raise ValueError("timer must target language-guard-offbox-worker.service")


def _exclusive_copy(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        if dest.is_symlink() or not dest.is_file():
            raise OSError(f"refusing to overwrite non-file destination: {dest}")
        if _sha256(dest) == _sha256(src):
            return  # idempotent no-op
        raise OSError(f"destination exists with different content: {dest}")
    tmp = dest.with_name(dest.name + ".tmp")
    if tmp.exists():
        tmp.unlink()
    shutil.copyfile(src, tmp)
    os.replace(tmp, dest)


def stage(dest: Path, *, include_units: bool = True) -> list[str]:
    listed = verify_modules()
    verify_units()
    written: list[str] = []
    modules_dest = dest / "offbox"
    for name in listed:
        src = OFFBOX_SRC / name
        target = modules_dest / name
        _exclusive_copy(src, target)
        if _sha256(target) != listed[name]:
            raise ValueError(f"staged hash mismatch: {name}")
        written.append(str(target.relative_to(dest)))
    # Carry authority files for operators.
    for meta in ("SHA256SUMS", "SOURCE_AUTHORITY.md"):
        _exclusive_copy(OFFBOX_SRC / meta, modules_dest / meta)
        written.append(f"offbox/{meta}")
    if include_units:
        units_dest = dest / "units"
        for name in UNIT_NAMES:
            _exclusive_copy(HERE / name, units_dest / name)
            written.append(f"units/{name}")
    return written


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("verify", help="Verify frozen module hashes and unit safety markers")
    stage_p = sub.add_parser("stage", help="Stage modules/units into a destination tree")
    stage_p.add_argument("--dest", required=True, type=Path, help="Destination directory")
    stage_p.add_argument(
        "--modules-only",
        action="store_true",
        help="Stage frozen modules only (skip unit templates)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "verify":
            listed = verify_modules()
            verify_units()
            print(f"VERIFY_OK modules={len(listed)} units={len(UNIT_NAMES)}")
            return 0
        if args.command == "stage":
            dest = args.dest.resolve()
            written = stage(dest, include_units=not args.modules_only)
            print(f"STAGE_OK dest={dest} files={len(written)}")
            for path in written:
                print(path)
            return 0
    except (OSError, ValueError, FileNotFoundError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
