#!/usr/bin/env python3
"""Reproduce and stage frozen offbox modules + unit templates.

Offline only. Never enables systemd units, never starts services, never
touches Google Drive/OAuth, and never modifies production hosts.

Module bytes are verified against the independently accepted D5A2D0-P1
inventory embedded below. A local SHA256SUMS file must match that inventory;
rewriting the manifest alone cannot authorize tampered module bytes.

Staging (`stage` / `install-app-tree`) assumes a trusted dedicated
destination directory. Do not run as root into a shared or untrusted path.

Usage examples (from repository root):

  python deploy/hetzner/install_offbox_packaging.py verify
  python deploy/hetzner/install_offbox_packaging.py stage --dest /tmp/offbox-stage
  python deploy/hetzner/install_offbox_packaging.py install-app-tree --dest /opt/language-guard

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

# Independently accepted D5A2D0-P1 / import commit 98b590e inventory.
# Do not derive this map from a mutable working-tree SHA256SUMS file.
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

UNIT_NAMES = (
    "language-guard-offbox-handoff.socket",
    "language-guard-offbox-handoff@.service",
    "language-guard-offbox-worker.service",
    "language-guard-offbox.timer",
)
APP_TREE_HELPERS = (
    "install_offbox_packaging.py",
    "offbox_report_lines.py",
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
    """Fail-closed check against the pinned D5A2D0-P1 inventory."""
    sums_path = offbox / "SHA256SUMS"
    if not sums_path.is_file():
        raise FileNotFoundError(f"missing {sums_path}")
    listed = _parse_sums(sums_path)
    if listed != ACCEPTED_D5A2D0_P1_SHA256:
        raise ValueError(
            "SHA256SUMS does not match accepted D5A2D0-P1 inventory "
            "(local manifest alone cannot authorize packaging)"
        )
    for name, expected in ACCEPTED_D5A2D0_P1_SHA256.items():
        path = offbox / name
        if not path.is_file() or path.is_symlink():
            raise FileNotFoundError(f"missing module: {name}")
        got = _sha256(path)
        if got != expected:
            raise ValueError(f"hash mismatch for {name}: {got} != {expected}")
    py_files = sorted(p.name for p in offbox.iterdir() if p.is_file() and p.suffix == ".py")
    expected_py = sorted(ACCEPTED_D5A2D0_P1_SHA256)
    if py_files != expected_py:
        raise ValueError(f"unexpected python inventory: {py_files} != {expected_py}")
    return dict(ACCEPTED_D5A2D0_P1_SHA256)


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


def stage(
    dest: Path,
    *,
    include_units: bool = True,
    hetzner_dir: Path = HERE,
) -> list[str]:
    offbox = hetzner_dir / "offbox"
    listed = verify_modules(offbox)
    verify_units(hetzner_dir)
    written: list[str] = []
    modules_dest = dest / "offbox"
    for name in listed:
        src = offbox / name
        target = modules_dest / name
        _exclusive_copy(src, target)
        if _sha256(target) != listed[name]:
            raise ValueError(f"staged hash mismatch: {name}")
        written.append(str(target.relative_to(dest)))
    for meta in ("SHA256SUMS", "SOURCE_AUTHORITY.md"):
        _exclusive_copy(offbox / meta, modules_dest / meta)
        written.append(f"offbox/{meta}")
    if include_units:
        units_dest = dest / "units"
        for name in UNIT_NAMES:
            _exclusive_copy(hetzner_dir / name, units_dest / name)
            written.append(f"units/{name}")
    return written


def install_app_tree(dest: Path, *, hetzner_dir: Path = HERE) -> list[str]:
    """Verify first, then install modules/helpers/units into an app tree.

    Layout:
      <dest>/offbox/*.py (+ SHA256SUMS, SOURCE_AUTHORITY.md)
      <dest>/deploy/hetzner/<helpers and unit templates>
    """
    offbox = hetzner_dir / "offbox"
    listed = verify_modules(offbox)
    verify_units(hetzner_dir)
    written: list[str] = []
    modules_dest = dest / "offbox"
    deploy_dest = dest / "deploy" / "hetzner"
    for name in listed:
        src = offbox / name
        target = modules_dest / name
        _exclusive_copy(src, target)
        if _sha256(target) != listed[name]:
            raise ValueError(f"installed hash mismatch: {name}")
        written.append(str(target.relative_to(dest)))
    for meta in ("SHA256SUMS", "SOURCE_AUTHORITY.md"):
        _exclusive_copy(offbox / meta, modules_dest / meta)
        written.append(f"offbox/{meta}")
    for helper in APP_TREE_HELPERS:
        _exclusive_copy(hetzner_dir / helper, deploy_dest / helper)
        written.append(f"deploy/hetzner/{helper}")
    for name in UNIT_NAMES:
        _exclusive_copy(hetzner_dir / name, deploy_dest / name)
        written.append(f"deploy/hetzner/{name}")
    return written


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("verify", help="Verify frozen module hashes and unit safety markers")
    stage_p = sub.add_parser("stage", help="Stage modules/units into a destination tree")
    stage_p.add_argument("--dest", required=True, type=Path, help="Trusted dedicated destination")
    stage_p.add_argument(
        "--modules-only",
        action="store_true",
        help="Stage frozen modules only (skip unit templates)",
    )
    install_p = sub.add_parser(
        "install-app-tree",
        help="Verify then install into <dest>/offbox and <dest>/deploy/hetzner",
    )
    install_p.add_argument("--dest", required=True, type=Path, help="Trusted app-tree destination")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "verify":
            listed = verify_modules()
            verify_units()
            print(f"VERIFY_OK modules={len(listed)} units={len(UNIT_NAMES)} inventory=D5A2D0-P1")
            return 0
        if args.command == "stage":
            dest = args.dest.resolve()
            written = stage(dest, include_units=not args.modules_only)
            print(f"STAGE_OK dest={dest} files={len(written)}")
            for path in written:
                print(path)
            return 0
        if args.command == "install-app-tree":
            dest = args.dest.resolve()
            written = install_app_tree(dest)
            print(f"INSTALL_OK dest={dest} files={len(written)} inventory=D5A2D0-P1")
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
