#!/usr/bin/env python3
"""Reproduce and stage frozen offbox modules + unit templates.

Offline only. Never enables systemd units, never starts services, never
touches Google Drive/OAuth, and never modifies production hosts.

Module bytes are verified against the independently accepted D5A2D0-P1
inventory embedded below. A local SHA256SUMS file must match that inventory;
rewriting the manifest alone cannot authorize tampered module bytes.

Trusted runtime destination (source design):
  /opt/language-guard-offbox/
    offbox/*.py (+ SHA256SUMS, SOURCE_AUTHORITY.md)
    deploy/hetzner/<helpers and unit templates>

``verify`` / ``verify-deps`` auto-detect modules either beside this
script (repo layout) or at ``<exec_root>/offbox`` when this script is
installed under ``<exec_root>/deploy/hetzner/``.

That tree must remain outside any guard-writable ancestor (not under
/opt/language-guard). Units must ExecStart /usr/bin/python3 -I against
modules in that tree — never the guard-owned app venv.

Production installs require ``install-execution-tree --production`` with
exact destination ``/opt/language-guard-offbox`` and destination ancestor
plus existing-descendant preflight before any copy. Offline staging/tests
omit ``--production``.

Usage examples (from repository root):

  python deploy/hetzner/install_offbox_packaging.py verify
  python deploy/hetzner/install_offbox_packaging.py verify-deps
  python deploy/hetzner/install_offbox_packaging.py stage --dest /tmp/offbox-stage
  python deploy/hetzner/install_offbox_packaging.py install-execution-tree \\
      --dest /opt/language-guard-offbox --production

Exit codes:
  0 success
  1 verification or staging failure (fail-closed)
  2 bad usage
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import os
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OFFBOX_SRC = HERE / "offbox"


def resolve_offbox_dir(hetzner_dir: Path = HERE) -> Path:
    """Locate frozen modules for repo layout or installed execution tree.

    Repo / offline staging keeps modules at ``<hetzner_dir>/offbox``.
    Production installs place modules at ``<exec_root>/offbox`` while this
    packager lives at ``<exec_root>/deploy/hetzner/``. Auto-detect both so
    ``verify`` / ``verify-deps`` work from the installed tree without moving
    frozen module bytes.
    """
    sibling = hetzner_dir / "offbox"
    if sibling.is_dir() and (sibling / "SHA256SUMS").is_file():
        return sibling
    if hetzner_dir.name == "hetzner" and hetzner_dir.parent.name == "deploy":
        candidate = hetzner_dir.parent.parent / "offbox"
        if candidate.is_dir() and (candidate / "SHA256SUMS").is_file():
            return candidate
    raise FileNotFoundError(
        "unable to locate offbox modules for "
        f"{hetzner_dir} (expected {sibling} or production <root>/offbox)"
    )

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

# Trusted execution layout (source design; VPS write still separately authorized).
OFFBOX_EXEC_ROOT = "/opt/language-guard-offbox"
OFFBOX_EXEC_MODULES = f"{OFFBOX_EXEC_ROOT}/offbox"
TRUSTED_INTERPRETER = "/usr/bin/python3"
TRUSTED_RESOLVED_INTERPRETER_RE = re.compile(r"^/usr/bin/python3(\.\d+)?$")
# Account DB remains under the app tree (data, not executable code).
APP_ACCOUNTS_DB = "/opt/language-guard/accounts.db"

HELPER_EXEC_START = f"{TRUSTED_INTERPRETER} -I {OFFBOX_EXEC_MODULES}/snapshot_helper.py"
WORKER_EXEC_START = f"{TRUSTED_INTERPRETER} -I {OFFBOX_EXEC_MODULES}/backup_worker.py"

FORBIDDEN_ACTIVE_SUBSTRINGS = (
    "StateDirectory=language-guard-backup",
    "/mnt/d/Tools/",
    "LG_DRIVE_FOLDER=",
    "LG_UPLOAD_ENABLED=",
    "/opt/language-guard/venv/",
    "/opt/language-guard/offbox/",
    "venv/bin/python",
)

# Exact active systemd contracts (section -> multiset of KEY=VALUE).
# Comments/blank lines are ignored by the parser; any active extra/changed
# security-sensitive directive (Environment, ProtectSystem, paths, …) fails.
HELPER_UNIT_CONTRACT: dict[str, list[tuple[str, str]]] = {
    "Unit": [
        ("Description", "Language Guard off-box snapshot helper"),
    ],
    "Service": [
        ("Type", "simple"),
        ("User", "guard"),
        ("Group", "guard"),
        ("UMask", "0077"),
        ("NoNewPrivileges", "yes"),
        ("PrivateNetwork", "yes"),
        ("PrivateTmp", "yes"),
        ("PrivateDevices", "yes"),
        ("ProtectSystem", "strict"),
        ("ProtectHome", "yes"),
        ("ProtectKernelTunables", "yes"),
        ("ProtectKernelModules", "yes"),
        ("ProtectControlGroups", "yes"),
        ("RestrictNamespaces", "yes"),
        ("LockPersonality", "yes"),
        ("RestrictRealtime", "yes"),
        ("RestrictSUIDSGID", "yes"),
        ("SystemCallArchitectures", "native"),
        ("CapabilityBoundingSet", ""),
        ("AmbientCapabilities", ""),
        ("RestrictAddressFamilies", "AF_UNIX"),
        ("WorkingDirectory", OFFBOX_EXEC_MODULES),
        ("Environment", "PYTHONDONTWRITEBYTECODE=1"),
        ("Environment", "PYTHONNOUSERSITE=1"),
        ("Environment", f"LG_SOURCE_DB={APP_ACCOUNTS_DB}"),
        ("Environment", "LG_AUDIT_DIR=/var/lib/language-guard-helper"),
        ("Environment", "LG_FORBIDDEN_PLAINTEXT_DIR=/var/lib/language-guard-backup"),
        ("Environment", "LG_EXPECTED_UID=994"),
        ("Environment", "LG_EXPECTED_GID=977"),
        ("Environment", "LG_EXPECTED_UNIT=language-guard-offbox-worker.service"),
        ("ReadOnlyPaths", f"{OFFBOX_EXEC_ROOT} {APP_ACCOUNTS_DB}"),
        ("ReadWritePaths", "/var/lib/language-guard-helper"),
        (
            "InaccessiblePaths",
            "-/etc/language-guard -/var/lib/language-guard-backup "
            "-/run/credentials -/opt/language-guard/venv",
        ),
        ("StandardInput", "socket"),
        ("StandardOutput", "socket"),
        ("StandardError", "journal"),
        ("ExecStart", HELPER_EXEC_START),
        ("TimeoutStartSec", "120"),
    ],
}
WORKER_UNIT_CONTRACT: dict[str, list[tuple[str, str]]] = {
    "Unit": [
        ("Description", "Language Guard off-box backup worker"),
        ("Requires", "language-guard-offbox-handoff.socket"),
        ("After", "language-guard-offbox-handoff.socket"),
    ],
    "Service": [
        ("Type", "oneshot"),
        ("User", "lg-backup"),
        ("Group", "lg-backup"),
        ("UMask", "0077"),
        ("NoNewPrivileges", "yes"),
        ("PrivateTmp", "yes"),
        ("PrivateDevices", "yes"),
        ("ProtectSystem", "strict"),
        ("ProtectHome", "yes"),
        ("ProtectKernelTunables", "yes"),
        ("ProtectKernelModules", "yes"),
        ("ProtectControlGroups", "yes"),
        ("RestrictNamespaces", "yes"),
        ("LockPersonality", "yes"),
        ("RestrictRealtime", "yes"),
        ("RestrictSUIDSGID", "yes"),
        ("SystemCallArchitectures", "native"),
        ("CapabilityBoundingSet", ""),
        ("AmbientCapabilities", ""),
        ("RestrictAddressFamilies", "AF_UNIX AF_INET AF_INET6"),
        ("WorkingDirectory", "/var/lib/language-guard-backup"),
        ("Environment", "PYTHONDONTWRITEBYTECODE=1"),
        ("Environment", "PYTHONNOUSERSITE=1"),
        ("Environment", "LG_STATE_DIR=/var/lib/language-guard-backup"),
        ("Environment", f"LG_SOURCE_DB={APP_ACCOUNTS_DB}"),
        ("Environment", "LG_SOCKET=/run/language-guard-offbox/handoff.sock"),
        ("Environment", "LG_RECIPIENT_FILE=/etc/language-guard/age-recipient"),
        ("Environment", "LG_AGE_BIN=/usr/local/lib/language-guard-age/age"),
        ("ReadOnlyPaths", OFFBOX_EXEC_ROOT),
        ("ReadWritePaths", "/var/lib/language-guard-backup"),
        (
            "InaccessiblePaths",
            f"-{APP_ACCOUNTS_DB} -/var/lib/language-guard-helper -/opt/language-guard/venv",
        ),
        ("LoadCredential", "oauth-refresh:/etc/language-guard/oauth-refresh"),
        ("ExecStart", WORKER_EXEC_START),
        ("TimeoutStartSec", "300"),
    ],
}
SOCKET_UNIT_CONTRACT: dict[str, list[tuple[str, str]]] = {
    "Unit": [
        ("Description", "Language Guard off-box handoff socket"),
    ],
    "Socket": [
        ("ListenStream", "/run/language-guard-offbox/handoff.sock"),
        ("SocketUser", "lg-backup"),
        ("SocketGroup", "lg-backup"),
        ("SocketMode", "0600"),
        ("DirectoryMode", "0755"),
        ("Accept", "yes"),
    ],
    "Install": [
        ("WantedBy", "sockets.target"),
    ],
}
TIMER_UNIT_CONTRACT: dict[str, list[tuple[str, str]]] = {
    "Unit": [
        (
            "Description",
            "Proposed Language Guard off-box backup schedule (DISABLED BY DEFAULT)",
        ),
    ],
    "Timer": [
        ("OnCalendar", "*-*-* 05:15:00 UTC"),
        ("Persistent", "true"),
        ("RandomizedDelaySec", "15m"),
        ("Unit", "language-guard-offbox-worker.service"),
    ],
    "Install": [
        ("WantedBy", "timers.target"),
    ],
}

# Expected modes for a future corrective VPS write (documented + tested offline).
EXPECTED_EXEC_DIR_MODE = 0o755
EXPECTED_EXEC_FILE_MODE = 0o644
EXPECTED_EXEC_OWNER = "root"
EXPECTED_EXEC_GROUP = "root"


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


def parse_unit_sections(text: str) -> dict[str, list[tuple[str, str]]]:
    """Parse systemd unit text into section -> active KEY=VALUE lists.

    Comments are ignored. Directives outside a section are rejected. Section
    headers themselves are not treated as satisfying required keys.
    """
    sections: dict[str, list[tuple[str, str]]] = {}
    current: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            name = line[1:-1].strip()
            if not name:
                raise ValueError(f"invalid empty section header: {line!r}")
            current = name
            sections.setdefault(current, [])
            continue
        if current is None:
            raise ValueError(f"directive outside any section: {line!r}")
        if "=" not in line:
            raise ValueError(f"invalid unit line (missing '='): {line!r}")
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            raise ValueError(f"invalid unit line (empty key): {line!r}")
        sections[current].append((key, value.strip()))
    return sections


def parse_active_unit_directives(text: str) -> list[tuple[str, str]]:
    """Flatten active directives across sections (legacy helper for tests)."""
    flat: list[tuple[str, str]] = []
    for directives in parse_unit_sections(text).values():
        flat.extend(directives)
    return flat


def _reject_forbidden_active(
    directives: list[tuple[str, str]],
    unit_name: str,
    *,
    section: str,
) -> None:
    """Defense-in-depth checks in addition to the exact section contract."""
    for key, value in directives:
        rendered = f"{key}={value}"
        lowered = rendered.lower()
        if "systemctl enable" in lowered or "systemctl start" in lowered:
            raise ValueError(f"{unit_name} must not embed enable/start actions")
        if key == "EnvironmentFile":
            raise ValueError(
                f"{unit_name}: [{section}] EnvironmentFile= is not authorized"
            )
        if key.startswith("Exec") and key != "ExecStart":
            raise ValueError(
                f"{unit_name}: [{section}] unexpected executable directive {key}="
            )
        if key == "ExecStart" and section != "Service":
            raise ValueError(
                f"{unit_name}: ExecStart= must appear under [Service], found [{section}]"
            )
        for marker in FORBIDDEN_ACTIVE_SUBSTRINGS:
            if marker in rendered or marker in value:
                raise ValueError(
                    f"{unit_name} [{section}] contains forbidden marker: {marker}"
                )


def _require_exact_section_contract(
    sections: dict[str, list[tuple[str, str]]],
    unit_name: str,
    contract: dict[str, list[tuple[str, str]]],
) -> None:
    """Require exact section set and exact active KEY=VALUE multiplicity."""
    expected_sections = frozenset(contract)
    actual_sections = frozenset(sections)
    if actual_sections != expected_sections:
        raise ValueError(
            f"{unit_name}: section set {sorted(actual_sections)} != "
            f"required {sorted(expected_sections)}"
        )
    for section, expected in contract.items():
        actual = sections.get(section, [])
        _reject_forbidden_active(actual, unit_name, section=section)
        if Counter(actual) != Counter(expected):
            raise ValueError(
                f"{unit_name}: [{section}] active directive contract mismatch "
                f"(expected {len(expected)} directives, got {len(actual)})"
            )


def verify_units(unit_dir: Path = HERE) -> None:
    """Validate exact active unit contracts (comments do not affect the check)."""
    for name in UNIT_NAMES:
        path = unit_dir / name
        if not path.is_file():
            raise FileNotFoundError(f"missing unit template: {name}")

    helper_name = "language-guard-offbox-handoff@.service"
    worker_name = "language-guard-offbox-worker.service"
    socket_name = "language-guard-offbox-handoff.socket"
    timer_name = "language-guard-offbox.timer"

    _require_exact_section_contract(
        parse_unit_sections((unit_dir / helper_name).read_text(encoding="utf-8")),
        helper_name,
        HELPER_UNIT_CONTRACT,
    )
    _require_exact_section_contract(
        parse_unit_sections((unit_dir / worker_name).read_text(encoding="utf-8")),
        worker_name,
        WORKER_UNIT_CONTRACT,
    )
    _require_exact_section_contract(
        parse_unit_sections((unit_dir / socket_name).read_text(encoding="utf-8")),
        socket_name,
        SOCKET_UNIT_CONTRACT,
    )
    _require_exact_section_contract(
        parse_unit_sections((unit_dir / timer_name).read_text(encoding="utf-8")),
        timer_name,
        TIMER_UNIT_CONTRACT,
    )


def _top_level_module(name: str) -> str:
    return name.split(".", 1)[0]


def _imported_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(_top_level_module(alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                names.add(f".{'.' * (node.level - 1)}{node.module or ''}")
                continue
            if node.module:
                names.add(_top_level_module(node.module))
    return names


def verify_dependency_closure(offbox: Path = OFFBOX_SRC) -> dict[str, set[str]]:
    """Offline import closure: stdlib + local offbox modules only."""
    verify_modules(offbox)
    local = {name[:-3] for name in ACCEPTED_D5A2D0_P1_SHA256}
    stdlib = set(getattr(sys, "stdlib_module_names", ()))
    if not stdlib:
        raise ValueError("sys.stdlib_module_names unavailable; need Python >= 3.10")
    per_file: dict[str, set[str]] = {}
    illegal: list[str] = []
    for name in sorted(ACCEPTED_D5A2D0_P1_SHA256):
        path = offbox / name
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported = _imported_names(tree)
        per_file[name] = imported
        for mod in sorted(imported):
            if mod.startswith("."):
                illegal.append(f"{name}: relative import {mod!r}")
                continue
            if mod in local or mod in stdlib:
                continue
            illegal.append(f"{name}: non-stdlib dependency {mod!r}")
    if illegal:
        raise ValueError("dependency closure failed: " + "; ".join(illegal))
    return per_file


class PathTrustMeta:
    """Metadata-only description of one path component for offline trust tests."""

    __slots__ = (
        "path",
        "owner",
        "group",
        "mode",
        "is_dir",
        "sticky",
        "writable_by",
        "is_symlink",
        "symlink_target",
        "acl_extra_write_principals",
    )

    def __init__(
        self,
        path: str,
        owner: str,
        group: str,
        mode: int,
        is_dir: bool,
        sticky: bool = False,
        writable_by: frozenset[str] | None = None,
        is_symlink: bool = False,
        symlink_target: str | None = None,
        acl_extra_write_principals: frozenset[str] | None = None,
    ) -> None:
        self.path = path
        self.owner = owner
        self.group = group
        self.mode = mode
        self.is_dir = is_dir
        self.sticky = sticky
        self.writable_by = writable_by
        self.is_symlink = is_symlink
        self.symlink_target = symlink_target
        self.acl_extra_write_principals = acl_extra_write_principals


def _posix_normalize(path: str) -> str:
    normalized = path.replace("\\", "/").rstrip("/")
    if not normalized.startswith("/"):
        normalized = "/" + normalized
    return normalized or "/"


def _posix_ancestor_dirs(path: str) -> list[str]:
    """Return POSIX ancestor directories of a file path, root-first."""
    normalized = _posix_normalize(path)
    segments = [seg for seg in normalized.split("/") if seg]
    out = ["/"]
    current = ""
    for seg in segments[:-1]:
        current += "/" + seg
        out.append(current)
    return out


def _writers_from_mode(
    meta: PathTrustMeta,
    *,
    less_trusted: str,
    less_trusted_groups: frozenset[str],
) -> set[str]:
    writers: set[str] = set()
    if meta.mode & 0o200 and meta.owner == less_trusted:
        writers.add(less_trusted)
    if meta.mode & 0o020:
        writers.add(f"group:{meta.group}")
        if meta.group == less_trusted or meta.group in less_trusted_groups:
            writers.add(less_trusted)
    if meta.mode & 0o002:
        writers.add("other")
        writers.add(less_trusted)
    return writers


def classify_execution_path_trust(
    *,
    path_meta: list[PathTrustMeta],
    interpreter_exec: str,
    module_paths: list[str],
    interpreter_resolved: str | None = None,
    less_trusted: str = "guard",
    less_trusted_groups: frozenset[str] | None = None,
) -> str:
    """Classify PASS/UNSAFE/UNKNOWN from metadata fixtures (no filesystem writes).

    PASS requires:
    - exact trusted interpreter identity and a resolved target under /usr/bin/python3[.N]
    - complete metadata for every ancestor and executable leaf
    - inspected ACL evidence (empty extra-write set is OK; missing ACL => UNKNOWN)
    - no less-trusted / group / other write on ancestors or executable leaves
    - no untrusted symlinks on the executable path
    """
    groups = less_trusted_groups if less_trusted_groups is not None else frozenset()
    if not path_meta or not module_paths:
        return "UNKNOWN"

    if interpreter_exec != TRUSTED_INTERPRETER:
        return "UNSAFE"
    if "/venv/" in interpreter_exec:
        return "UNSAFE"
    if interpreter_resolved is None:
        return "UNKNOWN"
    if not TRUSTED_RESOLVED_INTERPRETER_RE.fullmatch(interpreter_resolved):
        return "UNSAFE"

    by_path = {_posix_normalize(item.path): item for item in path_meta}
    required_paths: list[str] = []
    for module in module_paths:
        required_paths.extend(_posix_ancestor_dirs(module))
        required_paths.append(_posix_normalize(module))
    # Interpreter leaf + its parents when provided in path_meta; require at least
    # the interpreter path itself when present in fixtures for PASS completeness.
    required_paths.append(_posix_normalize(interpreter_exec))
    if interpreter_resolved != interpreter_exec:
        required_paths.append(_posix_normalize(interpreter_resolved))
        required_paths.extend(_posix_ancestor_dirs(interpreter_resolved))

    for path in required_paths:
        meta = by_path.get(path)
        if meta is None:
            return "UNKNOWN"
        if meta.acl_extra_write_principals is None:
            return "UNKNOWN"
        if meta.is_symlink:
            target = meta.symlink_target
            if not target:
                return "UNKNOWN"
            if target.startswith("/"):
                abs_target = _posix_normalize(target)
            else:
                parent = path.rsplit("/", 1)[0] or "/"
                abs_target = _posix_normalize(f"{parent}/{target}")
            # Allow only the system python3 -> python3.N indirection under /usr/bin.
            if path in {
                _posix_normalize(interpreter_exec),
                "/usr/bin/python3",
            }:
                if not (
                    TRUSTED_RESOLVED_INTERPRETER_RE.fullmatch(abs_target)
                    or TRUSTED_RESOLVED_INTERPRETER_RE.fullmatch(
                        _posix_normalize(interpreter_resolved)
                    )
                ):
                    return "UNSAFE"
            else:
                # Symlinked code/module ancestors are not accepted for PASS.
                return "UNSAFE"
            # Symlink inode modes are not authoritative on Linux; rely on target
            # and parent directory metadata instead.
            writers = set(meta.writable_by or ())
            writers |= set(meta.acl_extra_write_principals)
        else:
            writers = set(meta.writable_by or ())
            writers |= _writers_from_mode(
                meta, less_trusted=less_trusted, less_trusted_groups=groups
            )
            writers |= set(meta.acl_extra_write_principals)
            if meta.owner == less_trusted and (meta.mode & 0o200):
                return "UNSAFE"
            # Executable leaves must not be group/world writable.
            if not meta.is_dir and (meta.mode & 0o022):
                return "UNSAFE"
        if less_trusted in writers or "other" in writers:
            return "UNSAFE"
        if any(item.startswith("group:") and item[6:] in groups for item in writers):
            return "UNSAFE"
    return "PASS"


def expected_execution_tree_modes(dest: Path) -> list[tuple[str, int]]:
    """Document expected root-immutable modes after a corrective VPS write."""
    expected: list[tuple[str, int]] = [(str(dest), EXPECTED_EXEC_DIR_MODE)]
    expected.append((str(dest / "offbox"), EXPECTED_EXEC_DIR_MODE))
    for name in ACCEPTED_D5A2D0_P1_SHA256:
        expected.append((str(dest / "offbox" / name), EXPECTED_EXEC_FILE_MODE))
    return expected


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


def _posix_dest(dest: Path) -> str:
    return dest.as_posix().rstrip("/") or "/"


def _iter_existing_ancestors(path: Path) -> list[Path]:
    found: list[Path] = []
    current = path
    while True:
        if current.exists() or current.is_symlink():
            found.append(current)
        if current.parent == current:
            break
        current = current.parent
    return found


class PathProbe:
    """Filesystem probe result used by production destination preflight."""

    __slots__ = ("is_symlink", "is_dir", "is_file", "uid", "gid", "mode")

    def __init__(
        self,
        *,
        is_symlink: bool,
        is_dir: bool,
        is_file: bool,
        uid: int,
        gid: int,
        mode: int,
    ) -> None:
        self.is_symlink = is_symlink
        self.is_dir = is_dir
        self.is_file = is_file
        self.uid = uid
        self.gid = gid
        self.mode = mode


def _probe_path(path: Path) -> PathProbe | None:
    """Return metadata for an existing path, or None if absent.

    Tests may monkeypatch this helper to inject ownership/mode fixtures.
    """
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink():
        return PathProbe(
            is_symlink=True,
            is_dir=False,
            is_file=False,
            uid=-1,
            gid=-1,
            mode=0o777,
        )
    st = path.lstat()
    return PathProbe(
        is_symlink=False,
        is_dir=path.is_dir(),
        is_file=path.is_file(),
        uid=int(getattr(st, "st_uid", 0)),
        gid=int(getattr(st, "st_gid", 0)),
        mode=int(st.st_mode) & 0o777,
    )


def planned_execution_tree_paths(dest: Path) -> list[Path]:
    """All directories/files the installer may create or overwrite."""
    paths: list[Path] = [
        dest,
        dest / "offbox",
        dest / "deploy",
        dest / "deploy" / "hetzner",
    ]
    for name in ACCEPTED_D5A2D0_P1_SHA256:
        paths.append(dest / "offbox" / name)
    for meta in ("SHA256SUMS", "SOURCE_AUTHORITY.md"):
        paths.append(dest / "offbox" / meta)
    for helper in APP_TREE_HELPERS:
        paths.append(dest / "deploy" / "hetzner" / helper)
    for name in UNIT_NAMES:
        paths.append(dest / "deploy" / "hetzner" / name)
    return paths


def assert_trusted_existing_path(
    path: Path,
    probe: PathProbe,
    *,
    require_root_owner: bool,
    enforce_unix_modes: bool,
    expect_dir: bool | None = None,
) -> None:
    """Fail closed on symlink / ownership / mode drift for one existing path."""
    if probe.is_symlink:
        raise ValueError(f"symlink in destination target set: {path}")
    if expect_dir is True and not probe.is_dir:
        raise ValueError(f"expected directory at destination path: {path}")
    if expect_dir is False and not probe.is_file:
        raise ValueError(f"expected regular file at destination path: {path}")
    mode = probe.mode & 0o777
    if enforce_unix_modes and (mode & 0o022):
        raise ValueError(
            f"group/world-writable destination path: {path} mode={oct(mode)}"
        )
    if not require_root_owner:
        return
    if probe.uid != 0 or probe.gid != 0:
        raise ValueError(
            f"ownership drift on destination path {path}: "
            f"uid={probe.uid} gid={probe.gid} (require root:root)"
        )
    if probe.is_dir and mode != EXPECTED_EXEC_DIR_MODE:
        raise ValueError(
            f"directory mode drift: {path} mode={oct(mode)} "
            f"expected {oct(EXPECTED_EXEC_DIR_MODE)}"
        )
    if probe.is_file and mode != EXPECTED_EXEC_FILE_MODE:
        raise ValueError(
            f"file mode drift: {path} mode={oct(mode)} "
            f"expected {oct(EXPECTED_EXEC_FILE_MODE)}"
        )


def preflight_execution_tree_targets(
    dest: Path,
    *,
    require_root_owner: bool,
    enforce_unix_modes: bool | None = None,
) -> None:
    """Inspect existing planned descendants before any copy."""
    if enforce_unix_modes is None:
        enforce_unix_modes = bool(require_root_owner or os.name == "posix")
    for path in planned_execution_tree_paths(dest):
        probe = _probe_path(path)
        if probe is None:
            continue
        expect_dir: bool | None
        if path == dest or path.name in {"offbox", "deploy", "hetzner"}:
            expect_dir = True
        elif path.suffix or path.name in {"SHA256SUMS", "SOURCE_AUTHORITY.md"}:
            expect_dir = False
        else:
            expect_dir = None
        assert_trusted_existing_path(
            path,
            probe,
            require_root_owner=require_root_owner,
            enforce_unix_modes=enforce_unix_modes,
            expect_dir=expect_dir,
        )


def validate_install_destination(dest: Path, *, production: bool) -> None:
    """Fail closed on unsafe destinations before any file copy.

    production=True: destination must be exactly ``/opt/language-guard-offbox``,
    with symlink/ownership/mode preflight on existing ancestors **and** any
    existing planned descendant paths (modules/helpers/units). Correct-hash
    files with unsafe ownership/mode are rejected (no silent idempotent skip).

    production=False: offline/test staging — refuse the guard app-tree segment
    ``language-guard`` and refuse symlink destinations, but allow other roots.
    """
    posix = _posix_dest(dest)
    if production:
        if posix != OFFBOX_EXEC_ROOT:
            raise ValueError(
                f"production install destination must be exactly {OFFBOX_EXEC_ROOT}, "
                f"got {posix}"
            )
    else:
        # Offline/test destinations may use a directory *named*
        # language-guard-offbox, but never the app-tree segment language-guard.
        parts = Path(posix).parts
        if "language-guard" in parts:
            raise ValueError(
                "refusing to install execution tree under the guard-owned app path; "
                f"use {OFFBOX_EXEC_ROOT} with --production, or a non-app test root"
            )

    if dest.exists() and dest.is_symlink():
        raise ValueError(f"destination must not be a symlink: {dest}")

    for ancestor in _iter_existing_ancestors(dest):
        if ancestor.is_symlink():
            raise ValueError(f"symlink in destination ancestry: {ancestor}")
        if not production:
            continue
        # Production preflight on POSIX hosts when metadata is available.
        if os.name != "posix":
            continue
        probe = _probe_path(ancestor)
        if probe is None:
            continue
        mode = probe.mode & 0o777
        if mode & 0o022:
            raise ValueError(
                f"group/world-writable destination ancestor: {ancestor} "
                f"mode={oct(mode)}"
            )
        ancestor_posix = ancestor.as_posix().rstrip("/") or "/"
        if ancestor_posix in {"/opt", OFFBOX_EXEC_ROOT} or ancestor_posix.startswith(
            OFFBOX_EXEC_ROOT + "/"
        ):
            if probe.uid != 0 or probe.gid != 0:
                raise ValueError(
                    f"ownership drift on production ancestor {ancestor_posix}: "
                    f"uid={probe.uid} gid={probe.gid} (require root:root)"
                )

    # Existing destination subtree must already be immutable/trusted, or absent.
    # Symlinks in the planned target set are always rejected; unix mode/owner
    # drift is enforced for production and on POSIX hosts.
    preflight_execution_tree_targets(
        dest,
        require_root_owner=bool(production and os.name == "posix"),
        enforce_unix_modes=bool(production or os.name == "posix"),
    )


def stage(
    dest: Path,
    *,
    include_units: bool = True,
    hetzner_dir: Path = HERE,
) -> list[str]:
    """Offline staging into an arbitrary trusted test destination (non-production)."""
    validate_install_destination(dest, production=False)
    offbox = hetzner_dir / "offbox"
    listed = verify_modules(offbox)
    verify_units(hetzner_dir)
    verify_dependency_closure(offbox)
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


def install_execution_tree(
    dest: Path,
    *,
    hetzner_dir: Path = HERE,
    production: bool = False,
) -> list[str]:
    """Verify first, then install the dedicated immutable execution tree.

    Layout (production dest: /opt/language-guard-offbox):
      <dest>/offbox/*.py (+ SHA256SUMS, SOURCE_AUTHORITY.md)
      <dest>/deploy/hetzner/<helpers and unit templates>

    Destination preflight and unit/module verification run before any copy.
    Does not chown (may run offline on Windows). A future authorized VPS write
    must pass ``production=True`` and apply root:root 0755/0644.
    """
    validate_install_destination(dest, production=production)

    offbox = hetzner_dir / "offbox"
    listed = verify_modules(offbox)
    verify_units(hetzner_dir)
    verify_dependency_closure(offbox)
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


def install_app_tree(dest: Path, *, hetzner_dir: Path = HERE) -> list[str]:
    """Backward-compatible offline/test alias (never production mode)."""
    return install_execution_tree(dest, hetzner_dir=hetzner_dir, production=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("verify", help="Verify frozen module hashes and unit safety markers")
    sub.add_parser(
        "verify-deps",
        help="Verify offline import dependency closure (stdlib + local offbox only)",
    )
    stage_p = sub.add_parser("stage", help="Stage modules/units into a destination tree")
    stage_p.add_argument("--dest", required=True, type=Path, help="Offline/test destination")
    stage_p.add_argument(
        "--modules-only",
        action="store_true",
        help="Stage frozen modules only (skip unit templates)",
    )
    install_p = sub.add_parser(
        "install-execution-tree",
        help=(
            "Verify then install into <dest>/offbox and <dest>/deploy/hetzner "
            f"(production requires --production and dest={OFFBOX_EXEC_ROOT})"
        ),
    )
    install_p.add_argument(
        "--dest",
        required=True,
        type=Path,
        help=f"Execution-tree destination (production: {OFFBOX_EXEC_ROOT})",
    )
    install_p.add_argument(
        "--production",
        action="store_true",
        help=(
            f"Require exact destination {OFFBOX_EXEC_ROOT} and POSIX ancestry "
            "preflight before copy"
        ),
    )
    legacy_p = sub.add_parser(
        "install-app-tree",
        help="Legacy offline/test alias of install-execution-tree (never --production)",
    )
    legacy_p.add_argument("--dest", required=True, type=Path, help="Offline/test destination")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "verify":
            offbox = resolve_offbox_dir()
            listed = verify_modules(offbox)
            verify_units()
            verify_dependency_closure(offbox)
            print(
                f"VERIFY_OK modules={len(listed)} units={len(UNIT_NAMES)} "
                f"inventory=D5A2D0-P1 exec_root={OFFBOX_EXEC_ROOT} "
                f"interpreter={TRUSTED_INTERPRETER} "
                f"modules_dir={offbox.as_posix()}"
            )
            return 0
        if args.command == "verify-deps":
            offbox = resolve_offbox_dir()
            per_file = verify_dependency_closure(offbox)
            print(
                f"DEPS_OK modules={len(per_file)} stdlib_or_local_only=1 "
                f"modules_dir={offbox.as_posix()}"
            )
            return 0
        if args.command == "stage":
            dest = args.dest
            written = stage(dest, include_units=not args.modules_only)
            print(f"STAGE_OK dest={dest.resolve()} files={len(written)}")
            for path in written:
                print(path)
            return 0
        if args.command == "install-execution-tree":
            dest = args.dest
            written = install_execution_tree(dest, production=bool(args.production))
            print(
                f"INSTALL_EXEC_OK dest={_posix_dest(dest)} files={len(written)} "
                f"inventory=D5A2D0-P1 production={int(bool(args.production))}"
            )
            for path in written:
                print(path)
            return 0
        if args.command == "install-app-tree":
            dest = args.dest
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
