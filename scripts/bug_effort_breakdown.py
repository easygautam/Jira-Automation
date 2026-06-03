#!/usr/bin/env python3
"""Aggregate Bug issue effort per epic and member."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from timeline_breakdown import (
    assignee_name,
    epic_summary,
    get_field,
    is_bug_issue,
    is_epic_issue,
    load_config,
    resolve_epic_key,
    side_display,
)
from jira_teams import team_from_issue


def build_bug_effort_breakdown(
    issues: list[dict[str, Any]],
    schedule: dict[str, Any],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    teams_cfg = config.get("teams") or {}
    side_display_map = (config.get("timeline") or {}).get("sideDisplay") or {}

    index = {i["key"]: i for i in issues if i.get("key")}
    scheduled_by_key = {r["key"]: r for r in schedule.get("scheduled", [])}

    epic_keys: set[str] = set()
    for issue in issues:
        if is_epic_issue(issue):
            epic_keys.add(issue["key"])
        ek = resolve_epic_key(issue, index)
        if ek:
            epic_keys.add(ek)

    results: list[dict[str, Any]] = []

    for epic_key in sorted(epic_keys):
        epic_bugs = [
            i
            for i in issues
            if is_bug_issue(i)
            and (i.get("key") == epic_key or resolve_epic_key(i, index) == epic_key)
        ]
        if not epic_bugs:
            continue

        member_rows: dict[str, dict[str, Any]] = {}

        for issue in epic_bugs:
            key = issue.get("key")
            est_h = int(get_field(issue, "timeoriginalestimate") or 0) / 3600.0
            member = assignee_name(issue)
            team = team_from_issue(issue, teams_cfg, config)
            side = side_display(team, side_display_map)
            sch = scheduled_by_key.get(key)
            if member not in member_rows:
                member_rows[member] = {
                    "member": member,
                    "effortsHours": 0.0,
                    "issues": [],
                    "sides": set(),
                }
            row = member_rows[member]
            row["effortsHours"] += est_h
            row["sides"].add(side)
            row["issues"].append(
                {
                    "key": key,
                    "summary": (get_field(issue, "summary") or "")[:100],
                    "side": side,
                    "effortsHours": round(est_h, 1) if est_h else None,
                    "start": sch["startDate"] if sch else None,
                    "end": sch["dueDate"] if sch else None,
                    "status": (get_field(issue, "status") or {}).get("name"),
                }
            )

        members = sorted(
            member_rows.values(),
            key=lambda m: (m["effortsHours"], m["member"]),
            reverse=True,
        )
        for m in members:
            m["effortsHours"] = round(m["effortsHours"], 1) if m["effortsHours"] else None
            m["issueCount"] = len(m["issues"])
            sides = m.pop("sides", set())
            m["sides"] = sorted(sides)
            m["side"] = ", ".join(m["sides"]) if sides else "Other"

        by_side: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"totalEffortHours": 0.0, "members": []}
        )
        for m in members:
            side = m["side"]
            by_side[side]["totalEffortHours"] += m.get("effortsHours") or 0
            by_side[side]["members"].append(m["member"])
        for side, data in by_side.items():
            data["totalEffortHours"] = round(data["totalEffortHours"], 1) or None
            data["memberCount"] = len(data["members"])

        total = round(sum(m.get("effortsHours") or 0 for m in members), 1)

        results.append(
            {
                "epicKey": epic_key,
                "prdName": epic_summary(epic_key, issues, index),
                "totalBugHours": total or None,
                "bugCount": len(epic_bugs),
                "members": members,
                "bySide": dict(by_side),
            }
        )

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Build bug effort breakdown JSON")
    parser.add_argument("--config", default=".cursor/config/em-config.yaml")
    parser.add_argument("--issues", required=True)
    parser.add_argument("--schedule", required=True)
    parser.add_argument("--output", help="Write JSON path")
    args = parser.parse_args()

    config = load_config(Path(args.config))
    payload = json.loads(Path(args.issues).read_text(encoding="utf-8"))
    issues = payload if isinstance(payload, list) else payload.get("issues", payload)
    schedule = json.loads(Path(args.schedule).read_text(encoding="utf-8"))

    result = build_bug_effort_breakdown(issues, schedule, config)
    out = json.dumps(result, indent=2)
    if args.output:
        Path(args.output).write_text(out + "\n", encoding="utf-8")
    else:
        sys.stdout.write(out + "\n")


if __name__ == "__main__":
    main()
