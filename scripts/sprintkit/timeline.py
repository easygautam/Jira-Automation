"""Step 5 — aggregate Jira tasks into per-epic team plans and execution stages.

Calendar dates are intentionally not produced here (the sprint-window date rule
is deferred); each epic carries effort, leave, resources, calc-days, and the
mapped task keys per platform stage and per team member.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from sprintkit.jira_model import (
    assignee_name,
    build_index,
    epic_summary,
    get_field,
    is_bug_issue,
    is_epic_issue,
    is_task_or_subtask,
    issue_type_name,
    resolve_epic_key,
    sort_epic_keys,
    task_has_subtasks,
)
from sprintkit.config import DEFAULT_SIDE_DISPLAY, resolve_side_display_map
from sprintkit.stages import (
    DEFAULT_EXECUTION_STAGES,
    PLATFORM_KEYS,
    PLATFORM_SIDE,
    STAGE_BUG_FIXES,
    STAGE_DEVELOPMENT,
    STAGE_QA_TEST_PLANNING,
    STAGE_STAGE_FINAL_TESTING,
    STAGE_STAGE_TESTING,
    TEAM_PRODUCT_DESIGN,
    classify_issue,
)
from sprintkit.teams import TEAM_OTHER

TEAM_PLAN_SIDES = (
    "Backend",
    "Data Engineering",
    "DevOps",
    "Web",
    "Mobile",
    "Product + Design",
    "QA",
    "Other",
)

_WORK_MEMBER_STAGES = frozenset(
    {"Development", "Tech Solutioning", STAGE_STAGE_TESTING, STAGE_QA_TEST_PLANNING}
)


def side_display(team: str, side_display_map: dict[str, str] | None = None) -> str:
    """Map internal team key to Teams plan row label; defaults never collapse to Other."""
    merged = {**DEFAULT_SIDE_DISPLAY, **(side_display_map or {})}
    if team in (TEAM_OTHER, "unknown"):
        return merged.get("other") or merged.get("unknown", "Other")
    return merged.get(team, merged.get("other", "Other"))


def member_side_for_classification(
    classification: dict[str, Any],
    side_display_map: dict[str, str],
) -> str:
    """Teams plan row for a classified issue (Other only when segment mapping failed)."""
    kind = classification.get("kind")
    if kind == "unmapped":
        return side_display(TEAM_OTHER, side_display_map)
    if kind == "additional_effort":
        return side_display(classification.get("team") or "qa", side_display_map)
    if kind == "leave":
        return side_display(classification.get("team") or TEAM_OTHER, side_display_map)
    work_team = classification.get("team") or classification.get("platform")
    if work_team == "qa":
        return side_display("qa", side_display_map)
    if work_team == TEAM_PRODUCT_DESIGN:
        return side_display(TEAM_PRODUCT_DESIGN, side_display_map)
    return side_display(work_team or TEAM_OTHER, side_display_map)


_ADDITIONAL_EFFORT_TEAMS = frozenset(
    {
        "backend",
        "frontend",
        "mobile",
        "qa",
        "data_engineering",
        "devops",
        TEAM_PRODUCT_DESIGN,
    }
)


def additional_effort_team_side(
    classification: dict[str, Any],
    side_display_map: dict[str, str],
) -> str:
    """Display team for Additional efforts table (inferred team when known)."""
    team = classification.get("team")
    if team in _ADDITIONAL_EFFORT_TEAMS:
        return side_display(team, side_display_map)
    return side_display(TEAM_OTHER, side_display_map)


def check_timeline_team_consistency(timeline: list[dict[str, Any]]) -> list[str]:
    """Safety net: Backend/Web/Mobile stage effort with dev work under Other."""
    warnings: list[str] = []
    for epic in timeline:
        epic_key = epic.get("epicKey", "")
        other_members = (epic.get("membersBySide") or {}).get("Other") or []
        if not other_members:
            continue
        dev_keys: set[str] = set()
        for member in other_members:
            tasks = member.get("tasks") or []
            if tasks and not all(t == "(unmapped)" for t in tasks):
                if any(t in _WORK_MEMBER_STAGES for t in tasks):
                    dev_keys.update(member.get("issueKeys") or [])
        if not dev_keys:
            continue
        for platform, side_label in PLATFORM_SIDE.items():
            block = (epic.get("executionStages") or {}).get(platform) or {}
            if not block.get("hasWork"):
                continue
            summary = (epic.get("teamSummary") or {}).get(side_label) or {}
            if (summary.get("taskCount") or 0) > 0 and not (summary.get("members") or []):
                warnings.append(
                    f"{epic_key}: {side_label} execution stages have effort but "
                    f"assignees with mapped dev/QA work appear under Other — "
                    f"check config loading."
                )
                break
    return warnings


def stage_max_days(bucket: dict[str, Any], hours_per_day: float) -> float | None:
    """Stage duration = max person-days across assignees; synthetic stages use aggregate."""
    member_hours = bucket.get("memberHours") or {}
    if member_hours:
        days = [round(h / hours_per_day, 2) for h in member_hours.values() if h > 0]
        if days:
            return max(days)
    resource_count = len(bucket["resources"])
    resources = float(resource_count) if resource_count else 0.0
    if resources <= 0 and bucket["effortsHours"] > 0:
        resources = 1.0
    return calc_days(
        bucket["effortsHours"],
        bucket["plannedLeaveHours"],
        bucket["unplannedDelayHours"],
        resources,
        hours_per_day,
    )


def calc_days(
    efforts: float,
    planned_leave: float,
    unplanned: float,
    resources: float,
    hours_per_day: float,
) -> float | None:
    """Person-days as a decimal: total hours / (resources × hours per day)."""
    if resources <= 0:
        return None
    total = efforts + planned_leave + unplanned
    if total <= 0:
        return None
    return round(total / (resources * hours_per_day), 2)


def format_calc_days(value: float | int | None) -> str:
    """Render calc days for tables (e.g. 0.5, 4.33, 2)."""
    if value is None:
        return "—"
    rounded = round(float(value), 2)
    if rounded == int(rounded):
        return str(int(rounded))
    return f"{rounded:.2f}".rstrip("0").rstrip(".")


def bump_member(
    member_stats: dict[tuple[str, str], dict[str, Any]],
    side: str,
    member: str,
    *,
    efforts: float = 0.0,
    planned: float = 0.0,
    unplanned: float = 0.0,
    issue_key: str | None = None,
    stage_name: str | None = None,
) -> None:
    key = (side, member)
    if key not in member_stats:
        member_stats[key] = {
            "effortsHours": 0.0,
            "plannedLeaveHours": 0.0,
            "unplannedDelayHours": 0.0,
            "issueKeys": [],
            "canonicalTasks": set(),
        }
    row = member_stats[key]
    row["effortsHours"] += efforts
    row["plannedLeaveHours"] += planned
    row["unplannedDelayHours"] += unplanned
    if issue_key:
        row["issueKeys"].append(issue_key)
    if stage_name:
        row["canonicalTasks"].add(stage_name)


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


def _empty_stage_bucket() -> dict[str, Any]:
    return {
        "effortsHours": 0.0,
        "plannedLeaveHours": 0.0,
        "unplannedDelayHours": 0.0,
        "resources": set(),
        "issueKeys": [],
        "memberHours": {},
        "source": None,
    }


def _init_platform_buckets(stage_names: list[str]) -> dict[str, dict[str, Any]]:
    return {name: _empty_stage_bucket() for name in stage_names}


def _apply_synthetic_buffers(
    platform_buckets: dict[str, dict[str, dict[str, Any]]],
    buffers: dict[str, Any],
) -> None:
    bug_pct = float(buffers.get("bugFixesPercentOfDevelopment", 0.10))
    final_pct = float(buffers.get("stageFinalTestingPercentOfStageTesting", 0.10))
    for platform in PLATFORM_KEYS:
        buckets = platform_buckets.get(platform) or {}
        dev = buckets.get(STAGE_DEVELOPMENT, _empty_stage_bucket())
        stage = buckets.get(STAGE_STAGE_TESTING, _empty_stage_bucket())
        dev_h = dev["effortsHours"]
        stage_h = stage["effortsHours"]
        if STAGE_BUG_FIXES in buckets and dev_h > 0:
            b = buckets[STAGE_BUG_FIXES]
            b["effortsHours"] = round(dev_h * bug_pct, 1)
            b["source"] = "synthetic"
        if STAGE_STAGE_FINAL_TESTING in buckets and stage_h > 0:
            f = buckets[STAGE_STAGE_FINAL_TESTING]
            f["effortsHours"] = round(stage_h * final_pct, 1)
            f["source"] = "synthetic"


def _stage_to_row(
    stage_name: str,
    bucket: dict[str, Any],
    hours_per_day: float,
) -> dict[str, Any]:
    resource_count = len(bucket["resources"])
    resources = float(resource_count) if resource_count else 0.0
    # Synthetic buffers (e.g. Bug fixes) have effort but no assignees — assume 1 resource.
    if resources <= 0 and bucket["effortsHours"] > 0:
        resources = 1.0
    calc = stage_max_days(bucket, hours_per_day)
    return {
        "stage": stage_name,
        "source": bucket.get("source") or ("jira" if bucket["issueKeys"] else None),
        "resources": resources if resources > 0 else None,
        "effortsHours": round(bucket["effortsHours"], 1) if bucket["effortsHours"] else None,
        "plannedLeaveHours": round(bucket["plannedLeaveHours"], 1),
        "unplannedDelayHours": round(bucket["unplannedDelayHours"], 1),
        "calculatedDays": calc,
        "issueKeys": list(bucket["issueKeys"]),
    }


def _build_platform_block(
    platform: str,
    stage_order: list[str],
    buckets: dict[str, dict[str, Any]],
    hours_per_day: float,
) -> dict[str, Any]:
    stages_out = [
        _stage_to_row(name, buckets.get(name, _empty_stage_bucket()), hours_per_day)
        for name in stage_order
    ]
    has_work = any(b["issueKeys"] for b in buckets.values())
    return {
        "platform": platform,
        "side": PLATFORM_SIDE[platform],
        "hasWork": has_work,
        "stages": stages_out,
    }


def _stage_task_keys(stage_rows: list[dict[str, Any]]) -> set[str]:
    keys: set[str] = set()
    for row in stage_rows:
        for k in row.get("issueKeys") or []:
            keys.add(k)
    return keys


def build_timeline_breakdown(
    issues: list[dict[str, Any]],
    schedule: dict[str, Any],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    timeline_cfg = config.get("timeline") or {}
    teams_cfg = config.get("teams") or {}
    hours_per_day = float(timeline_cfg.get("hoursPerDay", 6))
    side_display_map = resolve_side_display_map(config)
    execution_stages = timeline_cfg.get("executionStages") or DEFAULT_EXECUTION_STAGES
    buffers = timeline_cfg.get("effortBuffers") or {}

    index = {i["key"]: i for i in issues if i.get("key")}
    scheduled_keys = {r["key"] for r in schedule.get("scheduled", [])}

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

        platform_buckets: dict[str, dict[str, dict[str, Any]]] = {
            p: _init_platform_buckets(execution_stages.get(p, DEFAULT_EXECUTION_STAGES[p]))
            for p in PLATFORM_KEYS
        }
        leave_by_side: dict[str, dict[str, float]] = defaultdict(
            lambda: {"planned": 0.0, "unplanned": 0.0}
        )
        member_stats: dict[tuple[str, str], dict[str, Any]] = {}
        unmapped: list[dict[str, Any]] = []

        epic_index = build_index(epic_issues)

        for issue in epic_issues:
            if is_epic_issue(issue):
                continue
            if is_bug_issue(issue):
                continue
            if not is_task_or_subtask(issue):
                continue
            key = issue.get("key")
            if (
                key
                and issue_type_name(issue) == "task"
                and task_has_subtasks(key, epic_index)
            ):
                continue
            est_h = int(get_field(issue, "timeoriginalestimate") or 0) / 3600.0
            classification = classify_issue(
                issue, timeline_cfg, teams_cfg, config, epic_issues=epic_issues
            )
            member = assignee_name(issue)

            if classification["kind"] == "leave":
                side = member_side_for_classification(classification, side_display_map)
                leave_by_side[side][classification["leaveType"]] += est_h
                planned = est_h if classification["leaveType"] == "planned" else 0.0
                unplanned = est_h if classification["leaveType"] == "unplanned" else 0.0
                bump_member(
                    member_stats,
                    side,
                    member,
                    planned=planned,
                    unplanned=unplanned,
                    issue_key=key,
                )
                continue

            if classification["kind"] in ("unmapped", "additional_effort"):
                if est_h > 0 or key in scheduled_keys:
                    is_additional = classification["kind"] == "additional_effort"
                    if not is_additional:
                        side = member_side_for_classification(
                            classification, side_display_map
                        )
                        bump_member(
                            member_stats,
                            side,
                            member,
                            efforts=est_h,
                            issue_key=key,
                            stage_name="(unmapped)",
                        )
                    unmapped.append(
                        {
                            "key": key,
                            "summary": (get_field(issue, "summary") or "")[:80],
                            "effortsHours": est_h,
                            "assignee": member,
                            "team": additional_effort_team_side(
                                classification, side_display_map
                            ),
                            "additionalEffort": is_additional,
                        }
                    )
                continue

            platform = classification["platform"]
            stage_name = classification["stage"]
            if not platform or not stage_name:
                continue

            bucket_map = platform_buckets[platform]
            if stage_name not in bucket_map:
                bucket_map[stage_name] = _empty_stage_bucket()

            b = bucket_map[stage_name]
            member_side = member_side_for_classification(classification, side_display_map)

            b["effortsHours"] += est_h
            if b.get("source") != "synthetic":
                b["source"] = "jira"
            assignee = get_field(issue, "assignee")
            if assignee:
                aid = assignee.get("displayName") or assignee.get("accountId")
                if aid:
                    b["resources"].add(aid)
            b["issueKeys"].append(key)
            member_hours = b.setdefault("memberHours", {})
            member_hours[member] = member_hours.get(member, 0.0) + est_h
            bump_member(
                member_stats,
                member_side,
                member,
                efforts=est_h,
                issue_key=key,
                stage_name=stage_name,
            )

        _apply_synthetic_buffers(platform_buckets, buffers)

        for side_name, amounts in leave_by_side.items():
            plat = next((p for p, s in PLATFORM_SIDE.items() if s == side_name), None)
            target_buckets = platform_buckets.get(plat or "") if plat else None
            if not target_buckets:
                continue
            side_rows = [
                n
                for n, b in target_buckets.items()
                if b["effortsHours"] > 0 and n not in (STAGE_BUG_FIXES, STAGE_STAGE_FINAL_TESTING)
            ]
            if not side_rows:
                side_rows = [n for n, b in target_buckets.items() if b["effortsHours"] > 0]
            if not side_rows:
                continue
            target = max(side_rows, key=lambda n: target_buckets[n]["effortsHours"])
            target_buckets[target]["plannedLeaveHours"] += amounts["planned"]
            target_buckets[target]["unplannedDelayHours"] += amounts["unplanned"]

        execution_out: dict[str, Any] = {}
        for platform in PLATFORM_KEYS:
            order = execution_stages.get(platform, DEFAULT_EXECUTION_STAGES[platform])
            execution_out[platform] = _build_platform_block(
                platform, order, platform_buckets[platform], hours_per_day
            )

        members_by_side = build_members_by_side(member_stats, hours_per_day)
        team_summary: dict[str, Any] = {}
        for side in TEAM_PLAN_SIDES:
            members = members_by_side.get(side, [])
            plat_key = next((p for p, s in PLATFORM_SIDE.items() if s == side), None)
            stage_rows = (
                execution_out[plat_key]["stages"] if plat_key and plat_key in execution_out else []
            )
            if not stage_rows and not members:
                continue
            peak = max((r.get("resources") or 0) for r in stage_rows) if stage_rows else 0
            if members:
                peak = max(peak, float(len(members)))
            total_effort = sum(m.get("effortsHours") or 0 for m in members)
            task_count = sum(m.get("issueCount", 0) for m in members)
            if not total_effort and stage_rows:
                total_effort = sum(r.get("effortsHours") or 0 for r in stage_rows)
                task_count = len(_stage_task_keys(stage_rows))
            total_leave = sum(m.get("plannedLeaveHours") or 0 for m in members)
            total_delay = sum(m.get("unplannedDelayHours") or 0 for m in members)
            team_summary[side] = {
                "peakResources": peak if peak else None,
                "totalEffortHours": round(total_effort, 1) or None,
                "totalLeaveHours": round(total_leave, 1) if total_leave else None,
                "totalDelayHours": round(total_delay, 1) if total_delay else None,
                "taskCount": task_count,
                "members": members,
            }

        results.append(
            {
                "epicKey": epic_key,
                "prdName": epic_summary(epic_key, issues, index),
                "executionStages": execution_out,
                "teamSummary": team_summary,
                "membersBySide": members_by_side,
                "unmapped": unmapped,
            }
        )

    return results
