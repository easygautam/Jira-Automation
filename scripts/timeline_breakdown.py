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
    assessment_target,
    qa_platform_stream,
    stage_mapping_rule_applies,
    task_from_pipe_prefix_team,
    team_from_issue,
)

TEAM_PLAN_SIDES = ("Backend", "Web", "Mobile", "QA", "Other")
PLATFORM_KEYS = ("backend", "frontend", "mobile")
PLATFORM_SIDE = {"backend": "Backend", "frontend": "Web", "mobile": "Mobile"}
QA_CROSS = "qa_cross"

STAGE_TEST_PLANNING = "Test planning"
STAGE_ASSESSMENT = "Assessment"
STAGE_DEVELOPMENT = "Development"
STAGE_STAGE_TESTING = "Stage testing"
STAGE_BUG_FIXES = "Bug fixes"
STAGE_STAGE_FINAL_TESTING = "Stage final testing"
STAGE_PROD_RELEASE = "Prod release"
STAGE_PROD_FINAL_TESTING = "Prod final testing"
STAGE_PREPROD = "Pre-Prod testing"
STAGE_UAT = "UAT"
STAGE_READY = "Ready for release"
STAGE_GO_LIVE = "Go live date"

DEFAULT_EXECUTION_STAGES: dict[str, list[str]] = {
    "backend": [
        STAGE_ASSESSMENT,
        STAGE_DEVELOPMENT,
        STAGE_STAGE_TESTING,
        STAGE_BUG_FIXES,
        STAGE_STAGE_FINAL_TESTING,
        STAGE_PROD_RELEASE,
        STAGE_PROD_FINAL_TESTING,
        STAGE_GO_LIVE,
    ],
    "frontend": [
        STAGE_ASSESSMENT,
        STAGE_DEVELOPMENT,
        STAGE_STAGE_TESTING,
        STAGE_BUG_FIXES,
        STAGE_STAGE_FINAL_TESTING,
        STAGE_PREPROD,
        STAGE_UAT,
        STAGE_READY,
        STAGE_GO_LIVE,
    ],
    "mobile": [
        STAGE_ASSESSMENT,
        STAGE_DEVELOPMENT,
        STAGE_STAGE_TESTING,
        STAGE_BUG_FIXES,
        STAGE_STAGE_FINAL_TESTING,
        STAGE_PREPROD,
        STAGE_UAT,
        STAGE_READY,
        STAGE_GO_LIVE,
    ],
}


def load_config(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        return yaml.safe_load(text) or {}
    return {}


def is_task_or_subtask(issue: dict[str, Any]) -> bool:
    itype = issue_type_name(issue)
    return itype in ("task", "sub-task", "subtask")


def side_display(team: str, side_display_map: dict[str, str]) -> str:
    if team in ("other", "unknown"):
        return side_display_map.get("other") or side_display_map.get("unknown", "Other")
    return side_display_map.get(team, side_display_map.get("other", "Other"))


def platform_side(platform: str, side_display_map: dict[str, str]) -> str:
    if platform == QA_CROSS:
        return side_display_map.get("qa", "QA")
    return PLATFORM_SIDE.get(platform, side_display_map.get("other", "Other"))


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
    stage_name: str | None = None,
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
        # Start/End dates deferred (sprint-window rule to be implemented later);
        # rendered as placeholders.
        start = None
        end = None
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


def _empty_stage_bucket() -> dict[str, Any]:
    return {
        "effortsHours": 0.0,
        "plannedLeaveHours": 0.0,
        "unplannedDelayHours": 0.0,
        "resources": set(),
        "starts": [],
        "ends": [],
        "issueKeys": [],
        "source": None,
        "leaveComments": [],
    }


def _init_platform_buckets(stage_names: list[str]) -> dict[str, dict[str, Any]]:
    return {name: _empty_stage_bucket() for name in stage_names}


def _match_config_stage(
    stage_mapping: list[dict[str, Any]],
    platform: str,
    summary: str,
) -> str | None:
    for rule in stage_mapping:
        if rule.get("platform") != platform:
            continue
        if stage_mapping_rule_applies(rule, summary):
            return rule.get("stage")
    return None


def _is_stage_testing_qa(summary: str) -> bool:
    lower = summary.lower()
    if "pre-prod" in lower or "pre prod" in lower:
        return False
    if "ready for release" in lower:
        return False
    markers = (
        "1st iteration",
        "2nd iteration",
        "iteration",
        "stage testing",
        "mweb stage",
        "admin + bug",
        "api contract",
        "automation testing",
    )
    return any(m in lower for m in markers)


def _qa_scoped_release_stage(summary: str, platform: str) -> str | None:
    lower = summary.lower()
    if "ready for release" in lower:
        return STAGE_READY
    if ("uat" in lower or "uat stage" in lower) and "pre-prod" not in lower and "pre prod" not in lower:
        if "prod final" in lower or "uat prod" in lower:
            return None
        return STAGE_UAT
    if "pre-prod" in lower or "pre prod" in lower:
        return STAGE_PREPROD
    return None


def _backend_prod_stage(summary: str) -> str | None:
    lower = summary.lower()
    if any(k in lower for k in ("prod final", "production final", "uat prod")):
        return STAGE_PROD_FINAL_TESTING
    if any(k in lower for k in ("prod release", "production release")):
        if "prod final" in lower or "final testing" in lower:
            return None
        return STAGE_PROD_RELEASE
    return None


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
    stage_mapping = timeline_cfg.get("stageMapping") or []

    def _work(platform: str, stage: str, team: str) -> dict[str, Any]:
        return {
            "kind": "work",
            "platform": platform,
            "stage": stage,
            "team": team,
            "issueKey": issue.get("key"),
        }

    def _leave_result(leave_type: str, prefix_len: int) -> dict[str, Any]:
        team = resolve_leave_team(issue, epic_issues or [], teams_cfg, config)
        comment = summary[prefix_len:].strip(" -:")
        return {
            "kind": "leave",
            "leaveType": leave_type,
            "team": team,
            "comment": comment,
        }

    if lower.startswith(planned_p):
        return _leave_result("planned", len(prefixes.get("planned") or "Leave | Planned"))
    if lower.startswith(unplanned_p):
        return _leave_result(
            "unplanned", len(prefixes.get("unplanned") or "Leave | Unplanned")
        )
    if lower.startswith(generic_p):
        return _leave_result("planned", len(prefixes.get("generic") or "Leave |"))

    assess_platform = assessment_target(summary, config)
    if assess_platform == QA_CROSS:
        return _work(QA_CROSS, STAGE_TEST_PLANNING, "qa")
    if assess_platform in PLATFORM_KEYS:
        return _work(assess_platform, STAGE_ASSESSMENT, assess_platform)

    team = team_from_issue(issue, teams_cfg, config)
    itype = issue_type_name(issue)
    qa_stream = qa_platform_stream(summary)

    if team == "qa" or itype == "test execution":
        if qa_stream:
            release_stage = _qa_scoped_release_stage(summary, qa_stream)
            if release_stage and qa_stream in ("frontend", "mobile"):
                return _work(qa_stream, release_stage, "qa")
            if qa_stream == "backend":
                prod = _backend_prod_stage(summary)
                if prod:
                    return _work("backend", prod, "qa")
            if _is_stage_testing_qa(summary):
                return _work(qa_stream, STAGE_STAGE_TESTING, "qa")
            mapped = _match_config_stage(stage_mapping, qa_stream, summary)
            if mapped:
                return _work(qa_stream, mapped, "qa")
        markers_planning = (
            "test case",
            "test cases",
            "test planning",
            "test execution",
            "qa planning",
        )
        if any(m in lower for m in markers_planning) or qa_stream is None:
            return _work(QA_CROSS, STAGE_TEST_PLANNING, "qa")
        return _work(qa_stream, STAGE_STAGE_TESTING, "qa")

    if team == "backend" or qa_stream == "backend":
        prod = _backend_prod_stage(summary)
        if prod:
            return _work("backend", prod, team if team != TEAM_OTHER else "backend")
        if "go live" in lower:
            return _work("backend", STAGE_GO_LIVE, "backend")

    if team in PLATFORM_KEYS:
        mapped = _match_config_stage(stage_mapping, team, summary)
        if mapped:
            return _work(team, mapped, team)
        if team in ("frontend", "mobile"):
            release_stage = _qa_scoped_release_stage(summary, team)
            if release_stage:
                return _work(team, release_stage, team)
        if "go live" in lower:
            return _work(team, STAGE_GO_LIVE, team)

    if itype == "bug":
        return {"kind": "unmapped", "platform": None, "stage": None, "team": team}

    dev_stage = task_from_pipe_prefix_team(summary, team, timeline_cfg, itype, config)
    if dev_stage and team in PLATFORM_KEYS:
        return _work(team, dev_stage, team)

    return {"kind": "unmapped", "platform": None, "stage": None, "team": team}


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
    resources = float(len(bucket["resources"])) if bucket["resources"] else 0.0
    # Start/End dates deferred (sprint-window rule to be implemented later).
    start = None
    end = None
    calc = calc_days(
        bucket["effortsHours"],
        bucket["plannedLeaveHours"],
        bucket["unplannedDelayHours"],
        resources,
        hours_per_day,
    )
    return {
        "stage": stage_name,
        "source": bucket.get("source") or ("jira" if bucket["issueKeys"] else None),
        "resources": resources if resources > 0 else None,
        "effortsHours": round(bucket["effortsHours"], 1) if bucket["effortsHours"] else None,
        "plannedLeaveHours": round(bucket["plannedLeaveHours"], 1),
        "unplannedDelayHours": round(bucket["unplannedDelayHours"], 1),
        "start": start,
        "end": end,
        "calculatedDays": calc,
        "issueKeys": list(bucket["issueKeys"]),
    }


def _build_platform_block(
    platform: str,
    stage_order: list[str],
    buckets: dict[str, dict[str, Any]],
    hours_per_day: float,
) -> dict[str, Any]:
    stages_out: list[dict[str, Any]] = []
    dated_ends: list[str] = []
    dated_starts: list[str] = []
    go_live = None
    for name in stage_order:
        b = buckets.get(name, _empty_stage_bucket())
        row = _stage_to_row(name, b, hours_per_day)
        stages_out.append(row)
        if row.get("start"):
            dated_starts.append(row["start"])
        if row.get("end"):
            dated_ends.append(row["end"])
        if name == STAGE_GO_LIVE and row.get("end"):
            go_live = row["end"]
    delivery_start = min(dated_starts) if dated_starts else None
    delivery_end = max(dated_ends) if dated_ends else None
    if not go_live:
        go_live = delivery_end
    has_work = any(b["issueKeys"] for b in buckets.values())
    return {
        "platform": platform,
        "side": PLATFORM_SIDE[platform],
        "deliveryStart": delivery_start,
        "deliveryEnd": delivery_end,
        "goLive": go_live,
        "hasWork": has_work,
        "stages": stages_out,
    }


def build_timeline_breakdown(
    issues: list[dict[str, Any]],
    schedule: dict[str, Any],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    timeline_cfg = config.get("timeline") or {}
    teams_cfg = config.get("teams") or {}
    hours_per_day = float(timeline_cfg.get("hoursPerDay", 6))
    side_display_map = timeline_cfg.get("sideDisplay") or {}
    execution_stages = timeline_cfg.get("executionStages") or DEFAULT_EXECUTION_STAGES
    qa_stages = timeline_cfg.get("qaCrossPlatformStages") or [STAGE_TEST_PLANNING]
    buffers = timeline_cfg.get("effortBuffers") or {}

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

        platform_buckets: dict[str, dict[str, dict[str, Any]]] = {
            p: _init_platform_buckets(execution_stages.get(p, DEFAULT_EXECUTION_STAGES[p]))
            for p in PLATFORM_KEYS
        }
        qa_buckets = _init_platform_buckets(list(qa_stages))
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
                        stage_name="(unmapped)",
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

            platform = classification["platform"]
            stage_name = classification["stage"]
            if not platform or not stage_name:
                continue

            if platform == QA_CROSS:
                bucket_map = qa_buckets
            else:
                bucket_map = platform_buckets[platform]

            if stage_name not in bucket_map:
                bucket_map[stage_name] = _empty_stage_bucket()

            b = bucket_map[stage_name]
            member_side = platform_side(platform, side_display_map)
            if platform != QA_CROSS:
                member_side = side_display(classification.get("team") or platform, side_display_map)
                if classification.get("team") == "qa":
                    member_side = side_display("qa", side_display_map)

            b["effortsHours"] += est_h
            if b.get("source") != "synthetic":
                b["source"] = "jira"
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
                stage_name=stage_name,
            )

        _apply_synthetic_buffers(platform_buckets, buffers)

        for side_name, amounts in leave_by_side.items():
            plat = None
            for p, s in PLATFORM_SIDE.items():
                if s == side_name:
                    plat = p
                    break
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
        all_starts: list[str] = []
        all_ends: list[str] = []
        for platform in PLATFORM_KEYS:
            order = execution_stages.get(platform, DEFAULT_EXECUTION_STAGES[platform])
            block = _build_platform_block(
                platform, order, platform_buckets[platform], hours_per_day
            )
            execution_out[platform] = block
            if block.get("deliveryStart"):
                all_starts.append(block["deliveryStart"])
            if block.get("deliveryEnd"):
                all_ends.append(block["deliveryEnd"])

        qa_block = {
            "stages": [
                _stage_to_row(name, qa_buckets.get(name, _empty_stage_bucket()), hours_per_day)
                for name in qa_stages
            ]
        }

        legacy_tasks: list[dict[str, Any]] = []
        for platform in PLATFORM_KEYS:
            side = PLATFORM_SIDE[platform]
            for row in execution_out[platform]["stages"]:
                legacy_tasks.append(
                    {
                        "task": row["stage"],
                        "team": side,
                        "resources": row.get("resources"),
                        "effortsHours": row.get("effortsHours"),
                        "plannedLeaveHours": row.get("plannedLeaveHours"),
                        "unplannedDelayHours": row.get("unplannedDelayHours"),
                        "start": row.get("start"),
                        "end": row.get("end"),
                        "calculatedDays": row.get("calculatedDays"),
                        "calendarDays": None,
                        "leaveComment": None,
                        "otherComments": None,
                    }
                )
        for row in qa_block["stages"]:
            legacy_tasks.append(
                {
                    "task": row["stage"],
                    "team": "QA",
                    "resources": row.get("resources"),
                    "effortsHours": row.get("effortsHours"),
                    "plannedLeaveHours": row.get("plannedLeaveHours"),
                    "unplannedDelayHours": row.get("unplannedDelayHours"),
                    "start": row.get("start"),
                    "end": row.get("end"),
                    "calculatedDays": row.get("calculatedDays"),
                }
            )

        delivery_start = min(all_starts) if all_starts else None
        delivery_end = max(all_ends) if all_ends else None
        go_lives = [
            execution_out[p].get("goLive")
            for p in PLATFORM_KEYS
            if execution_out.get(p, {}).get("goLive")
        ]
        go_live = max(go_lives) if go_lives else delivery_end

        members_by_side = build_members_by_side(member_stats, hours_per_day)
        team_summary: dict[str, Any] = {}
        for side in TEAM_PLAN_SIDES:
            members = members_by_side.get(side, [])
            plat_key = next((p for p, s in PLATFORM_SIDE.items() if s == side), None)
            stage_rows = (
                execution_out[plat_key]["stages"] if plat_key and plat_key in execution_out else []
            )
            if side == "QA":
                stage_rows = qa_block["stages"]
            if not stage_rows and not members:
                continue
            peak = max((r.get("resources") or 0) for r in stage_rows) if stage_rows else 0
            if members:
                peak = max(peak, float(len(members)))
            total_effort = sum(m.get("effortsHours") or 0 for m in members)
            if not total_effort and stage_rows:
                total_effort = sum(r.get("effortsHours") or 0 for r in stage_rows)
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
                "executionStages": execution_out,
                "qaCrossPlatform": qa_block,
                "teamSummary": team_summary,
                "membersBySide": members_by_side,
                "tasks": legacy_tasks,
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
