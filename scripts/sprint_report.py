#!/usr/bin/env python3
"""Single entry point for the EM sprint report.

Reads Jira issues JSON (fetched by the sprint-analyst agent) and the EM config,
then runs the whole pipeline and writes the markdown report.

Examples
--------
Full report:
    python scripts/sprint_report.py --issues scripts/.tmp/issues.json --project VP

Recalculate with a Schedule Delta vs the previous run:
    python scripts/sprint_report.py --issues scripts/.tmp/issues.json --recalc

Standup summary (chat only):
    python scripts/sprint_report.py --issues scripts/.tmp/issues.json --standup
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sprintkit.config import load_config, resolve_project_key  # noqa: E402
from sprintkit.pipeline import run_pipeline, standup_summary  # noqa: E402


def _load_issues(path: str) -> list[dict]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return payload if isinstance(payload, list) else payload.get("issues", payload)


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the EM sprint report")
    parser.add_argument("--issues", default="scripts/.tmp/issues.json")
    parser.add_argument("--config", default=".cursor/config/em-config.yaml")
    parser.add_argument("--output", default=None, help="Report path; default reports/sprint-{date}.md")
    parser.add_argument("--tmp-dir", default="scripts/.tmp", help="Where pipeline JSON snapshots are written")
    parser.add_argument(
        "--project",
        default=None,
        help="Jira project key (default: jira.projectKey from config)",
    )
    parser.add_argument("--sprint-label", default="Active Sprint")
    parser.add_argument("--jira-site-url", default=None, help="Override jira.siteUrl from config")
    parser.add_argument("--sprint-field", default=None, help="Override config fields.sprint")
    parser.add_argument("--sprint-start", default=None, help="Override sprint start YYYY-MM-DD")
    parser.add_argument("--sprint-end", default=None, help="Override sprint end YYYY-MM-DD")
    parser.add_argument("--today", default=None, help="Override today (YYYY-MM-DD) for deterministic runs")
    parser.add_argument("--prior-schedule", default=None, help="Prior schedule JSON for Schedule Delta")
    parser.add_argument(
        "--recalc",
        action="store_true",
        help="Snapshot the existing schedule.json as prior and include a Schedule Delta",
    )
    parser.add_argument(
        "--standup",
        action="store_true",
        help="Print a short standup summary to stdout (report saved only with --output)",
    )
    args = parser.parse_args()

    config = load_config(Path(args.config))
    issues = _load_issues(args.issues)
    jira_site_url = args.jira_site_url or (config.get("jira") or {}).get("siteUrl")

    tmp_dir = Path(args.tmp_dir)
    schedule_path = tmp_dir / "schedule.json"

    prior_schedule = None
    if args.prior_schedule and Path(args.prior_schedule).exists():
        prior_schedule = json.loads(Path(args.prior_schedule).read_text(encoding="utf-8"))
    elif args.recalc and schedule_path.exists():
        prior_schedule = json.loads(schedule_path.read_text(encoding="utf-8"))
        _write_json(tmp_dir / "prior-schedule.json", prior_schedule)

    try:
        project = resolve_project_key(cli=args.project, config=config)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    try:
        result = run_pipeline(
            issues,
            config,
            project=project,
            sprint_label=args.sprint_label,
            sprint_start=args.sprint_start,
            sprint_end=args.sprint_end,
            sprint_field=args.sprint_field,
            today=args.today,
            jira_site_url=jira_site_url,
            prior_schedule=prior_schedule,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    # Snapshot pipeline JSON for debugging and recalculate continuity.
    _write_json(tmp_dir / "sprint-meta.json", result.sprint_meta)
    _write_json(tmp_dir / "engine-input.json", result.engine)
    _write_json(schedule_path, result.schedule)
    _write_json(tmp_dir / "timeline-breakdown.json", result.timeline)
    _write_json(tmp_dir / "bug-effort-breakdown.json", result.bug_effort)

    if args.standup:
        sys.stdout.write(
            standup_summary(result, issues, config, jira_site_url=jira_site_url, project=project)
        )
        if args.output:
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(result.markdown, encoding="utf-8")
        return

    out_path = args.output or f"reports/sprint-{datetime.now().strftime('%Y-%m-%d')}.md"
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(result.markdown, encoding="utf-8")

    print(out_path)
    print(
        json.dumps(
            {
                "status_counts": dict(result.status_counts),
                "scheduled": len(result.schedule.get("scheduled", [])),
                "unscheduled": len(result.schedule.get("unscheduled", [])),
                "sprint": result.sprint_meta,
            }
        )
    )


if __name__ == "__main__":
    main()
