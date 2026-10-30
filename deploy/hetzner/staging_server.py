"""Launch one isolated staging account server.

The parent process must already have passed ``staging_guard`` and must
start this file with the copied package on ``PYTHONPATH``. AI handlers are
replaced before ``serve`` so the fake startup key is never sent to a provider.
"""

from __future__ import annotations

import os
import sys

import staging_guard


def main() -> int:
    layout = staging_guard.layout_from_environ()
    try:
        staging_guard.validate(layout, require_env_file=True)
        proof = (os.environ.get("STAGING_PROOF_FILE") or "").strip()
        if proof:
            staging_guard.validate_proof_path(layout, proof)
        else:
            proof = staging_guard.allocate_proof_path(layout)
    except staging_guard.StagingGuardError as error:
        sys.stderr.write("staging guard rejected\n")
        sys.stderr.write(error.code + "\n")
        return 1
    import account_server
    import account_store
    import config
    import sync_http

    if not _effective_matches(layout, account_server, account_store, config, sync_http):
        sys.stderr.write("staging guard rejected\n")
        sys.stderr.write("effective\n")
        return 2
    account_server._grade = _mock("grade")
    account_server._reading = _mock("reading")
    account_server._listening = _mock("listening")
    account_server._enrich = _mock("enrich")
    try:
        staging_guard.write_proof(layout, proof, sync_enabled=sync_http.sync_enabled())
    except staging_guard.StagingGuardError as error:
        sys.stderr.write("staging guard rejected\n")
        sys.stderr.write(error.code + "\n")
        return 1
    return account_server.serve()


def _effective_matches(layout, account_server, account_store, config, sync_http) -> bool:
    if config.OPENAI_API_KEY != staging_guard.STAGING_FAKE_API_KEY:
        return False
    if account_server.HOST != staging_guard.REQUIRED_BIND:
        return False
    if account_server.PORT != layout.port or account_server.PORT == staging_guard.PRODUCTION_PORT:
        return False
    if os.environ.get("OPENAI_API_KEY") != staging_guard.STAGING_FAKE_API_KEY:
        return False
    if os.environ.get("OPENAI_BASE_URL") != staging_guard.STAGING_FAKE_BASE_URL:
        return False
    account_real = os.path.normcase(os.path.realpath(account_store.db_path()))
    sync_real = os.path.normcase(os.path.realpath(sync_http.sync_db_path()))
    if account_real != os.path.normcase(os.path.realpath(layout.account_db)):
        return False
    if sync_real != os.path.normcase(os.path.realpath(layout.sync_db)):
        return False
    return True


def _mock(name: str):
    def respond(_payload):
        return {"mock": name}

    return respond


if __name__ == "__main__":
    raise SystemExit(main())
