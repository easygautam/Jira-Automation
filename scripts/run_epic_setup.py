#!/usr/bin/env python3
"""Post-fetch wrapper: validate epic issues and run epic setup plan."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sprintkit.cli_common import require_issues_file  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run epic setup plan after Jira fetch"
    )
    parser.add_argument("--epic", required=True)
    parser.add_argument(
        "--issues",
        default=None,
        help="Defaults to scripts/.tmp/epic-{KEY}-issues.json",
    )
    parser.add_argument("--config", default=".cursor/config/em-config.yaml")
    parser.add_argument("--platforms", default=None)
    parser.add_argument("--no-dev-placeholders", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--create",
        action="store_true",
        help="Emit MCP create payloads for missing stage tasks",
    )
    args, extra = parser.parse_known_args()

    epic_key = args.epic.upper()
    issues_path = args.issues or f"scripts/.tmp/epic-{epic_key}-issues.json"
    require_issues_file(issues_path)

    cmd = [
        sys.executable,
        str(Path(__file__).resolve().parent / "epic_setup.py"),
        "--epic",
        epic_key,
        "--issues",
        issues_path,
        "--config",
        args.config,
    ]
    if args.platforms:
        cmd.extend(["--platforms", args.platforms])
    if args.no_dev_placeholders:
        cmd.append("--no-dev-placeholders")
    if args.json:
        cmd.append("--json")
    if args.create:
        cmd.append("--create")
    cmd.extend(extra)

    raise SystemExit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
