#!/usr/bin/env python3
"""Epic setup CLI — plan delivery-stage tasks; optional --create payloads for MCP."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sprintkit.cli_common import load_issues, resolve_config_path  # noqa: E402
from sprintkit.config import load_config, load_epic_setup_config  # noqa: E402
from sprintkit.env_loader import find_repo_root  # noqa: E402
from sprintkit.epic_setup import (  # noqa: E402
    build_setup_plan,
    format_setup_plan_summary,
)


def _parse_platforms(raw: str | None, config: dict) -> list[str]:
    if raw:
        return [p.strip() for p in raw.split(",") if p.strip()]
    setup = load_epic_setup_config(config)
    return list(setup.get("defaultPlatforms") or ["backend", "mobile"])


def run_epic_setup_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Plan delivery-stage Jira tasks for an epic (dry-run by default)"
    )
    parser.add_argument("--epic", required=True, help="Epic issue key (e.g. PPL-1546)")
    parser.add_argument(
        "--issues",
        default=None,
        help="Defaults to scripts/.tmp/epic-{KEY}-issues.json",
    )
    parser.add_argument("--config", default=".cursor/config/em-config.yaml")
    parser.add_argument(
        "--platforms",
        default=None,
        help="Comma-separated: backend,mobile,frontend (default from config)",
    )
    parser.add_argument(
        "--no-dev-placeholders",
        action="store_true",
        help="Omit Development placeholder tasks from the plan",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable plan JSON on stdout",
    )
    parser.add_argument(
        "--create",
        action="store_true",
        help="Include create payloads; agent should run MCP createJiraIssue for each",
    )
    args = parser.parse_args(argv)

    repo_root = find_repo_root()
    config = load_config(resolve_config_path(args.config, repo_root=repo_root))
    epic_key = args.epic.upper()
    issues_path = args.issues or f"scripts/.tmp/epic-{epic_key}-issues.json"
    issues = load_issues(issues_path)

    setup = load_epic_setup_config(config)
    dev_placeholders = bool(setup.get("devPlaceholders", True))
    if args.no_dev_placeholders:
        dev_placeholders = False

    try:
        plan = build_setup_plan(
            epic_key,
            issues,
            _parse_platforms(args.platforms, config),
            dev_placeholders=dev_placeholders,
            config=config,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.json:
        json.dump(plan, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    summary = format_setup_plan_summary(plan, create_mode=args.create)
    sys.stdout.write(summary)

    if args.create and plan.get("toCreate"):
        sys.stdout.write("\n--- MCP create payloads ---\n")
        for row in plan["toCreate"]:
            json.dump(row.get("createPayload") or {}, sys.stdout, indent=2)
            sys.stdout.write("\n")

    return 0


def main() -> None:
    raise SystemExit(run_epic_setup_cli())


if __name__ == "__main__":
    main()
