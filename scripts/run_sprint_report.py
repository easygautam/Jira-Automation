#!/usr/bin/env python3
"""Post-fetch wrapper: validate issues JSON, run sprint report, print summary."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sprintkit.cli_common import require_issues_file  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run sprint report after Jira fetch")
    parser.add_argument("--issues", default="scripts/.tmp/issues.json")
    parser.add_argument("--config", default=".cursor/config/em-config.yaml")
    parser.add_argument("--project", default=None)
    parser.add_argument("--recalc", action="store_true")
    parser.add_argument("--standup", action="store_true")
    parser.add_argument("--output", default=None)
    parser.add_argument("--tmp-dir", default="scripts/.tmp")
    args, extra = parser.parse_known_args()

    require_issues_file(args.issues)

    cmd = [
        sys.executable,
        str(Path(__file__).resolve().parent / "sprint_report.py"),
        "--issues",
        args.issues,
        "--config",
        args.config,
        "--tmp-dir",
        args.tmp_dir,
    ]
    if args.project:
        cmd.extend(["--project", args.project])
    if args.recalc:
        cmd.append("--recalc")
    if args.standup:
        cmd.append("--standup")
    elif not args.output:
        cmd.append("--summary")
    if args.output:
        cmd.extend(["--output", args.output])
    cmd.extend(extra)

    raise SystemExit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
