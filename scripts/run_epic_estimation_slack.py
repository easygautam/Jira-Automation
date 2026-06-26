#!/usr/bin/env python3
"""Post-fetch wrapper: epic estimation + canvas + Slack in one pipeline run."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sprintkit.cli_common import require_issues_file  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run epic estimation and Slack post after Jira fetch")
    parser.add_argument("--epic", required=True)
    parser.add_argument("--issues", default=None)
    parser.add_argument("--config", default=".cursor/config/em-config.yaml")
    parser.add_argument("--write-canvas", nargs="?", const="", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--check-slack", action="store_true")
    parser.add_argument("--tmp-dir", default="scripts/.tmp")
    args, extra = parser.parse_known_args()

    if args.check_slack:
        cmd = [
            sys.executable,
            str(Path(__file__).resolve().parent / "epic_estimation_slack.py"),
            "--check-slack",
            "--config",
            args.config,
        ]
        raise SystemExit(subprocess.call(cmd))

    epic_key = args.epic.upper()
    issues_path = args.issues or f"scripts/.tmp/epic-{epic_key}-issues.json"
    require_issues_file(issues_path)

    cmd = [
        sys.executable,
        str(Path(__file__).resolve().parent / "epic_estimation_slack.py"),
        "--epic",
        epic_key,
        "--issues",
        issues_path,
        "--config",
        args.config,
        "--write-canvas",
    ]
    if args.write_canvas is not None and args.write_canvas:
        cmd.append(args.write_canvas)
    if args.dry_run:
        cmd.append("--dry-run")
    else:
        cmd.append("--summary-only")
    if args.tmp_dir:
        cmd.extend(["--tmp-dir", args.tmp_dir])
    cmd.extend(extra)

    raise SystemExit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
