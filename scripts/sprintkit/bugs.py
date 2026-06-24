"""Bug fix effort: worklog time-spent per epic, engineering side, and member."""

from __future__ import annotations

from typing import Any

from sprintkit.jira_model import (
    assignee_name,
    epic_summary,
    is_bug_issue,
    is_epic_issue,
    resolve_epic_key,
    sort_epic_keys,
    time_spent_seconds,
)
from sprintkit.config import resolve_side_display_map
from sprintkit.teams import delivery_platform, team_from_issue
from sprintkit.timeline import side_display

BUG_EPIC_SIDE_COLUMNS = frozenset({"Backend", "Web", "Mobile", "QA", "Other"})


def bug_epic_side_label(
    team: str,
    side_display_map: dict[str, str],
    config: dict[str, Any],
) -> str:
    """Epic table column: DE/DevOps roll into Backend delivery."""
    if delivery_platform(team, config) == "backend":
        return "Backend"
    side = side_display(team, side_display_map)
    return side if side in BUG_EPIC_SIDE_COLUMNS else "Other"


def collect_sprint_epic_keys(
    issues: list[dict[str, Any]],
    schedule: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> list[str]:
    """Epic keys in sprint scope (same set as Delivery items table), Jira Rank order."""
    keys: set[str] = {i["key"] for i in issues if is_epic_issue(i)}
    for bucket in ("scheduled", "unscheduled"):
        for row in schedule.get(bucket) or []:
            ek = row.get("epicKey")
            if ek:
                keys.add(ek)
    index = {i["key"]: i for i in issues if i.get("key")}
    return sort_epic_keys(keys, index, config)


def build_bug_effort_breakdown(
    issues: list[dict[str, Any]],
    schedule: dict[str, Any],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    teams_cfg = config.get("teams") or {}
    side_display_map = resolve_side_display_map(config)

    index = {i["key"]: i for i in issues if i.get("key")}
    epic_keys = collect_sprint_epic_keys(issues, schedule, config)

    results: list[dict[str, Any]] = []

    for epic_key in epic_keys:
        epic_bugs = [
            i
            for i in issues
            if is_bug_issue(i)
            and (i.get("key") == epic_key or resolve_epic_key(i, index) == epic_key)
        ]

        member_rows: dict[str, dict[str, Any]] = {}
        side_hours: dict[str, float] = {}

        for issue in epic_bugs:
            est_h = time_spent_seconds(issue, config) / 3600.0
            member = assignee_name(issue)
            team = team_from_issue(issue, teams_cfg, config)
            side = bug_epic_side_label(team, side_display_map, config)
            side_hours[side] = side_hours.get(side, 0.0) + est_h
            if member not in member_rows:
                member_rows[member] = {"member": member, "effortsHours": 0.0, "bugCount": 0}
            row = member_rows[member]
            row["effortsHours"] += est_h
            row["bugCount"] += 1

        members: list[dict[str, Any]] = []
        side_hours_out: dict[str, float] = {}
        total = None

        if epic_bugs:
            members = sorted(
                member_rows.values(),
                key=lambda m: (m["effortsHours"], m["member"]),
                reverse=True,
            )
            for m in members:
                m["effortsHours"] = round(m["effortsHours"], 1) if m["effortsHours"] else None
            side_hours_out = {s: round(h, 1) for s, h in side_hours.items() if round(h, 1)}
            total = round(sum(side_hours.values()), 1) or None

        results.append(
            {
                "epicKey": epic_key,
                "prdName": epic_summary(epic_key, issues, index),
                "totalBugHours": total or None,
                "bugCount": len(epic_bugs),
                "members": members,
                "sideHours": side_hours_out,
            }
        )

    return results
