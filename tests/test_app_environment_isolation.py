"""Environment identity and isolation (ADR-025). No live production network."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

import app_environment
import config


@pytest.fixture(autouse=True)
def _reset_identity(monkeypatch):
    app_environment.reset_identity_cache()
    monkeypatch.delenv("LG_APP_ENVIRONMENT", raising=False)
    monkeypatch.delenv("APP_ENVIRONMENT", raising=False)
    monkeypatch.delenv("LG_DATA_DIR", raising=False)
    monkeypatch.delenv("LG_TRUSTED_STAGING_HOSTS", raising=False)
    yield
    app_environment.reset_identity_cache()


def _manifest(channel: str, tmp_path: Path) -> app_environment.BuildManifest:
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "build_manifest.json"
    path.write_text(
        json.dumps(
            {
                "channel": channel,
                "version": "1.4.0-test",
                "commit_sha": "abc123deadbeef",
                "built_at": "2026-11-19T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    return app_environment.load_build_manifest(str(path))


def test_development_staging_production_identity_labels(tmp_path):
    for channel, title_bit in (
        ("development", "DEVELOPMENT"),
        ("staging", "STAGING"),
        ("production", "PRODUCTION"),
    ):
        identity = app_environment.resolve_identity(
            manifest=_manifest(channel, tmp_path / channel),
            runtime_override=channel,
            frozen=True,
        )
        assert identity.runtime_environment == channel
        assert identity.build_channel == channel
        assert title_bit in identity.display_title()
        assert identity.network_writes_allowed


def test_details_expose_backend_host_and_sha(tmp_path):
    identity = app_environment.resolve_identity(
        manifest=_manifest("staging", tmp_path),
        runtime_override="staging",
        frozen=True,
    )
    details = app_environment.environment_details(
        identity=identity,
        backend_url="http://127.0.0.1:8765",
        data_directory=r"C:\Users\x\AppData\Roaming\langstudyguard-staging",
        account_label="alice (id 2)",
        cloud_sync_label="Pending",
        cloud_sync_detail="Upload or download in progress",
    )
    assert details["backend_host"] == "127.0.0.1"
    assert details["git_commit_sha"] == "abc123deadbeef"
    assert details["build_channel"] == "staging"
    assert "token" not in json.dumps(details).lower()
    assert "password" not in json.dumps(details).lower()


def test_staging_data_folder_isolated_from_production(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    staging = app_environment.resolve_identity(
        manifest=_manifest("staging", tmp_path),
        frozen=True,
    )
    production = app_environment.resolve_identity(
        manifest=_manifest("production", tmp_path / "prod"),
        frozen=True,
    )
    assert staging.data_folder == "langstudyguard-staging"
    assert production.data_folder == "langstudyguard"
    assert staging.data_folder != production.data_folder
    assert staging.exe_basename == "langstudyguard-staging.exe"
    assert production.exe_basename == "langstudyguard.exe"

    app_environment.reset_identity_cache()
    monkeypatch.setattr(app_environment, "load_build_manifest", lambda path=None: staging)
    monkeypatch.setattr(config, "is_frozen", lambda: True)
    # Force config to use our staging identity
    monkeypatch.setattr(config, "environment_identity", lambda: staging)
    data = config.data_dir()
    install = config.install_dir()
    assert os.path.basename(data) == "langstudyguard-staging"
    assert os.path.basename(install) == "langstudyguard-staging"
    assert os.path.basename(data) != "langstudyguard"


def test_staging_refuses_production_endpoint(tmp_path):
    identity = app_environment.resolve_identity(
        manifest=_manifest("staging", tmp_path),
        frozen=True,
    )
    err = app_environment.validate_backend_for_identity(
        identity, "https://langstudyguard.com"
    )
    assert err and "production host" in err
    with pytest.raises(app_environment.EnvironmentIdentityError):
        app_environment.assert_network_writes_allowed(
            "https://api.langstudyguard.com",
            identity=identity,
        )


def test_staging_allows_localhost(tmp_path):
    identity = app_environment.resolve_identity(
        manifest=_manifest("staging", tmp_path),
        frozen=True,
    )
    assert (
        app_environment.validate_backend_for_identity(
            identity, "http://127.0.0.1:8765"
        )
        is None
    )


def test_channel_runtime_mismatch_fails_closed(tmp_path):
    identity = app_environment.resolve_identity(
        manifest=_manifest("staging", tmp_path),
        runtime_override="production",
        frozen=True,
    )
    # Frozen builds pin runtime to build channel; conflicting override becomes error.
    assert identity.identity_error or identity.runtime_environment == "staging"
    if identity.identity_error:
        assert not identity.network_writes_allowed


def test_missing_manifest_frozen_fails_closed():
    identity = app_environment.resolve_identity(manifest=None, frozen=True)
    assert identity.identity_error
    assert not identity.network_writes_allowed
    with pytest.raises(app_environment.EnvironmentIdentityError):
        app_environment.assert_network_writes_allowed(
            "http://127.0.0.1:8765",
            identity=identity,
        )


def test_production_settings_token_not_adopted_by_staging(tmp_path):
    identity = app_environment.resolve_identity(
        manifest=_manifest("staging", tmp_path),
        frozen=True,
    )
    legacy_production_settings = {
        "account_token": "prod-secret-token",
        "account_username": "owner",
        # no environment marker → production-only adoption
    }
    assert not app_environment.settings_token_compatible(
        legacy_production_settings, identity
    )
    production = app_environment.resolve_identity(
        manifest=_manifest("production", tmp_path / "p"),
        frozen=True,
    )
    assert app_environment.settings_token_compatible(
        legacy_production_settings, production
    )


def test_cloud_sync_never_guesses_synced():
    label, detail = app_environment.cloud_sync_ui_state(
        signed_in=False, engine_running=False
    )
    assert "Guest" in label or "Disabled" in label
    assert label != "Synced"

    label, detail = app_environment.cloud_sync_ui_state(
        signed_in=True, engine_running=False
    )
    assert "Server Sync disabled" in label
    assert "Synced" not in label

    label, _ = app_environment.cloud_sync_ui_state(
        signed_in=True,
        engine_running=True,
        engine_status="pending",
        caught_up=False,
    )
    assert label == "Pending"

    label, _ = app_environment.cloud_sync_ui_state(
        signed_in=True,
        engine_running=True,
        engine_status="synced",
        caught_up=True,
    )
    assert label == "Synced"

    label, _ = app_environment.cloud_sync_ui_state(
        signed_in=True,
        engine_running=True,
        engine_status="synced",
        caught_up=False,
    )
    assert label == "Pending"


def test_account_client_blocks_production_from_staging(tmp_path, monkeypatch):
    import account_client

    identity = app_environment.resolve_identity(
        manifest=_manifest("staging", tmp_path),
        frozen=True,
    )
    monkeypatch.setattr(app_environment, "get_identity", lambda refresh=False: identity)
    monkeypatch.setattr(config, "ACCOUNT_SERVER_URL", "https://langstudyguard.com")
    with pytest.raises(account_client.AccountError) as caught:
        account_client._post("/api/login", {"username": "x", "password": "y"})
    assert "production host" in str(caught.value).lower() or "refused" in str(
        caught.value
    ).lower()


def test_staging_smoke_synthetic_accounts_separate_dbs(tmp_path, monkeypatch):
    """Synthetic staging accounts write under staging data root only."""
    from account_local_store import AccountLocalStore, db_path

    staging_root = tmp_path / "langstudyguard-staging"
    production_root = tmp_path / "langstudyguard"
    production_root.mkdir()
    marker = production_root / "settings.json"
    marker.write_text('{"account_token":"prod-only"}', encoding="utf-8")
    before = marker.read_text(encoding="utf-8")

    monkeypatch.setenv("LG_DATA_DIR", str(staging_root))
    store_a = AccountLocalStore(101, data_root=str(staging_root))
    store_b = AccountLocalStore(202, data_root=str(staging_root))
    store_a.close()
    store_b.close()

    assert Path(db_path(101, str(staging_root))).is_file()
    assert Path(db_path(202, str(staging_root))).is_file()
    assert not (production_root / "accounts").exists()
    assert marker.read_text(encoding="utf-8") == before


def test_unknown_configuration_blocks_writes():
    bad = app_environment.EnvironmentIdentity(
        build_channel="unknown",
        runtime_environment="unknown",
        version="x",
        commit_sha="y",
        data_folder="langstudyguard-staging",
        install_folder="langstudyguard-staging",
        exe_basename="langstudyguard-staging.exe",
        startup_link="langstudyguard-staging.lnk",
        network_writes_allowed=False,
        identity_error="incomplete",
    )
    with pytest.raises(app_environment.EnvironmentIdentityError):
        app_environment.assert_network_writes_allowed(
            "http://127.0.0.1:8765", identity=bad
        )


def test_f1_lg_data_dir_rejects_production_appdata(tmp_path, monkeypatch):
    roaming = tmp_path / "Roaming"
    local = tmp_path / "Local"
    prod = roaming / "langstudyguard"
    prod.mkdir(parents=True)
    (prod / "settings.json").write_text('{"account_token":"keep"}', encoding="utf-8")
    before = (prod / "settings.json").read_text(encoding="utf-8")

    identity = app_environment.resolve_identity(
        manifest=_manifest("staging", tmp_path / "m"),
        frozen=True,
    )
    monkeypatch.setattr(config, "environment_identity", lambda: identity)
    monkeypatch.setenv("APPDATA", str(roaming))
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setenv("LG_DATA_DIR", str(prod))

    with pytest.raises(app_environment.EnvironmentIdentityError) as caught:
        config.data_dir()
    assert "production" in str(caught.value).lower()
    assert (prod / "settings.json").read_text(encoding="utf-8") == before


def test_f1_lg_data_dir_allows_isolated_synthetic(tmp_path, monkeypatch):
    identity = app_environment.resolve_identity(
        manifest=_manifest("development", tmp_path / "m"),
        frozen=True,
    )
    monkeypatch.setattr(config, "environment_identity", lambda: identity)
    synthetic = tmp_path / "synthetic-dev-data"
    synthetic.mkdir()
    monkeypatch.setenv("LG_DATA_DIR", str(synthetic))
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    resolved = config.data_dir()
    assert Path(resolved) == synthetic.resolve()


def test_f1_rejects_overlap_into_production_install(tmp_path):
    identity = app_environment.resolve_identity(
        manifest=_manifest("staging", tmp_path / "m"),
        frozen=True,
    )
    local = tmp_path / "Local"
    install = local / "langstudyguard"
    install.mkdir(parents=True)
    err = app_environment.validate_data_root_for_identity(
        str(install / "nested"),
        identity,
        appdata=str(tmp_path / "Roaming"),
        localappdata=str(local),
    )
    assert err and "production" in err.lower()


def test_f2_account_client_refuses_redirect_to_production(tmp_path, monkeypatch):
    """Localhost issues a 302 to a production host — credentials never follow."""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    import account_client

    identity = app_environment.resolve_identity(
        manifest=_manifest("staging", tmp_path / "m"),
        frozen=True,
    )
    monkeypatch.setattr(app_environment, "get_identity", lambda refresh=False: identity)

    hit = {"count": 0}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            hit["count"] += 1
            self.send_response(302)
            self.send_header("Location", "https://langstudyguard.com/api/login")
            self.end_headers()

        def log_message(self, *_args):
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(config, "ACCOUNT_SERVER_URL", f"http://127.0.0.1:{port}")
    try:
        with pytest.raises(account_client.AccountError) as caught:
            account_client._post(
                "/api/login",
                {"username": "synth", "password": "synth-secret"},
                token="bearer-must-not-travel",
            )
        message = str(caught.value).lower()
        assert "production" in message or "redirect" in message or "refused" in message
        assert hit["count"] == 1
    finally:
        server.shutdown()
        server.server_close()


def test_f2_assert_redirect_allowed_blocks_production_location(tmp_path):
    identity = app_environment.resolve_identity(
        manifest=_manifest("development", tmp_path / "m"),
        frozen=True,
    )
    with pytest.raises(app_environment.RedirectRejected) as caught:
        app_environment.assert_redirect_allowed(
            "https://api.langstudyguard.com/v1",
            identity=identity,
        )
    assert "production" in str(caught.value).lower()


def test_f3_login_window_title_exposes_environment(tmp_path, monkeypatch):
    import setup_wizard

    for channel, expected in (
        ("staging", "STAGING"),
        ("development", "DEVELOPMENT"),
        ("production", "PRODUCTION"),
    ):
        identity = app_environment.resolve_identity(
            manifest=_manifest(channel, tmp_path / channel),
            frozen=True,
        )
        monkeypatch.setattr(config, "environment_identity", lambda idn=identity: idn)
        title = setup_wizard._window_title()
        assert expected in title
        assert "token" not in title.lower()
        assert "password" not in title.lower()
