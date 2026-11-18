"""Monitoring report-line template tests (offline, no notifier wiring)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from offbox_support import ROOT

MODULE_PATH = ROOT / "deploy" / "hetzner" / "offbox_report_lines.py"


def _load():
    spec = importlib.util.spec_from_file_location("offbox_report_lines", MODULE_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _write_state(directory: Path, name: str, payload: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(json.dumps(payload), encoding="utf-8")


def test_absent_state_is_not_configured(tmp_path: Path) -> None:
    mod = _load()
    lines = mod.render_lines(str(tmp_path / "missing"))
    assert lines[0] == mod.DRIVE_NOT_CONFIGURED
    assert lines[1] == mod.LAST_ATTEMPT_ABSENT
    assert lines[2] == mod.RESTORE_NOT_RUN
    assert lines[3] == mod.CLOUD_SYNC_OFF


def test_fake_verified_does_not_claim_production(tmp_path: Path) -> None:
    mod = _load()
    attempt = tmp_path / "attempts"
    _write_state(
        attempt,
        "01-state.json",
        {
            "state": "VERIFIED",
            "transport": "fake",
            "download_verified": True,
            "detail": "downloaded-sha256",
            "drive_file_id": "fakefile001",
            "restore_drill": False,
        },
    )
    lines = mod.render_lines(str(attempt))
    assert lines[0] == mod.DRIVE_NOT_CONFIGURED
    assert "Off-box last attempt: VERIFIED" in lines[1]


def test_production_eligible_https_verified(tmp_path: Path) -> None:
    mod = _load()
    attempt = tmp_path / "attempts"
    _write_state(
        attempt,
        "02-state.json",
        {
            "state": "VERIFIED",
            "transport": "https",
            "download_verified": True,
            "detail": "downloaded-sha256",
            "drive_file_id": "abc123",
            "restore_drill": True,
        },
    )
    lines = mod.render_lines(str(attempt))
    assert lines[0] == mod.DRIVE_VERIFIED
    assert lines[2] == "Off-box restore drill: RECORDED"


def test_failed_https_maps_to_failed(tmp_path: Path) -> None:
    mod = _load()
    attempt = tmp_path / "attempts"
    _write_state(
        attempt,
        "03-state.json",
        {
            "state": "FAILED",
            "transport": "https",
            "download_verified": False,
            "detail": "upload-failed",
            "drive_file_id": "",
            "restore_drill": False,
        },
    )
    lines = mod.render_lines(str(attempt))
    assert lines[0] == mod.DRIVE_FAILED
