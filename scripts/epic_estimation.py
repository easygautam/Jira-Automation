#!/usr/bin/env python3
"""Epic estimation CLI — stdout JSON only; no report file is written."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sprintkit.config import load_config  # noqa: E402
from sprintkit.epic_pipeline import result_to_json, run_epic_estimation  # noqa: E402


def _load_issues(path: str) -> list[dict]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return payload if isinstance(payload, list) else payload.get("issues", payload)


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Epic estimation (stdout JSON; no report file)")
    parser.add_argument("--epic", required=True, help="Epic issue key (e.g. VP-12345)")
    parser.add_argument("--issues", default="scripts/.tmp/issues.json")
    parser.add_argument("--config", default=".cursor/config/em-config.yaml")
    parser.add_argument("--project", default="VP")
    parser.add_argument("--jira-site-url", default=None)
    parser.add_argument(
        "--tmp-dir",
        default=None,
        help="Optional debug snapshot directory (not a user deliverable)",
    )
    args = parser.parse_args()

    config = load_config(Path(args.config))
    issues = _load_issues(args.issues)
    jira_site_url = args.jira_site_url or (config.get("jira") or {}).get("siteUrl")

    try:
        result = run_epic_estimation(
            issues,
            config,
            args.epic.upper(),
            project=args.project,
            jira_site_url=jira_site_url,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    payload = result_to_json(result)

    if args.tmp_dir:
        tmp = Path(args.tmp_dir)
        _write_json(tmp / f"epic-{args.epic.upper()}-timeline.json", payload["timeline"])

    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
