"""Jira issue model: field access, hierarchy, effort, status and epic helpers."""

from __future__ import annotations

from datetime import date
from typing import Any

from sprintkit.config import (
    DEFAULT_BUG_ACTIVE_STATUSES,
    DEFAULT_BUG_NO_WORKLOG_STATUSES,
    DEFAULT_PRIORITY,
)


def get_field(issue: dict[str, Any], name: str) -> Any:
    fields = issue.get("fields") or issue
    return fields.get(name)


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


def is_task_or_subtask(issue: dict[str, Any]) -> bool:
    return issue_type_name(issue) in ("task", "sub-task", "subtask")


def is_subtask(issue: dict[str, Any]) -> bool:
    return issue_type_name(issue) in ("sub-task", "subtask")


def get_subtasks(
    parent_key: str, index: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Return sub-tasks whose parent key matches."""
    out: list[dict[str, Any]] = []
    for issue in index.values():
        parent = get_field(issue, "parent") or {}
        if parent.get("key") == parent_key and is_subtask(issue):
            out.append(issue)
    return out


def subtasks_estimate_seconds(
    parent_key: str,
    index: dict[str, dict[str, Any]],
    config: dict[str, Any] | None = None,
) -> int:
    """Sum Original Estimate on all sub-tasks under a parent task."""
    return sum(estimate_seconds(st, config) for st in get_subtasks(parent_key, index))


def task_has_subtasks(parent_key: str, index: dict[str, dict[str, Any]]) -> bool:
    return bool(get_subtasks(parent_key, index))


def is_bug_issue(issue: dict[str, Any]) -> bool:
    return issue_type_name(issue) == "bug"


def assignee_id(issue: dict[str, Any]) -> str:
    a = get_field(issue, "assignee")
    if not a:
        return "unassigned"
    return a.get("accountId") or a.get("displayName") or "unassigned"


def assignee_name(issue: dict[str, Any]) -> str:
    assignee = get_field(issue, "assignee")
    if not assignee:
        return "Unassigned"
    return assignee.get("displayName") or assignee.get("accountId") or "Unassigned"


def priority_rank(name: str | None, order: list[str]) -> int:
    if not name:
        return len(order) + 1
    try:
        return order.index(name) + 1
    except ValueError:
        return len(order) + 1


def estimate_seconds(issue: dict[str, Any], config: dict[str, Any] | None = None) -> int:
    """Original Estimate only. Prefer effective_estimate_seconds for scheduling."""
    fields_cfg = (config or {}).get("fields") or {}
    oe_field = fields_cfg.get("originalEstimate", "timeoriginalestimate")
    return int(get_field(issue, oe_field) or 0)


def time_spent_seconds(issue: dict[str, Any], config: dict[str, Any] | None = None) -> int:
    fields_cfg = (config or {}).get("fields") or {}
    ts_field = fields_cfg.get("timeSpent", "timespent")
    return int(get_field(issue, ts_field) or 0)


def jira_start_date(
    issue: dict[str, Any], config: dict[str, Any] | None = None
) -> date | None:
    """Parse Jira Start date field (ISO date string) or return None."""
    fields_cfg = (config or {}).get("fields") or {}
    field_id = fields_cfg.get("startDate", "customfield_10015")
    raw = get_field(issue, field_id)
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw)[:10])
    except (ValueError, TypeError):
        return None


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


def resolve_epic_key(
    issue: dict[str, Any], index: dict[str, dict[str, Any]]
) -> str | None:
    """Return epic key for an issue by walking the parent chain."""
    if is_epic(issue):
        return issue.get("key")
    epic = resolve_epic(issue, index)
    return epic.get("key") if epic else None


def filter_issues_for_epic(
    issues: list[dict[str, Any]], epic_key: str
) -> list[dict[str, Any]]:
    """Return epic issue and all descendants linked to the epic key."""
    index = build_index(issues)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for issue in issues:
        key = issue.get("key")
        if not key or key in seen:
            continue
        if key == epic_key or resolve_epic_key(issue, index) == epic_key:
            out.append(issue)
            seen.add(key)
    return out


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
