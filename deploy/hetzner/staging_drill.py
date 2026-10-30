"""Isolated local staging drill. Not a VPS deployment.

Copies the account-server import closure into a temporary tree, checks that
tree before creating databases, and exercises synthetic HTTP, backup, and
restore verification on loopback. The process environment is built from the
staging layout. The parent process environment is not copied.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import sync_backup
import sync_restore_verify

import staging_guard

REPO = Path(__file__).resolve().parents[2]
APP = REPO / "app"
SETUP = Path(__file__).resolve().with_name("setup.sh")
SERVER = Path(__file__).resolve().with_name("staging_server.py")
VOCAB_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
VOCAB_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
VOCAB_C = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
TRAP_KEY = "sk-trap-production-key-should-never-load"
_BASE_ENV = ("PATH", "SYSTEMROOT", "PATHEXT", "WINDIR", "COMSPEC", "SYSTEMDRIVE")


class DrillError(RuntimeError):
    """The local staging drill did not finish."""


class StagingProcess:
    """A staging server that is stopped on close, including after a failure."""

    def __init__(self, process: subprocess.Popen, layout: staging_guard.StagingLayout, streams: dict, proof: str):
        self.process = process
        self.layout = layout
        self.streams = streams
        self.proof = proof

    def stop(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        _wait_until_free(self.layout.port)

    def __enter__(self) -> "StagingProcess":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.stop()
        return False


def run_synthetic_drill(root: Path) -> dict:
    """Run the synthetic staging sequence under ``root``. ``root`` is not created first."""
    root = Path(root)
    before = _repo_snapshot()
    port = _choose_port()
    off = _layout(root, port, "0")
    staging_guard.validate(off)
    _materialize(off)
    staging_guard.validate(off, require_env_file=True)
    (root / ".env").write_text("OPENAI_API_KEY=" + TRAP_KEY + "\n", encoding="utf-8")
    _import_probe(off)
    _create_users(off)
    report = {"bind": off.bind, "port": port}
    running = None
    try:
        running = start_server(off)
        report.update(_section_off(running, expecting_db=False, label="off"))
        _assert_no_trap(running)
        running.stop()
        running = None
        on = _layout(root, port, "1")
        _wait_until_free(port)
        _write_env(on)
        staging_guard.validate(on, require_env_file=True)
        running = start_server(on)
        report.update(_section_on(running))
        report.update(_section_backup(on))
        sync_hash = _hash(on.sync_db)
        _assert_no_trap(running)
        running.stop()
        running = None
        _wait_until_free(port)
        _write_env(off)
        staging_guard.validate(off, require_env_file=True)
        running = start_server(off)
        report.update(_section_off(running, expecting_db=True, sync_hash=sync_hash, label="disabled"))
        _assert_no_trap(running)
    finally:
        if running is not None:
            running.stop()
    report["port_released"] = not staging_guard._port_is_occupied(port)
    report["trap_absent"] = TRAP_KEY not in (root / "language-guard-staging" / ".env").read_text(encoding="utf-8")
    report["repo_unchanged"] = _repo_snapshot() == before
    report["production_tree_absent"] = not Path("/opt/language-guard-staging").exists()
    return report


def start_server(layout: staging_guard.StagingLayout) -> StagingProcess:
    """Start one staging process. Caller must stop it."""
    staging_guard.validate(layout, require_env_file=True)
    proof = staging_guard.allocate_proof_path(layout)
    process = subprocess.Popen(
        [sys.executable, str(SERVER)],
        cwd=layout.package_dir,
        env=child_environment(layout, proof=proof),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    streams = {"out": [], "err": []}
    _pump(process.stdout, streams["out"])
    _pump(process.stderr, streams["err"])
    staging = StagingProcess(process, layout, streams, proof)
    try:
        _wait_ready(staging)
        _read_proof(proof, layout)
        return staging
    except Exception:
        staging.stop()
        raise


def child_environment(layout: staging_guard.StagingLayout, *, proof: str) -> dict:
    """Environment for the staging process. Does not copy the parent environment."""
    env = {}
    for name in _BASE_ENV:
        value = os.environ.get(name)
        if value:
            env[name] = value
    env.update(
        {
            "PYTHONPATH": layout.package_dir,
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUTF8": "1",
            "PYTHONUNBUFFERED": "1",
            "TEMP": layout.package_dir,
            "TMP": layout.package_dir,
            "ACCOUNT_BIND": layout.bind,
            "ACCOUNT_PORT": str(layout.port),
            "STAGING_PACKAGE_DIR": layout.package_dir,
            "STUDY_SYNC_DIR": layout.sync_dir,
            "STUDY_SYNC_BACKUP_DIR": layout.backup_dir,
            "STUDY_SYNC_VERIFY_DIR": layout.verify_root,
            "STAGING_ENV_FILE": layout.env_file,
            "STAGING_PROOF_DIR": layout.proof_dir,
            "OPENAI_API_KEY": layout.api_key,
            "OPENAI_BASE_URL": layout.openai_base_url,
            "STUDY_SYNC_ENABLED": layout.sync_enabled,
        }
    )
    if proof:
        env["STAGING_PROOF_FILE"] = proof
    return env


def _layout(root: Path, port: int, sync_enabled: str) -> staging_guard.StagingLayout:
    package = root / "language-guard-staging"
    sync_dir = root / "sync"
    return staging_guard.StagingLayout(
        bind=staging_guard.REQUIRED_BIND,
        port=port,
        package_dir=str(package),
        account_db=str(package / "accounts.db"),
        sync_dir=str(sync_dir),
        sync_db=str(sync_dir / "study_sync.db"),
        backup_dir=str(root / "backups"),
        verify_root=str(root / "verify"),
        env_file=str(package / ".env"),
        proof_dir=str(root / "proof"),
        api_key=staging_guard.STAGING_FAKE_API_KEY,
        sync_enabled=sync_enabled,
        openai_base_url=staging_guard.STAGING_FAKE_BASE_URL,
    )


def _materialize(layout: staging_guard.StagingLayout) -> None:
    for directory in (
        layout.package_dir,
        layout.sync_dir,
        layout.backup_dir,
        layout.verify_root,
        layout.proof_dir,
    ):
        os.makedirs(directory, exist_ok=True)
    for name in _package_python_files():
        source = APP / name
        if not source.is_file():
            raise DrillError("missing package file")
        destination = Path(layout.package_dir) / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    _write_env(layout)


def _write_env(layout: staging_guard.StagingLayout) -> None:
    lines = [
        "OPENAI_API_KEY=" + layout.api_key,
        "OPENAI_BASE_URL=" + layout.openai_base_url,
        "ACCOUNT_BIND=" + layout.bind,
        "ACCOUNT_PORT=" + str(layout.port),
        "STUDY_SYNC_DIR=" + layout.sync_dir,
        "STUDY_SYNC_ENABLED=" + layout.sync_enabled,
        "",
    ]
    Path(layout.env_file).write_text("\n".join(lines), encoding="utf-8")


def _package_python_files() -> list:
    text = SETUP.read_text(encoding="utf-8")
    match = re.search(r"FILES=\((.*?)\)", text, re.S)
    if not match:
        raise DrillError("package list missing")
    return re.findall(r"[A-Za-z0-9_./-]+\.py", match.group(1))


def _import_probe(layout: staging_guard.StagingLayout) -> None:
    script = (
        "import account_server\n"
        "assert account_server.sync_http.sync_enabled() is False\n"
        "print('import-ok')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=layout.package_dir,
        env=child_environment(layout, proof=""),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )
    if result.returncode != 0 or "import-ok" not in result.stdout:
        raise DrillError(result.stderr[-500:])
    if TRAP_KEY in result.stdout or TRAP_KEY in result.stderr:
        raise DrillError("trap key reached the import probe")
    if Path(layout.sync_db).exists():
        raise DrillError("import created the sync database")


def _create_users(layout: staging_guard.StagingLayout) -> None:
    script = (
        "import account_store\n"
        "account_store.add_user('staginga', 'secret1')\n"
        "account_store.add_user('stagingb', 'secret2')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=layout.package_dir,
        env=child_environment(layout, proof=""),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )
    if result.returncode != 0:
        raise DrillError(result.stderr[-500:])


def _section_off(
    server: StagingProcess,
    *,
    expecting_db: bool,
    label: str,
    sync_hash: str = "",
) -> dict:
    token = _login(server.layout.port, "staginga", "secret1")
    mocks = []
    for path, name in (
        ("/api/grade", "grade"),
        ("/api/reading", "reading"),
        ("/api/listening", "listening"),
        ("/api/enrich", "enrich"),
    ):
        status, body = _post(server.layout.port, path, {"word": "huis"}, token)
        if status != 200 or body != {"mock": name}:
            raise DrillError("mocked AI route failed")
        mocks.append(name)
    hidden, hidden_body = _post(
        server.layout.port,
        "/api/sync/vocabulary/put",
        _put_body(VOCAB_A, "house", 0, "op-hidden"),
        token,
    )
    if hidden != 404 or hidden_body.get("error") != "Không có chức năng này.":
        raise DrillError("sync route was not hidden")
    exists = Path(server.layout.sync_db).is_file()
    if exists != expecting_db:
        raise DrillError("sync database presence mismatch")
    if expecting_db and _hash(server.layout.sync_db) != sync_hash:
        raise DrillError("sync database changed while disabled")
    login_again = _login(server.layout.port, "stagingb", "secret2")
    return {
        label + "_login": 200,
        label + "_mocks": mocks,
        label + "_sync_status": hidden,
        label + "_db_exists": exists,
        label + "_second_login": bool(login_again),
    }


def _section_on(server: StagingProcess) -> dict:
    port = server.layout.port
    missing, _body = _post(port, "/api/sync/vocabulary/put", _put_body(VOCAB_A, "house", 0, "op-no-auth"))
    invalid, _body = _post(
        port,
        "/api/sync/vocabulary/put",
        _put_body(VOCAB_A, "house", 0, "op-bad-auth"),
        "not-a-session",
    )
    if missing != 401 or invalid != 401:
        raise DrillError("unauthenticated sync was accepted")
    if Path(server.layout.sync_db).exists():
        raise DrillError("unauthenticated sync created the database")
    token_a = _login(port, "staginga", "secret1")
    token_b = _login(port, "stagingb", "secret2")
    created, created_body = _post(port, "/api/sync/vocabulary/put", _put_body(VOCAB_A, "house", 0, "op-a-create", user_id=999), token_a)
    updated, updated_body = _post(port, "/api/sync/vocabulary/put", _put_body(VOCAB_A, "house-2", 1, "op-a-update"), token_a)
    replay, replay_body = _post(port, "/api/sync/vocabulary/put", _put_body(VOCAB_A, "house-2", 1, "op-a-update"), token_a)
    reused, _reused_body = _post(port, "/api/sync/vocabulary/put", _put_body(VOCAB_A, "other", 1, "op-a-update"), token_a)
    stale, _stale_body = _post(port, "/api/sync/vocabulary/put", _put_body(VOCAB_A, "house-3", 1, "op-a-stale"), token_a)
    deleted, deleted_body = _post(port, "/api/sync/vocabulary/delete", _delete_body(VOCAB_A, 2, "op-a-delete"), token_a)
    other, other_body = _post(port, "/api/sync/vocabulary/put", _put_body(VOCAB_B, "book", 0, "op-b-create"), token_a)
    _require_ok(created, created_body, 1, False)
    _require_ok(updated, updated_body, 2, False)
    _require_ok(replay, replay_body, 2, False)
    if reused != 409 or stale != 409:
        raise DrillError("conflict was not rejected")
    _require_ok(deleted, deleted_body, 3, True)
    _require_ok(other, other_body, 1, False)
    pages = _walk_changes(port, token_a)
    if [item["cursor"] for item in pages] != sorted(item["cursor"] for item in pages):
        raise DrillError("cursors were not ordered")
    if len(pages) < 4 or not any(item["deleted"] and item["vocab_id"] == VOCAB_A for item in pages):
        raise DrillError("history was incomplete")
    foreign, foreign_body = _post(port, "/api/sync/vocabulary/changes", {"limit": 50}, token_b)
    if foreign != 200 or any(item["vocab_id"] in (VOCAB_A, VOCAB_B) for item in foreign_body["changes"]):
        raise DrillError("second account saw the first account")
    private, private_body = _post(port, "/api/sync/vocabulary/put", _put_body(VOCAB_C, "tree", 0, "op-c-create"), token_b)
    _require_ok(private, private_body, 1, False)
    again, again_body = _post(port, "/api/sync/vocabulary/changes", {"limit": 50}, token_a)
    if again != 200 or any(item["vocab_id"] == VOCAB_C for item in again_body["changes"]):
        raise DrillError("first account saw the second account")
    return {
        "missing_bearer": missing,
        "invalid_bearer": invalid,
        "create_revision": created_body["revision"],
        "update_revision": updated_body["revision"],
        "replay_revision": replay_body["revision"],
        "reuse_status": reused,
        "stale_status": stale,
        "delete_revision": deleted_body["revision"],
        "delete_tombstone": deleted_body["deleted"] is True,
        "pages": len(pages),
        "cursors_ordered": True,
        "other_account_hidden": True,
        "spoofed_user_hidden": True,
    }


def _section_backup(layout: staging_guard.StagingLayout) -> dict:
    source = Path(layout.sync_db)
    before = source.read_bytes()
    published = sync_backup.backup_database(str(source), layout.backup_dir)
    if published is None:
        raise DrillError("backup did not publish")
    after_backup = source.read_bytes()
    if after_backup != before:
        raise DrillError("backup changed the source")
    backup_bytes = Path(published.path).read_bytes()
    verified = sync_restore_verify.verify_latest_backup(
        layout.backup_dir,
        layout.verify_root,
        layout.sync_db,
    )
    if verified.status != sync_restore_verify.STATUS_VERIFIED:
        raise DrillError("restore verification failed")
    if source.read_bytes() != before or Path(published.path).read_bytes() != backup_bytes:
        raise DrillError("verification changed a database")
    inspect = Path(layout.backup_dir).parent / "inspect.db"
    if inspect.exists():
        raise DrillError("inspect destination already existed")
    sync_backup.restore_database(published.path, str(inspect))
    try:
        sync_backup.restore_database(published.path, layout.sync_db)
    except sync_backup.SyncBackupError:
        overwrite_refused = True
    else:
        overwrite_refused = False
    if source.read_bytes() != before or not overwrite_refused:
        raise DrillError("restore overwrote an existing database")
    distinct = {
        os.path.normcase(os.path.realpath(path))
        for path in (layout.account_db, layout.sync_db, published.path, str(inspect))
    }
    if len(distinct) != 4:
        raise DrillError("restored database was not separate")
    version, integrity, tombstone = _inspect(str(inspect))
    if version != 2 or integrity != "ok" or not tombstone:
        raise DrillError("restored contents were incomplete")
    return {
        "verify_status": verified.status,
        "schema_version": version,
        "integrity": integrity,
        "source_unchanged": True,
        "backup_unchanged": True,
        "overwrite_refused": True,
    }


def _inspect(path: str) -> tuple:
    connection = sqlite3.connect(sync_backup._sqlite_uri(path, read_only=True), uri=True)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        version = connection.execute(
            "SELECT value FROM sync_meta WHERE key = 'schema_version'"
        ).fetchone()[0]
        tombstone = connection.execute(
            "SELECT revision, deleted FROM vocabulary_entities WHERE vocab_id = ?",
            (VOCAB_A,),
        ).fetchone()
        history = connection.execute("SELECT COUNT(*) FROM vocabulary_changes").fetchone()[0]
    finally:
        connection.close()
    return int(version), str(integrity), bool(tombstone) and int(tombstone[0]) == 3 and int(tombstone[1]) == 1 and history >= 4


def _walk_changes(port: int, token: str) -> list:
    cursor = 0
    seen = []
    for _ in range(10):
        status, body = _post(
            port,
            "/api/sync/vocabulary/changes",
            {"after_cursor": cursor, "limit": 1},
            token,
        )
        if status != 200:
            raise DrillError("change page failed")
        rows = body["changes"]
        if not rows:
            if body["has_more"]:
                raise DrillError("empty page reported more changes")
            break
        if len(rows) != 1 or rows[0]["cursor"] <= cursor:
            raise DrillError("page was not ordered")
        seen.append(rows[0])
        cursor = body["next_cursor"]
        if not body["has_more"]:
            break
    return seen


def _login(port: int, username: str, password: str) -> str:
    status, body = _post(port, "/api/login", {"username": username, "password": password})
    if status != 200 or not body.get("token"):
        raise DrillError("login failed")
    return body["token"]


def _put_body(vocab_id: str, meaning: str, expected: int, operation: str, user_id: int = 0) -> dict:
    body = {
        "language_code": "nl",
        "vocab_id": vocab_id,
        "payload": {"id": vocab_id, "word": "huis", "meaning": meaning},
        "expected_revision": expected,
        "operation_id": operation,
    }
    if user_id:
        body["user_id"] = user_id
    return body


def _delete_body(vocab_id: str, expected: int, operation: str) -> dict:
    return {
        "language_code": "nl",
        "vocab_id": vocab_id,
        "expected_revision": expected,
        "operation_id": operation,
    }


def _require_ok(status: int, body: dict, revision: int, deleted: bool) -> None:
    if status != 200 or body.get("revision") != revision or body.get("deleted") is not deleted:
        raise DrillError("sync mutation failed")


def _post(port: int, path: str, payload: dict, token: str = ""):
    if port == staging_guard.PRODUCTION_PORT:
        raise DrillError("refusing the production port")
    request = urllib.request.Request(
        "http://127.0.0.1:%s%s" % (port, path),
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
    )
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", "Bearer " + token)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


def _assert_no_trap(server: StagingProcess) -> None:
    text = "".join(server.streams["out"]) + "".join(server.streams["err"])
    if TRAP_KEY in text or "sk-" in text:
        raise DrillError("trap key reached the staging process")


def _read_proof(path: str, layout: staging_guard.StagingLayout) -> None:
    deadline = time.time() + 5
    while not os.path.exists(path):
        if time.time() > deadline:
            raise DrillError("effective staging proof missing")
        time.sleep(0.05)
    proof = json.loads(Path(path).read_text(encoding="utf-8"))
    text = Path(path).read_text(encoding="utf-8")
    if TRAP_KEY in text or "sk-" in text or staging_guard.STAGING_FAKE_API_KEY in text:
        raise DrillError("proof contained a provider key")
    allowed = {"base_url", "bind", "key_is_staging_fake", "port", "sync_enabled"}
    if set(proof) != allowed:
        raise DrillError("proof fields were not limited to status")
    if proof.get("bind") != staging_guard.REQUIRED_BIND or proof.get("port") != layout.port:
        raise DrillError("effective bind was not loopback")
    if proof.get("key_is_staging_fake") is not True:
        raise DrillError("effective key was not the staging fake")
    if proof.get("base_url") != staging_guard.STAGING_FAKE_BASE_URL:
        raise DrillError("effective provider URL was not loopback")
    expected_on = layout.sync_enabled == "1"
    if proof.get("sync_enabled") is not expected_on:
        raise DrillError("effective sync flag mismatch")


def _wait_ready(server: StagingProcess) -> None:
    proof = server.proof
    deadline = time.time() + 30
    while time.time() < deadline:
        if server.process.poll() is not None:
            raise DrillError(_process_output(server))
        if os.path.exists(proof) and staging_guard._port_is_occupied(server.layout.port):
            return
        time.sleep(0.05)
    raise DrillError(_process_output(server) or "staging server did not become ready")


def _process_output(server: StagingProcess) -> str:
    return ("".join(server.streams["err"]) + "".join(server.streams["out"]))[-800:]


def _pump(stream, sink: list) -> None:
    def read() -> None:
        for line in stream:
            sink.append(line)

    threading.Thread(target=read, daemon=True).start()


def _choose_port() -> int:
    for _ in range(5):
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            probe.bind((staging_guard.REQUIRED_BIND, 0))
            port = int(probe.getsockname()[1])
        finally:
            probe.close()
        if port != staging_guard.PRODUCTION_PORT:
            return port
    raise DrillError("no staging port")


def _wait_until_free(port: int) -> None:
    deadline = time.time() + 5
    while time.time() < deadline:
        if not staging_guard._port_is_occupied(port):
            return
        time.sleep(0.05)
    raise DrillError("staging port stayed occupied")


def _hash(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _repo_snapshot() -> tuple:
    rows = []
    for path in (APP / "accounts.db", APP / "study_sync.db", REPO / ".env"):
        if path.exists():
            stat = path.stat()
            rows.append((str(path), stat.st_size, stat.st_mtime_ns))
        else:
            rows.append((str(path), None, None))
    return tuple(rows)


def main() -> int:
    sys.stderr.write("staging drill is a local test harness and does not create a host staging tree\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
