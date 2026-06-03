#!/usr/bin/env python3
"""Normalize Jira issue JSON into schedule_engine input."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

from jira_teams import team_from_issue

DEFAULT_PRIORITY = ["Highest", "High", "Medium", "Low", "Lowest"]
DEFAULT_BUG_ACTIVE_STATUSES = ["To Do", "In Progress", "Hold", "Deferred"]
DEFAULT_BUG_NO_WORKLOG_STATUSES = ["Not a Bug"]
SCHEDULABLE_TYPES = frozenset(
    {"task", "sub-task", "subtask", "bug", "test execution"}
)


def load_config(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        return yaml.safe_load(text) or {}
    # Minimal fallback without PyYAML
    config: dict[str, Any] = {"priorityOrder": DEFAULT_PRIORITY, "teams": {}}
    return config


def priority_rank(name: str | None, order: list[str]) -> int:
    if not name:
        return len(order) + 1
    try:
        return order.index(name) + 1
    except ValueError:
        return len(order) + 1


def issue_type_name(issue: dict[str, Any]) -> str:
    fields = issue.get("fields") or issue
    it = fields.get("issuetype") or {}
    return (it.get("name") or "").lower()


def is_epic(issue: dict[str, Any]) -> bool:
    fields = issue.get("fields") or issue
    it = fields.get("issuetype") or {}
    if (it.get("name") or "").lower() == "epic":
        return True
    return (it.get("hierarchyLevel") or 0) > 0


is_epic_issue = is_epic


def get_field(issue: dict[str, Any], name: str) -> Any:
    fields = issue.get("fields") or issue
    return fields.get(name)


def assignee_id(issue: dict[str, Any]) -> str:
    a = get_field(issue, "assignee")
    if not a:
        return "unassigned"
    return a.get("accountId") or a.get("displayName") or "unassigned"


def is_bug_issue(issue: dict[str, Any]) -> bool:
    return issue_type_name(issue) == "bug"


def estimate_seconds(issue: dict[str, Any], config: dict[str, Any] | None = None) -> int:
    """Original Estimate only (legacy name). Prefer effective_estimate_seconds."""
    fields_cfg = (config or {}).get("fields") or {}
    oe_field = fields_cfg.get("originalEstimate", "timeoriginalestimate")
    return int(get_field(issue, oe_field) or 0)


def time_spent_seconds(issue: dict[str, Any], config: dict[str, Any] | None = None) -> int:
    fields_cfg = (config or {}).get("fields") or {}
    ts_field = fields_cfg.get("timeSpent", "timespent")
    return int(get_field(issue, ts_field) or 0)


def effective_estimate_seconds(
    issue: dict[str, Any], config: dict[str, Any] | None = None
) -> int:
    """
    Task/Sub-task/Test Execution: Original Estimate only.
    Bug: time spent (worklog total) if > 0, else Original Estimate.
    """
    oe = estimate_seconds(issue, config)
    if is_bug_issue(issue):
        spent = time_spent_seconds(issue, config)
        return spent if spent > 0 else oe
    return oe


def resolve_epic_key(
    issue: dict[str, Any], index: dict[str, dict[str, Any]]
) -> str | None:
    """Return epic key for an issue by walking parent chain."""
    if is_epic(issue):
        return issue.get("key")
    epic = resolve_epic(issue, index)
    return epic.get("key") if epic else None


def jira_rank(issue: dict[str, Any] | None, config: dict[str, Any] | None = None) -> str:
    """LexoRank string from Jira Rank field (board drag-and-drop order)."""
    if not issue:
        return ""
    fields_cfg = (config or {}).get("fields") or {}
    field_id = fields_cfg.get("rank", "customfield_10019")
    return str(get_field(issue, field_id) or "")


def epic_jira_sort_key(
    epic_key: str,
    issue_by_key: dict[str, dict[str, Any]],
    config: dict[str, Any] | None = None,
) -> tuple:
    """Sort key: ranked epics first (LexoRank), unranked last, then epic key."""
    rank = jira_rank(issue_by_key.get(epic_key), config)
    return (0, rank, epic_key) if rank else (1, epic_key)


def sort_epic_keys(
    epic_keys: set[str] | list[str],
    issue_by_key: dict[str, dict[str, Any]],
    config: dict[str, Any] | None = None,
) -> list[str]:
    """Return epic keys in Jira board (Rank) order."""
    return sorted(epic_keys, key=lambda k: epic_jira_sort_key(k, issue_by_key, config))


def epic_summary(
    epic_key: str,
    issues: list[dict[str, Any]],
    index: dict[str, dict[str, Any]],
) -> str:
    epic = index.get(epic_key)
    if epic:
        return (get_field(epic, "summary") or epic_key).strip()
    for issue in issues:
        parent = get_field(issue, "parent") or {}
        if parent.get("key") == epic_key:
            pf = parent.get("fields") or {}
            return (pf.get("summary") or epic_key).strip()
    return epic_key


def jira_status_name(issue: dict[str, Any]) -> str:
    status = get_field(issue, "status") or {}
    return (status.get("name") or "").strip()


def normalize_status_name(name: str) -> str:
    return " ".join(name.lower().split())


def bug_active_statuses(config: dict[str, Any] | None = None) -> set[str]:
    dq = (config or {}).get("dataQuality") or {}
    raw = dq.get("bugActiveStatuses") or DEFAULT_BUG_ACTIVE_STATUSES
    return {normalize_status_name(s) for s in raw}


def is_bug_active_status(issue: dict[str, Any], config: dict[str, Any] | None = None) -> bool:
    if not is_bug_issue(issue):
        return False
    return normalize_status_name(jira_status_name(issue)) in bug_active_statuses(config)


def bug_no_worklog_statuses(config: dict[str, Any] | None = None) -> set[str]:
    """Bug statuses where worklog time is not expected (e.g. rejected as not a bug)."""
    dq = (config or {}).get("dataQuality") or {}
    raw = dq.get("bugNoWorklogStatuses") or DEFAULT_BUG_NO_WORKLOG_STATUSES
    return {normalize_status_name(s) for s in raw}


def is_bug_no_worklog_status(issue: dict[str, Any], config: dict[str, Any] | None = None) -> bool:
    if not is_bug_issue(issue):
        return False
    return normalize_status_name(jira_status_name(issue)) in bug_no_worklog_statuses(config)


def bug_missing_logged_time(issue: dict[str, Any], config: dict[str, Any] | None = None) -> bool:
    """Bug past active workflow states with no worklog time."""
    return (
        is_bug_issue(issue)
        and not is_bug_active_status(issue, config)
        and not is_bug_no_worklog_status(issue, config)
        and time_spent_seconds(issue, config) <= 0
    )


def lookup_status_phase(jira_status: str, config: dict[str, Any] | None = None) -> str:
    """Map Jira status name to delivery phase; whitespace/case normalized fallback."""
    raw = (config or {}).get("statusPhaseMap") or {}
    if jira_status in raw:
        return str(raw[jira_status])
    norm = normalize_status_name(jira_status)
    for key, phase in raw.items():
        if normalize_status_name(str(key)) == norm:
            return str(phase)
    return jira_status or "Unknown"


def count_unscheduled_breakdown(
    unscheduled: list[dict[str, Any]],
    issue_by_key: dict[str, dict[str, Any]],
    config: dict[str, Any] | None = None,
) -> tuple[int, int, int]:
    """
    Return (active_bugs, tasks_missing_estimate, other_unscheduled).
    Active bugs in exempt statuses are expected to lack estimates.
    """
    active_bugs = 0
    tasks_missing = 0
    other = 0
    for row in unscheduled:
        key = row.get("key")
        if not key:
            continue
        issue = issue_by_key.get(key, {})
        if is_bug_issue(issue):
            if is_bug_active_status(issue, config) or is_bug_no_worklog_status(issue, config):
                active_bugs += 1
            else:
                other += 1
        else:
            tasks_missing += 1
    return active_bugs, tasks_missing, other


def is_blocked(issue: dict[str, Any]) -> bool:
    status = get_field(issue, "status") or {}
    name = (status.get("name") or "").lower()
    if "block" in name:
        return True
    labels = [x.lower() for x in (get_field(issue, "labels") or [])]
    return any("impediment" in l or "blocked" in l for l in labels)


def build_index(issues: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for issue in issues:
        key = issue.get("key") or issue.get("id")
        if key:
            index[str(key)] = issue
    return index


def resolve_epic(
    issue: dict[str, Any],
    index: dict[str, dict[str, Any]],
    depth: int = 0,
) -> dict[str, Any] | None:
    if depth > 10:
        return None
    if is_epic(issue):
        return issue
    parent = get_field(issue, "parent")
    if not parent:
        return None
    parent_key = parent.get("key")
    if not parent_key or parent_key not in index:
        return None
    return resolve_epic(index[parent_key], index, depth + 1)


def resolve_story(
    issue: dict[str, Any],
    index: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    t = issue_type_name(issue)
    if t == "story":
        return issue
    parent = get_field(issue, "parent")
    if not parent:
        return None
    parent_key = parent.get("key")
    if not parent_key or parent_key not in index:
        return None
    parent_issue = index[parent_key]
    if issue_type_name(parent_issue) == "story":
        return parent_issue
    return resolve_story(parent_issue, index)


def find_backend_dependency(
    epic_key: str | None,
    index: dict[str, dict[str, Any]],
    teams_cfg: dict[str, list[str]],
    self_key: str,
    config: dict[str, Any] | None = None,
) -> str | None:
    if not epic_key:
        return None
    for key, issue in index.items():
        if key == self_key:
            continue
        epic = resolve_epic(issue, index)
        if not epic or epic.get("key") != epic_key:
            continue
        if team_from_issue(issue, teams_cfg, config) != "backend":
            continue
        t = issue_type_name(issue)
        if t in ("task", "sub-task", "subtask"):
            return key
    return None


def normalize(
    issues: list[dict[str, Any]],
    config: dict[str, Any],
    sprint_start: str,
    sprint_end: str,
    today: str | None = None,
) -> dict[str, Any]:
    from datetime import date

    index = build_index(issues)
    priority_order = config.get("priorityOrder") or DEFAULT_PRIORITY
    teams_cfg = config.get("teams") or {}
    scheduling = config.get("scheduling") or {}

    items: list[dict[str, Any]] = []
    story_rank_counter = 0
    story_ranks: dict[str, int] = {}

    schedulable_types = {"task", "sub-task", "subtask", "bug", "test execution"}

    for issue in issues:
        t = issue_type_name(issue)
        if t not in schedulable_types:
            continue

        story = resolve_story(issue, index)
        epic = resolve_epic(issue, index)
        story_key = story.get("key") if story else None
        epic_key = epic.get("key") if epic else None

        if story_key and story_key not in story_ranks:
            story_rank_counter += 1
            story_ranks[story_key] = story_rank_counter

        epic_priority = None
        if epic:
            epic_priority = (get_field(epic, "priority") or {}).get("name")

        team = team_from_issue(issue, teams_cfg, config)
        dependencies: list[dict[str, Any]] = []
        if team in ("mobile", "frontend", "qa"):
            be_key = find_backend_dependency(
                epic_key, index, teams_cfg, issue.get("key", ""), config
            )
            if be_key:
                dependencies.append(
                    {
                        "type": "backend_delivery",
                        "dependsOnKey": be_key,
                        "epicKey": epic_key,
                    }
                )

        items.append(
            {
                "key": issue.get("key"),
                "storyKey": story_key,
                "epicKey": epic_key,
                "assignee": assignee_id(issue),
                "estimateSeconds": effective_estimate_seconds(issue, config),
                "epicPriorityRank": priority_rank(epic_priority, priority_order),
                "storyRank": story_ranks.get(story_key or "", 999),
                "team": team,
                "created": get_field(issue, "created") or "",
                "blocked": is_blocked(issue),
                "dependencies": dependencies,
            }
        )

    return {
        "sprintStart": sprint_start,
        "sprintEnd": sprint_end,
        "hoursPerDay": scheduling.get("hoursPerDay", 8),
        "workingDays": scheduling.get("workingDayInts", [0, 1, 2, 3, 4]),
        "today": today or date.today().isoformat(),
        "items": items,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize Jira JSON for schedule engine")
    parser.add_argument("--config", default=".cursor/config/em-config.yaml")
    parser.add_argument("--input", required=True, help="Jira issues JSON file")
    parser.add_argument("--output", help="Output path; default stdout")
    parser.add_argument("--sprint-meta", help="sprint-meta.json from sprint_meta.py")
    parser.add_argument("--sprint-start", help="Override sprint start YYYY-MM-DD")
    parser.add_argument("--sprint-end", help="Override sprint end YYYY-MM-DD")
    parser.add_argument("--today", default=None)
    args = parser.parse_args()

    config = load_config(Path(args.config))
    with open(args.input, encoding="utf-8") as f:
        payload = json.load(f)

    issues = payload if isinstance(payload, list) else payload.get("issues", payload)

    sprint_start = args.sprint_start
    sprint_end = args.sprint_end
    if args.sprint_meta:
        meta = json.loads(Path(args.sprint_meta).read_text(encoding="utf-8"))
        sprint_start = sprint_start or meta.get("sprintStart")
        sprint_end = sprint_end or meta.get("sprintEnd")

    if not sprint_start or not sprint_end:
        parser.error("Provide --sprint-meta or both --sprint-start and --sprint-end")

    result = normalize(
        issues,
        config,
        sprint_start,
        sprint_end,
        args.today,
    )

    out = json.dumps(result, indent=2)
    if args.output:
        Path(args.output).write_text(out + "\n", encoding="utf-8")
    else:
        sys.stdout.write(out + "\n")


if __name__ == "__main__":
    main()
