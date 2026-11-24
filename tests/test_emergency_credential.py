"""Local emergency credential. Synthetic data roots only; no screen lock."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

import app_environment
import bundle_secrets
import config
import emergency_credential
import install


class IdentityTestProtection:
    """Test double. This is not production protection."""

    name = "injected"

    def protect(self, plaintext: bytes) -> bytes:
        return b"test-v1:" + plaintext

    def unprotect(self, protected: bytes) -> bytes:
        prefix = b"test-v1:"
        if not protected.startswith(prefix):
            raise emergency_credential.CredentialUnreadable("unreadable")
        return protected[len(prefix) :]


@pytest.fixture(autouse=True)
def _protection_and_root(tmp_path, monkeypatch):
    monkeypatch.setenv("LG_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    monkeypatch.delenv("LG_RC_SMOKE", raising=False)
    emergency_credential.set_protection_for_tests(IdentityTestProtection())
    previous_token = config.ACCOUNT_TOKEN
    yield
    emergency_credential.set_protection_for_tests(None)
    config.ACCOUNT_TOKEN = previous_token


def _enroll() -> str:
    secret = emergency_credential.begin_or_resume()
    assert emergency_credential.acknowledge_current(secret) is True
    return secret


def test_generation_stores_a_protected_blob_not_the_secret():
    secret = emergency_credential.begin_or_resume()
    stored = Path(emergency_credential.credential_path()).read_text(encoding="utf-8")
    assert secret not in stored
    assert "test-v1:" not in stored
    assert emergency_credential.status() == "unacknowledged"
    assert emergency_credential.lock_allowed() is False
    other = emergency_credential.begin_or_resume()
    assert other == secret


def test_acknowledgement_and_offline_validation():
    secret = _enroll()
    assert emergency_credential.lock_allowed() is True
    assert emergency_credential.validate_offline(secret) is True
    assert emergency_credential.validate_offline("wrong-code") is False
    assert emergency_credential.validate_offline(secret) is True


def test_incorrect_acknowledgement_is_rejected():
    emergency_credential.begin_or_resume()
    assert emergency_credential.acknowledge_current("not-the-code") is False
    assert emergency_credential.status() == "unacknowledged"
    assert emergency_credential.screen_lock_enabled(["app", "--lock"]) is False


def test_missing_and_corrupt_credentials_leave_lock_off(tmp_path):
    assert emergency_credential.status() == "missing"
    assert emergency_credential.screen_lock_enabled(["app", "--lock"]) is False
    path = Path(emergency_credential.credential_path())
    path.parent.mkdir(parents=True)
    path.write_text("{not-json", encoding="utf-8")
    assert emergency_credential.status() == "unreadable"
    assert emergency_credential.lock_allowed() is False
    secret = emergency_credential.start_reenrollment(lock_active=False, replace_existing=True)
    assert emergency_credential.lock_allowed() is False
    assert emergency_credential.commit_reenrollment("wrong") is False
    assert emergency_credential.commit_reenrollment(secret) is True
    assert emergency_credential.lock_allowed() is True


def test_cancel_and_interrupted_enrollment_do_not_lock():
    secret = emergency_credential.begin_or_resume()
    emergency_credential.cancel_enrollment()
    assert emergency_credential.status() == "missing"
    assert not Path(emergency_credential.credential_path()).exists()
    again = emergency_credential.begin_or_resume()
    assert again != secret
    assert emergency_credential.screen_lock_enabled(["app", "--lock"]) is False


def test_established_credential_is_not_replaced_automatically():
    secret = _enroll()
    before = Path(emergency_credential.credential_path()).read_bytes()
    with pytest.raises(emergency_credential.CredentialEstablished):
        emergency_credential.begin_or_resume()
    assert Path(emergency_credential.credential_path()).read_bytes() == before
    pending = emergency_credential.start_reenrollment(lock_active=False, replace_existing=True)
    assert emergency_credential.validate_offline(secret) is True
    emergency_credential.cancel_reenrollment()
    assert emergency_credential.validate_offline(secret) is True
    assert emergency_credential.validate_offline(pending) is False


def test_explicit_reenrollment_commits_only_after_acknowledgement():
    secret = _enroll()
    pending = emergency_credential.start_reenrollment(lock_active=False, replace_existing=True)
    assert emergency_credential.commit_reenrollment(pending) is True
    assert emergency_credential.validate_offline(pending) is True
    assert emergency_credential.validate_offline(secret) is False


def test_recovery_is_refused_while_lock_is_active():
    _enroll()
    with pytest.raises(emergency_credential.RecoveryRefused):
        emergency_credential.reveal_outside_lock(lock_active=True)
    with pytest.raises(emergency_credential.RecoveryRefused):
        emergency_credential.start_reenrollment(lock_active=True, replace_existing=True)


def test_credential_survives_logout_and_account_switch():
    secret = _enroll()
    config.save_account("learner-a", "synthetic-token-a", user_id=4)
    config.clear_account()
    config.save_account("learner-b", "synthetic-token-b", user_id=5)
    assert emergency_credential.validate_offline(secret) is True
    settings = Path(config._settings_path()).read_text(encoding="utf-8")
    assert secret not in settings
    prefs = json.dumps(__import__("account_prefs").collect_local_account_preferences())
    assert secret not in prefs
    assert "emergency" not in prefs


def test_offline_validation_has_no_network_dependency():
    secret = _enroll()
    source = Path(emergency_credential.__file__).read_text(encoding="utf-8")
    assert "urllib" not in source
    assert "requests" not in source
    assert "socket" not in source
    assert emergency_credential.validate_offline(secret) is True


def test_upgrade_without_a_local_credential_ignores_lock():
    assert emergency_credential.status() == "missing"
    assert emergency_credential.screen_lock_enabled(["langstudyguard.exe", "--lock"]) is False
    secret = _enroll()
    assert emergency_credential.screen_lock_enabled(["langstudyguard.exe", "--lock"]) is True
    assert secret


def test_startup_registration_waits_for_acknowledgement(tmp_path, monkeypatch):
    installed = tmp_path / "Local" / "langstudyguard" / "langstudyguard.exe"
    installed.parent.mkdir(parents=True)
    installed.write_bytes(b"installed")
    monkeypatch.setattr(install.config, "is_frozen", lambda: True)
    monkeypatch.setattr(install.config, "installed_exe", lambda: str(installed))
    monkeypatch.setattr(install.config, "environment_identity", lambda: _production_identity())
    monkeypatch.setattr(install, "is_release_candidate_smoke", lambda: False)

    def allow_run(args, check=False, creationflags=0):
        return install.subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(install.subprocess, "run", allow_run)
    link = (
        tmp_path
        / "Roaming"
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
        / "langstudyguard.lnk"
    )
    assert install.register_startup_after_enrollment() is False
    assert not link.exists()
    secret = emergency_credential.begin_or_resume()
    assert install.register_startup_after_enrollment() is False
    assert not link.exists()
    assert emergency_credential.acknowledge_current(secret) is True
    assert install.register_startup_after_enrollment() is True
    assert link.is_file()
    link.write_bytes(b"existing-shortcut")
    assert install.register_startup_after_enrollment() is False
    assert link.read_bytes() == b"existing-shortcut"


def test_rc_data_root_still_fails_closed(tmp_path, monkeypatch):
    identity = app_environment.resolve_identity(
        manifest=app_environment.BuildManifest(
            channel="production",
            version="1.5.0",
            commit_sha="0" * 40,
            built_at="",
        ),
        frozen=True,
        rc_smoke=True,
    )
    monkeypatch.setattr(config, "environment_identity", lambda: identity)
    monkeypatch.delenv("LG_DATA_DIR", raising=False)
    app_environment.reset_identity_cache()
    with pytest.raises(app_environment.EnvironmentIdentityError):
        emergency_credential.credential_path()
    assert not (tmp_path / "Roaming" / "langstudyguard-rc").exists()


def test_dpapi_flags_are_current_user_only():
    assert emergency_credential.WindowsCurrentUserDpapi.FLAGS == 0x01
    assert emergency_credential.WindowsCurrentUserDpapi.FLAGS & 0x04 == 0
    emergency_credential.set_protection_for_tests(None)
    if os.name == "nt":
        protector = emergency_credential.active_protection()
        assert protector.name == emergency_credential.DPAPI_NAME
        assert protector.FLAGS & 0x04 == 0
    else:
        with pytest.raises(emergency_credential.CredentialUnavailable):
            emergency_credential.active_protection()


def test_release_configuration_has_no_emergency_password(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "EMERGENCY_PASSWORD=synthetic-not-a-real-password",
                "OPENAI_API_KEY=sk-test-not-real-1234567890",
                "ACCOUNT_TOKEN=synthetic-token",
                "ACCOUNT_SERVER_URL=https://langstudyguard.com",
            ]
        ),
        encoding="utf-8",
    )
    output = tmp_path / "bundled_secrets.json"
    assert bundle_secrets.main(["--channel", "production", "--output", str(output)]) == 0
    text = output.read_text(encoding="utf-8")
    assert json.loads(text) == {"account_server_url": "https://langstudyguard.com"}
    assert "emergency_password" not in text
    assert "synthetic-not-a-real-password" not in text
    assert "sk-test-not-real" not in text
    assert "synthetic-token" not in text
    with pytest.raises(ValueError):
        bundle_secrets.assert_release_config({"emergency_password": "synthetic"})


def _production_identity():
    return app_environment.EnvironmentIdentity(
        build_channel="production",
        runtime_environment="production",
        version="test",
        commit_sha="test",
        data_folder="langstudyguard",
        install_folder="langstudyguard",
        exe_basename="langstudyguard.exe",
        startup_link="langstudyguard.lnk",
        network_writes_allowed=True,
    )
