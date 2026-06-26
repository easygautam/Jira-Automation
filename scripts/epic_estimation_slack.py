#!/usr/bin/env python3
"""Epic estimation CLI with Slack Block Kit post."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from epic_estimation import _add_write_canvas_arg, run_epic_cli  # noqa: E402
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
from sprintkit.render.slack_blocks import build_slack_blocks  # noqa: E402
from sprintkit.render.summary import epic_estimation_summary  # noqa: E402
from sprintkit.slack_client import (  # noqa: E402
    SlackError,
    check_slack_setup,
    post_epic_estimation,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Epic estimation with optional Slack Block Kit post"
    )
    parser.add_argument("--epic", help="Epic issue key (e.g. ABC-12345)")
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
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print Block Kit JSON to stdout instead of posting to Slack",
    )
    parser.add_argument(
        "--check-slack",
        action="store_true",
        help="Verify Slack token and channel resolution without posting",
    )
    args = parser.parse_args()

    repo_root = find_repo_root()
    config_path = resolve_config_path(args.config, repo_root=repo_root)
    config = load_config(config_path)

    if args.check_slack:
        try:
            status = check_slack_setup(config, repo_root=repo_root)
        except SlackError as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(1)
        json.dump(status, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return

    if not args.epic:
        parser.error("--epic is required unless using --check-slack")

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
        sys.exit(1)

    canvas_path: Path | None = None
    if args.write_canvas is not None:
        canvas_path = (
            Path(args.write_canvas)
            if args.write_canvas
            else default_canvas_path(epic_key, config, repo_root=repo_root)
        )
        write_epic_canvas(result.canvas_data, canvas_path)

    slack_permalink: str | None = None
    slack_result: dict | None = None

    if args.dry_run:
        slack_payload = build_slack_blocks(result.canvas_data)
        summary = epic_estimation_summary(result, canvas_path=canvas_path)
        payload = result_to_json(
            result, summary=summary, canvas_path=str(canvas_path) if canvas_path else None
        )
        payload["slack"] = slack_payload
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return

    try:
        slack_result = post_epic_estimation(result.canvas_data, config)
        slack_permalink = slack_result.get("permalink")
    except SlackError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    summary = epic_estimation_summary(
        result,
        canvas_path=canvas_path,
        slack_permalink=slack_permalink,
    )
    payload = result_to_json(
        result, summary=summary, canvas_path=str(canvas_path) if canvas_path else None
    )
    payload["slack"] = slack_result

    if args.tmp_dir:
        write_json(Path(args.tmp_dir) / f"epic-{epic_key}-timeline.json", payload["timeline"])

    if args.summary_only:
        sys.stdout.write(summary)
        return

    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
