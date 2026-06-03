#!/usr/bin/env python3
"""Build per-epic timeline breakdown from Jira issues and schedule data."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

from jira_normalize import (
    epic_summary,
    get_field,
    is_bug_issue,
    is_epic_issue,
    issue_type_name,
    resolve_epic_key,
    sort_epic_keys,
)
from jira_teams import (
    TEAM_OTHER,
    mapping_rule_applies,
    qa_work_stream,
    task_from_pipe_prefix_team,
    team_from_issue,
)

# Engineering teams only — milestone rows (no side) stay in Task breakdown, not Teams plan.
TEAM_PLAN_SIDES = ("Backend", "Web", "Mobile", "QA", "Other")


def load_config(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        return yaml.safe_load(text) or {}
    return {}


def is_task_or_subtask(issue: dict[str, Any]) -> bool:
    """Timeline effort counts only Task and Sub-task issue types."""
    itype = issue_type_name(issue)
    return itype in ("task", "sub-task", "subtask")


def side_display(team: str, side_display_map: dict[str, str]) -> str:
    if team in ("other", "unknown"):
        return side_display_map.get("other") or side_display_map.get("unknown", "Other")
    return side_display_map.get(team, side_display_map.get("other", "Other"))


def canonical_side(
    ct: dict[str, Any], side_display_map: dict[str, str]
) -> str | None:
    """Team for canonical row; None = milestone (excluded from Teams plan)."""
    raw = ct.get("side")
    if raw is None or raw == "" or str(raw).lower() == "release":
        return None
    if raw in TEAM_PLAN_SIDES:
        return raw
    return side_display(str(raw).lower(), side_display_map)


def assignee_name(issue: dict[str, Any]) -> str:
    assignee = get_field(issue, "assignee")
    if not assignee:
        return "Unassigned"
    return assignee.get("displayName") or assignee.get("accountId") or "Unassigned"


def bump_member(
    member_stats: dict[tuple[str, str], dict[str, Any]],
    side: str,
    member: str,
    *,
    efforts: float = 0.0,
    planned: float = 0.0,
    unplanned: float = 0.0,
    start: str | None = None,
    end: str | None = None,
    issue_key: str | None = None,
    task_name: str | None = None,
) -> None:
    key = (side, member)
    if key not in member_stats:
        member_stats[key] = {
            "effortsHours": 0.0,
            "plannedLeaveHours": 0.0,
            "unplannedDelayHours": 0.0,
            "starts": [],
            "ends": [],
            "issueKeys": [],
            "canonicalTasks": set(),
        }
    row = member_stats[key]
    row["effortsHours"] += efforts
    row["plannedLeaveHours"] += planned
    row["unplannedDelayHours"] += unplanned
    if start:
        row["starts"].append(start)
    if end:
        row["ends"].append(end)
    if issue_key:
        row["issueKeys"].append(issue_key)
    if task_name:
        row["canonicalTasks"].add(task_name)


def build_members_by_side(
    member_stats: dict[tuple[str, str], dict[str, Any]],
    hours_per_day: float,
) -> dict[str, list[dict[str, Any]]]:
    by_side: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (side, member), data in member_stats.items():
        if (
            data["effortsHours"] <= 0
            and data["plannedLeaveHours"] <= 0
            and data["unplannedDelayHours"] <= 0
            and not data["issueKeys"]
        ):
            continue
        start = min(data["starts"]) if data["starts"] else None
        end = max(data["ends"]) if data["ends"] else None
        calc = calc_days(
            data["effortsHours"],
            data["plannedLeaveHours"],
            data["unplannedDelayHours"],
            1.0,
            hours_per_day,
        )
        by_side[side].append(
            {
                "member": member,
                "effortsHours": round(data["effortsHours"], 1) or None,
                "plannedLeaveHours": round(data["plannedLeaveHours"], 1),
                "unplannedDelayHours": round(data["unplannedDelayHours"], 1),
                "start": start,
                "end": end,
                "calculatedDays": calc,
                "issueCount": len(data["issueKeys"]),
                "issueKeys": data["issueKeys"],
                "tasks": sorted(data["canonicalTasks"]),
            }
        )
    for side in by_side:
        by_side[side].sort(
            key=lambda m: (m.get("effortsHours") or 0, m.get("member", "")),
            reverse=True,
        )
    return dict(by_side)


def calc_days(
    efforts: float,
    planned_leave: float,
    unplanned: float,
    resources: float,
    hours_per_day: float,
) -> int | None:
    if resources <= 0:
        return None
    total = efforts + planned_leave + unplanned
    if total <= 0:
        return None
    return math.ceil(total / (resources * hours_per_day))


def resolve_leave_team(
    issue: dict[str, Any],
    epic_issues: list[dict[str, Any]],
    teams_cfg: dict[str, list[str]],
    config: dict[str, Any] | None,
) -> str:
    """Leave | * titles use assignee's delivery team from other work on the same epic."""
    team = team_from_issue(issue, teams_cfg, config)
    if team != TEAM_OTHER:
        return team
    member = assignee_name(issue)
    if member == "Unassigned":
        return team
    for other in epic_issues:
        if other.get("key") == issue.get("key"):
            continue
        if is_bug_issue(other) or not is_task_or_subtask(other):
            continue
        if assignee_name(other) != member:
            continue
        other_team = team_from_issue(other, teams_cfg, config)
        if other_team != TEAM_OTHER:
            return other_team
    return team


def classify_issue(
    issue: dict[str, Any],
    timeline_cfg: dict[str, Any],
    teams_cfg: dict[str, list[str]],
    config: dict[str, Any] | None = None,
    epic_issues: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    summary = (get_field(issue, "summary") or "").strip()
    lower = summary.lower()
    prefixes = timeline_cfg.get("leaveTaskPrefixes") or {}
    planned_p = (prefixes.get("planned") or "Leave | Planned").lower()
    unplanned_p = (prefixes.get("unplanned") or "Leave | Unplanned").lower()
    generic_p = (prefixes.get("generic") or "Leave |").lower()

    def _leave_result(leave_type: str, prefix_key: str, prefix_len: int) -> dict[str, Any]:
        team = resolve_leave_team(
            issue, epic_issues or [], teams_cfg, config
        )
        comment = summary[prefix_len:].strip(" -:")
        return {
            "kind": "leave",
            "leaveType": leave_type,
            "team": team,
            "comment": comment,
            "task": None,
        }

    if lower.startswith(planned_p):
        return _leave_result("planned", "planned", len(prefixes.get("planned") or "Leave | Planned"))
    if lower.startswith(unplanned_p):
        return _leave_result(
            "unplanned", "unplanned", len(prefixes.get("unplanned") or "Leave | Unplanned")
        )
    if lower.startswith(generic_p):
        return _leave_result("planned", "generic", len(prefixes.get("generic") or "Leave |"))

    team = team_from_issue(issue, teams_cfg, config)
    itype = issue_type_name(issue)

    if team == "qa" or itype == "test execution":
        stream = qa_work_stream(summary)
        if "pre-prod" in lower or "pre prod" in lower:
            task = (
                "QA mobile pre-prod"
                if stream == "mobile"
                else "QA web pre-prod"
            )
            return {"kind": "work", "task": task, "team": "qa", "issueKey": issue.get("key")}
        if (
            "1st iteration" in lower
            or "2nd iteration" in lower
            or "iteration" in lower
            or "test case" in lower
        ):
            task = (
                "QA mobile stage + Admin + Bug fixes"
                if stream == "mobile"
                else "QA web/Mweb stage + Admin + Bug fixes"
            )
            return {"kind": "work", "task": task, "team": "qa", "issueKey": issue.get("key")}
        return {
            "kind": "work",
            "task": "QA Test cases & planning",
            "team": "qa",
            "issueKey": issue.get("key"),
        }

    for rule in timeline_cfg.get("mappingRules") or []:
        if not mapping_rule_applies(rule, summary, team):
            continue
        if rule.get("leaveType"):
            continue
        task = rule.get("task")
        if task is None and rule.get("useTeamBugRow"):
            bug_map = {
                "backend": "BE bugs fixes",
                "frontend": "Web bug fixes",
                "mobile": "Mobile bug fixes",
            }
            if itype == "bug" or "bug" in lower:
                task = bug_map.get(team)
            if not task:
                continue
        if task:
            return {"kind": "work", "task": task, "team": team, "issueKey": issue.get("key")}

    if itype == "bug":
        bug_map = {
            "backend": "BE bugs fixes",
            "frontend": "Web bug fixes",
            "mobile": "Mobile bug fixes",
            "qa": "QA web/Mweb stage + Admin + Bug fixes",
        }
        task = bug_map.get(team)
        if task:
            return {"kind": "work", "task": task, "team": team, "issueKey": issue.get("key")}

    prefix_task = task_from_pipe_prefix_team(summary, team, timeline_cfg, itype, config)
    if prefix_task:
        return {
            "kind": "work",
            "task": prefix_task,
            "team": team,
            "issueKey": issue.get("key"),
        }

    return {"kind": "unmapped", "task": None, "team": team, "issueKey": issue.get("key")}


def build_timeline_breakdown(
    issues: list[dict[str, Any]],
    schedule: dict[str, Any],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    timeline_cfg = config.get("timeline") or {}
    teams_cfg = config.get("teams") or {}
    hours_per_day = float(timeline_cfg.get("hoursPerDay", 6))
    side_display_map = timeline_cfg.get("sideDisplay") or {}
    canonical_tasks = timeline_cfg.get("canonicalTasks") or []

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

    for epic_key in sort_epic_keys(epic_keys, index, config):
        epic_issues = [
            i
            for i in issues
            if i.get("key") == epic_key or resolve_epic_key(i, index) == epic_key
        ]
        if epic_key not in index and not epic_issues:
            continue

        buckets: dict[str, dict[str, Any]] = {}
        for ct in canonical_tasks:
            name = ct["name"]
            side = canonical_side(ct, side_display_map)
            buckets[name] = {
                "task": name,
                "team": side,
                "resources": set(),
                "effortsHours": 0.0,
                "plannedLeaveHours": 0.0,
                "unplannedDelayHours": 0.0,
                "starts": [],
                "ends": [],
                "leaveComments": [],
                "otherComments": [],
                "issueKeys": [],
            }

        leave_by_side: dict[str, dict[str, float]] = defaultdict(
            lambda: {"planned": 0.0, "unplanned": 0.0}
        )
        member_stats: dict[tuple[str, str], dict[str, Any]] = {}
        unmapped: list[dict[str, Any]] = []

        for issue in epic_issues:
            if is_epic_issue(issue):
                continue
            if is_bug_issue(issue):
                continue
            if not is_task_or_subtask(issue):
                continue
            key = issue.get("key")
            est_h = int(get_field(issue, "timeoriginalestimate") or 0) / 3600.0
            classification = classify_issue(
                issue, timeline_cfg, teams_cfg, config, epic_issues=epic_issues
            )

            member = assignee_name(issue)
            sch = scheduled_by_key.get(key)
            sch_start = sch["startDate"] if sch else None
            sch_end = sch["dueDate"] if sch else None

            if classification["kind"] == "leave":
                side = side_display(classification["team"], side_display_map)
                leave_by_side[side][classification["leaveType"]] += est_h
                planned = est_h if classification["leaveType"] == "planned" else 0.0
                unplanned = est_h if classification["leaveType"] == "unplanned" else 0.0
                bump_member(
                    member_stats,
                    side,
                    member,
                    planned=planned,
                    unplanned=unplanned,
                    start=sch_start,
                    end=sch_end,
                    issue_key=key,
                )
                if classification.get("comment"):
                    for bn in buckets:
                        if buckets[bn]["team"] == side:
                            buckets[bn]["leaveComments"].append(classification["comment"])
                continue

            if classification["kind"] == "unmapped":
                if est_h > 0 or key in scheduled_by_key:
                    side = side_display(classification["team"], side_display_map)
                    bump_member(
                        member_stats,
                        side,
                        member,
                        efforts=est_h,
                        start=sch_start,
                        end=sch_end,
                        issue_key=key,
                        task_name="(unmapped)",
                    )
                    unmapped.append(
                        {
                            "key": key,
                            "summary": (get_field(issue, "summary") or "")[:80],
                            "effortsHours": est_h,
                            "assignee": member,
                        }
                    )
                continue

            task_name = classification["task"]
            if task_name not in buckets:
                continue

            b = buckets[task_name]
            member_side = side_display(classification.get("team") or team, side_display_map)
            b["effortsHours"] += est_h
            assignee = get_field(issue, "assignee")
            if assignee:
                aid = assignee.get("displayName") or assignee.get("accountId")
                if aid:
                    b["resources"].add(aid)
            if sch:
                b["starts"].append(sch["startDate"])
                b["ends"].append(sch["dueDate"])
            b["issueKeys"].append(key)
            bump_member(
                member_stats,
                member_side,
                member,
                efforts=est_h,
                start=sch_start,
                end=sch_end,
                issue_key=key,
                task_name=task_name,
            )

        # Distribute leave hours to rows on matching side (fallback: highest-effort row on epic)
        for side_name, amounts in leave_by_side.items():
            side_rows = [
                n
                for n, b in buckets.items()
                if b["team"] == side_name and b["effortsHours"] > 0
            ]
            if not side_rows:
                side_rows = [n for n, b in buckets.items() if b["team"] == side_name]
            if not side_rows:
                side_rows = [n for n, b in buckets.items() if b["effortsHours"] > 0]
            if not side_rows:
                continue
            target = max(side_rows, key=lambda n: buckets[n]["effortsHours"])
            buckets[target]["plannedLeaveHours"] += amounts["planned"]
            buckets[target]["unplannedDelayHours"] += amounts["unplanned"]

        task_rows: list[dict[str, Any]] = []
        for ct in canonical_tasks:
            name = ct["name"]
            b = buckets[name]
            resources = float(len(b["resources"])) if b["resources"] else 0.0
            start = min(b["starts"]) if b["starts"] else None
            end = max(b["ends"]) if b["ends"] else None
            calc = calc_days(
                b["effortsHours"],
                b["plannedLeaveHours"],
                b["unplannedDelayHours"],
                resources,
                hours_per_day,
            )
            leave_c = "; ".join(dict.fromkeys(b["leaveComments"]))[:120] or None
            other_c = None
            if b["issueKeys"] and len(b["issueKeys"]) <= 3:
                other_c = ", ".join(b["issueKeys"])
            task_rows.append(
                {
                    "task": name,
                    "team": b["team"],
                    "resources": resources if resources > 0 else None,
                    "effortsHours": round(b["effortsHours"], 1) if b["effortsHours"] else None,
                    "plannedLeaveHours": round(b["plannedLeaveHours"], 1),
                    "unplannedDelayHours": round(b["unplannedDelayHours"], 1),
                    "start": start,
                    "end": end,
                    "calculatedDays": calc,
                    "calendarDays": None,
                    "leaveComment": leave_c,
                    "otherComments": other_c,
                }
            )

        dated = [r for r in task_rows if r.get("start") and r.get("end")]
        delivery_start = min(r["start"] for r in dated) if dated else None
        delivery_end = max(r["end"] for r in dated) if dated else None
        go_live_row = next((r for r in task_rows if r["task"] == "Go live date"), None)
        go_live = go_live_row.get("end") if go_live_row and go_live_row.get("end") else delivery_end

        members_by_side = build_members_by_side(member_stats, hours_per_day)

        team_summary: dict[str, Any] = {}
        for side in TEAM_PLAN_SIDES:
            members = members_by_side.get(side, [])
            rows = [r for r in task_rows if r["team"] == side]
            if not rows and not members:
                continue
            peak = max((r["resources"] or 0) for r in rows) if rows else 0
            if members:
                peak = max(peak, float(len(members)))
            total_effort = sum(m.get("effortsHours") or 0 for m in members)
            if not total_effort and rows:
                total_effort = sum(r["effortsHours"] or 0 for r in rows)
            total_leave = sum(m.get("plannedLeaveHours") or 0 for m in members)
            total_delay = sum(m.get("unplannedDelayHours") or 0 for m in members)
            team_summary[side] = {
                "peakResources": peak if peak else None,
                "totalEffortHours": round(total_effort, 1) or None,
                "totalLeaveHours": round(total_leave, 1) if total_leave else None,
                "totalDelayHours": round(total_delay, 1) if total_delay else None,
                "taskCount": sum(m.get("issueCount", 0) for m in members),
                "members": members,
            }

        calendar_days = None
        if delivery_start and delivery_end:
            try:
                d0 = date.fromisoformat(delivery_start)
                d1 = date.fromisoformat(delivery_end)
                calendar_days = (d1 - d0).days + 1
            except ValueError:
                pass

        results.append(
            {
                "epicKey": epic_key,
                "prdName": epic_summary(epic_key, issues, index),
                "hoursPerDay": hours_per_day,
                "deliveryStart": delivery_start,
                "deliveryEnd": delivery_end,
                "goLive": go_live,
                "calendarDeliveryDays": calendar_days,
                "teamSummary": team_summary,
                "membersBySide": members_by_side,
                "tasks": task_rows,
                "unmapped": unmapped,
            }
        )

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Build timeline breakdown JSON from Jira")
    parser.add_argument("--config", default=".cursor/config/em-config.yaml")
    parser.add_argument("--issues", required=True)
    parser.add_argument("--schedule", required=True)
    parser.add_argument("--engine-input", default=None, help="Deprecated; ignored")
    parser.add_argument("--output", help="Write JSON path")
    args = parser.parse_args()

    config = load_config(Path(args.config))
    issues = json.loads(Path(args.issues).read_text(encoding="utf-8"))
    if isinstance(issues, dict):
        issues = issues.get("issues", issues)
    schedule = json.loads(Path(args.schedule).read_text(encoding="utf-8"))

    result = build_timeline_breakdown(issues, schedule, config)
    out = json.dumps(result, indent=2)
    if args.output:
        Path(args.output).write_text(out + "\n", encoding="utf-8")
    else:
        sys.stdout.write(out + "\n")


if __name__ == "__main__":
    main()
