"""RC smoke isolation — synthetic paths only; no production network contact."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

import app_environment
import config
import install
import updater


def _manifest(channel: str, tmp: Path):
    path = tmp / "build_manifest.json"
    path.write_text(
        json.dumps(
            {
                "channel": channel,
                "version": "1.4.0",
                "commit_sha": "rc-test-sha",
            }
        ),
        encoding="utf-8",
    )
    return app_environment.load_build_manifest(path)


@pytest.fixture(autouse=True)
def _clear_env_leaks(monkeypatch):
    monkeypatch.delenv("LG_APP_ENVIRONMENT", raising=False)
    monkeypatch.delenv("APP_ENVIRONMENT", raising=False)
    monkeypatch.delenv("LANGUAGE_GUARD_ENV", raising=False)
    monkeypatch.delenv("LG_DATA_DIR", raising=False)
    app_environment.reset_identity_cache()


def test_rc_identity_uses_isolated_appdata_folder(tmp_path, monkeypatch):
    monkeypatch.delenv("LG_RC_SMOKE", raising=False)
    monkeypatch.setattr(sys, "argv", ["langstudyguard-rc.exe"])
    identity = app_environment.resolve_identity(
        manifest=_manifest("production", tmp_path),
        frozen=True,
        rc_smoke=True,
    )
    assert identity.rc_smoke is True
    assert identity.build_channel == "production"
    assert identity.runtime_environment == "production"
    assert identity.data_folder == app_environment.RC_DATA_FOLDER
    assert identity.install_folder == app_environment.RC_DATA_FOLDER
    assert identity.exe_basename == app_environment.RC_EXE_BASENAME
    assert "PRODUCTION BACKEND" in identity.display_title()
    assert "RC TEST DATA" in identity.banner_text()
    assert identity.is_production is False
    assert identity.is_non_production is True


def test_rc_data_dir_isolated_from_existing_production(tmp_path, monkeypatch):
    roaming = tmp_path / "Roaming"
    local = tmp_path / "Local"
    prod = roaming / "langstudyguard"
    prod.mkdir(parents=True)
    (prod / "settings.json").write_text(
        json.dumps(
            {
                "account_token": "prod-token-must-not-leak",
                "account_username": "produser",
                "environment": "production",
            }
        ),
        encoding="utf-8",
    )
    before = (prod / "settings.json").read_text(encoding="utf-8")
    installed = local / "langstudyguard" / "langstudyguard.exe"
    installed.parent.mkdir(parents=True)
    installed.write_bytes(b"MZ-prod")

    identity = app_environment.resolve_identity(
        manifest=_manifest("production", tmp_path),
        frozen=True,
        rc_smoke=True,
    )
    monkeypatch.setattr(config, "environment_identity", lambda: identity)
    monkeypatch.setattr(config, "is_frozen", lambda: True)
    monkeypatch.setenv("APPDATA", str(roaming))
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.delenv("LG_DATA_DIR", raising=False)
    app_environment.reset_identity_cache()

    resolved = config.data_dir()
    assert Path(resolved).name == app_environment.RC_DATA_FOLDER
    assert Path(resolved) == (roaming / app_environment.RC_DATA_FOLDER).resolve()
    assert (prod / "settings.json").read_text(encoding="utf-8") == before
    assert installed.read_bytes() == b"MZ-prod"
    assert not paths_share(resolved, prod)


def paths_share(a, b) -> bool:
    return app_environment.paths_overlap(str(a), str(b))


def test_rc_refuses_lg_data_dir_pointing_at_production(tmp_path, monkeypatch):
    roaming = tmp_path / "Roaming"
    local = tmp_path / "Local"
    prod = roaming / "langstudyguard"
    prod.mkdir(parents=True)
    identity = app_environment.resolve_identity(
        manifest=_manifest("production", tmp_path),
        frozen=True,
        rc_smoke=True,
    )
    monkeypatch.setattr(config, "environment_identity", lambda: identity)
    monkeypatch.setenv("APPDATA", str(roaming))
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setenv("LG_DATA_DIR", str(prod))

    with pytest.raises(app_environment.EnvironmentIdentityError) as caught:
        config.data_dir()
    assert "production" in str(caught.value).lower() or "RC smoke" in str(caught.value)


def test_rc_does_not_adopt_production_tokens(tmp_path):
    identity = app_environment.resolve_identity(
        manifest=_manifest("production", tmp_path),
        frozen=True,
        rc_smoke=True,
    )
    prod_settings = {
        "account_token": "prod-secret",
        "environment": "production",
    }
    legacy = {"account_token": "legacy-prod"}
    assert app_environment.settings_token_compatible(prod_settings, identity) is False
    assert app_environment.settings_token_compatible(legacy, identity) is False
    rc_settings = {
        "account_token": "rc-only",
        "environment": app_environment.RC_SETTINGS_MARKER,
    }
    assert app_environment.settings_token_compatible(rc_settings, identity) is True
    assert app_environment.settings_environment_marker(identity) == (
        app_environment.RC_SETTINGS_MARKER
    )


def test_rc_session_writes_stay_in_rc_store(tmp_path, monkeypatch):
    roaming = tmp_path / "Roaming"
    local = tmp_path / "Local"
    prod = roaming / "langstudyguard"
    prod.mkdir(parents=True)
    (prod / "settings.json").write_text(
        json.dumps({"account_token": "prod-token", "environment": "production"}),
        encoding="utf-8",
    )
    before = (prod / "settings.json").read_text(encoding="utf-8")

    identity = app_environment.resolve_identity(
        manifest=_manifest("production", tmp_path),
        frozen=True,
        rc_smoke=True,
    )
    monkeypatch.setattr(config, "environment_identity", lambda: identity)
    monkeypatch.setattr(config, "is_frozen", lambda: True)
    monkeypatch.setenv("APPDATA", str(roaming))
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.delenv("LG_DATA_DIR", raising=False)
    config.SETTINGS_FILE = str(roaming / app_environment.RC_DATA_FOLDER / "settings.json")

    config.save_account("rcuser", "rc-token-value", user_id=9)
    rc_settings = json.loads(
        (roaming / app_environment.RC_DATA_FOLDER / "settings.json").read_text(
            encoding="utf-8"
        )
    )
    assert rc_settings["account_username"] == "rcuser"
    assert rc_settings["account_token"] == "rc-token-value"
    assert rc_settings["environment"] == app_environment.RC_SETTINGS_MARKER
    assert (prod / "settings.json").read_text(encoding="utf-8") == before


def test_rc_updater_blocked(tmp_path, monkeypatch):
    identity = app_environment.resolve_identity(
        manifest=_manifest("production", tmp_path),
        frozen=True,
        rc_smoke=True,
    )
    monkeypatch.setattr(config, "environment_identity", lambda: identity)
    monkeypatch.setattr(config, "is_frozen", lambda: True)
    monkeypatch.setenv("LG_RC_SMOKE", "1")
    assert updater.updates_allowed() is False
    with pytest.raises(OSError, match="RC|updater|production"):
        updater._swap_and_restart(str(tmp_path / "fake.exe"))


def test_production_identity_unchanged_without_rc_markers(tmp_path, monkeypatch):
    monkeypatch.delenv("LG_RC_SMOKE", raising=False)
    monkeypatch.setattr(sys, "argv", ["langstudyguard.exe"])
    monkeypatch.setattr(sys, "executable", str(tmp_path / "langstudyguard.exe"), raising=False)
    identity = app_environment.resolve_identity(
        manifest=_manifest("production", tmp_path),
        frozen=True,
        rc_smoke=False,
    )
    assert identity.rc_smoke is False
    assert identity.data_folder == "langstudyguard"
    assert identity.exe_basename == "langstudyguard.exe"
    assert identity.is_production is True
    assert "RC TEST DATA" not in identity.display_title()


def test_rc_install_prepare_does_not_touch_production(tmp_path, monkeypatch):
    installed = tmp_path / "Local" / "langstudyguard" / "langstudyguard.exe"
    rc = tmp_path / "dist-rc" / "langstudyguard-rc.exe"
    installed.parent.mkdir(parents=True)
    installed.write_bytes(b"production-installed")
    rc.parent.mkdir(parents=True)
    rc.write_bytes(b"rc-bytes")
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData"))
    monkeypatch.setattr(install.config, "is_frozen", lambda: True)
    monkeypatch.setattr(install.config, "installed_exe", lambda: str(installed))
    monkeypatch.setattr(sys, "executable", str(rc), raising=False)
    monkeypatch.setattr(sys, "argv", [str(rc)])
    monkeypatch.delenv("LG_RC_SMOKE", raising=False)
    seeds = {"n": 0}

    def seed():
        seeds["n"] += 1

    monkeypatch.setattr(install, "seed_vocab", seed)
    monkeypatch.setattr(
        install,
        "register_startup",
        lambda _p: (_ for _ in ()).throw(AssertionError("startup")),
    )

    assert install.is_release_candidate_smoke() is True
    assert install.prepare() is True
    assert installed.read_bytes() == b"production-installed"
    assert seeds["n"] == 1


def test_rc_allows_production_backend_host_for_login(tmp_path):
    identity = app_environment.resolve_identity(
        manifest=_manifest("production", tmp_path),
        frozen=True,
        rc_smoke=True,
    )
    assert identity.network_writes_allowed is True
    assert (
        app_environment.validate_backend_for_identity(
            identity, "https://account.langstudyguard.com"
        )
        is None
    )
