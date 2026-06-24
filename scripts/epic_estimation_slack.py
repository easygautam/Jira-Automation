#!/usr/bin/env python3
"""Epic estimation CLI with Slack Block Kit post."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sprintkit.config import load_config  # noqa: E402
from sprintkit.env_loader import find_repo_root  # noqa: E402
from sprintkit.epic_pipeline import result_to_json, run_epic_estimation  # noqa: E402
from sprintkit.render.slack_blocks import build_slack_blocks  # noqa: E402
from sprintkit.slack_client import (  # noqa: E402
    SlackError,
    check_slack_setup,
    post_epic_estimation,
)


def _load_issues(path: str) -> list[dict]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return payload if isinstance(payload, list) else payload.get("issues", payload)


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


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

    repo_root = find_repo_root(Path(__file__).resolve().parents[1])
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = repo_root / config_path
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

    issues = _load_issues(args.issues)
    jira_site_url = args.jira_site_url or (config.get("jira") or {}).get("siteUrl")

    try:
        result = run_epic_estimation(
            issues,
            config,
            args.epic.upper(),
            jira_site_url=jira_site_url,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    payload = result_to_json(result)

    if args.tmp_dir:
        tmp = Path(args.tmp_dir)
        _write_json(tmp / f"epic-{args.epic.upper()}-timeline.json", payload["timeline"])

    if args.dry_run:
        slack_payload = build_slack_blocks(result.canvas_data)
        json.dump({"epic": payload, "slack": slack_payload}, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return

    try:
        slack_result = post_epic_estimation(result.canvas_data, config)
    except SlackError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    payload["slack"] = slack_result
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
