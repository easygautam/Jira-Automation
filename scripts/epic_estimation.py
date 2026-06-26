#!/usr/bin/env python3
"""Epic estimation CLI — stdout JSON only; no report file is written."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sprintkit.cli_common import (  # noqa: E402
    default_canvas_path,
    load_issues,
    resolve_config_path,
    write_json,
)
from sprintkit.config import load_config  # noqa: E402
from sprintkit.env_loader import find_repo_root  # noqa: E402
from sprintkit.epic_pipeline import result_to_json, run_epic_estimation  # noqa: E402
from sprintkit.render.canvas_tsx import write_epic_canvas  # noqa: E402
from sprintkit.render.summary import epic_estimation_summary  # noqa: E402


def _add_write_canvas_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--write-canvas",
        nargs="?",
        const="",
        default=None,
        metavar="PATH",
        help="Write Cursor canvas .tsx (default path when flag has no value)",
    )


def run_epic_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Epic estimation (stdout JSON; no report file)")
    parser.add_argument("--epic", required=True, help="Epic issue key (e.g. ABC-12345)")
    parser.add_argument("--issues", default="scripts/.tmp/issues.json")
    parser.add_argument("--config", default=".cursor/config/em-config.yaml")
    parser.add_argument("--jira-site-url", default=None)
    parser.add_argument(
        "--tmp-dir",
        default=None,
        help="Optional debug snapshot directory (not a user deliverable)",
    )
    _add_write_canvas_arg(parser)
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Print summary text to stdout instead of JSON",
    )
    args = parser.parse_args(argv)

    repo_root = find_repo_root()
    config = load_config(resolve_config_path(args.config, repo_root=repo_root))
    issues = load_issues(args.issues)
    jira_site_url = args.jira_site_url or (config.get("jira") or {}).get("siteUrl")
    epic_key = args.epic.upper()

    try:
        result = run_epic_estimation(
            issues,
            config,
            epic_key,
            jira_site_url=jira_site_url,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    canvas_path: Path | None = None
    if args.write_canvas is not None:
        canvas_path = (
            Path(args.write_canvas)
            if args.write_canvas
            else default_canvas_path(epic_key, config, repo_root=repo_root)
        )
        write_epic_canvas(result.canvas_data, canvas_path)

    summary = epic_estimation_summary(result, canvas_path=canvas_path)
    payload = result_to_json(result, summary=summary, canvas_path=str(canvas_path) if canvas_path else None)

    if args.tmp_dir:
        write_json(Path(args.tmp_dir) / f"epic-{epic_key}-timeline.json", payload["timeline"])

    if args.summary_only:
        sys.stdout.write(summary)
        return 0

    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def main() -> None:
    raise SystemExit(run_epic_cli())


if __name__ == "__main__":
    main()
