"""Write build_manifest.json for a Language Guard EXE channel (ADR-025)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

import app_environment  # noqa: E402
import config  # noqa: E402


def _git_sha() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(ROOT),
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip() or "unknown"
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--channel",
        required=True,
        choices=sorted(app_environment.VALID_ENVIRONMENTS),
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "build_manifest.json"),
        help="Path to write build_manifest.json",
    )
    parser.add_argument("--version", default=config.APP_VERSION)
    args = parser.parse_args()

    payload = {
        "channel": args.channel,
        "version": str(args.version).strip() or config.APP_VERSION,
        "commit_sha": _git_sha(),
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    output = Path(args.output)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output} channel={payload['channel']} sha={payload['commit_sha'][:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
