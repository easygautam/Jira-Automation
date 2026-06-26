"""Data-quality flags grouped by assignee (estimates, worklog, mapping gaps)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sprintkit.config import SCHEDULABLE_TYPES
from sprintkit.jira_model import (
    assignee_id,
    assignee_name,
    bug_missing_logged_time,
    build_index,
    estimate_seconds,
    get_field,
    is_bug_issue,
    issue_type_name,
    resolve_epic,
    subtasks_estimate_seconds,
)

REASON_MISSING_ESTIMATE = "Missing estimates"
REASON_MISSING_LOGGED_TIME = "Missing logged time"
REASON_PARENT_NOT_MAPPED = "Parent not mapped"
REASON_EPIC_NOT_MAPPED = "Epic not mapped"
REASON_PARENT_OUT_OF_SCOPE = "Parent not in sprint"
REASON_QA_MISSING_PLATFORM = "QA task missing platform segment"
REASON_TIMELINE_UNMAPPED = "Timeline mapping"
REASON_UNASSIGNED = "Unassigned"

REASON_SORT_ORDER = (
    REASON_MISSING_ESTIMATE,
    REASON_MISSING_LOGGED_TIME,
    REASON_PARENT_NOT_MAPPED,
    REASON_PARENT_OUT_OF_SCOPE,
    REASON_EPIC_NOT_MAPPED,
    REASON_QA_MISSING_PLATFORM,
    REASON_TIMELINE_UNMAPPED,
    REASON_UNASSIGNED,
)


def assignee_display(issue: dict[str, Any], assignee_names: dict[str, str]) -> str:
    aid = assignee_id(issue)
    if aid == "unassigned":
        return "Unassigned"
    if aid in assignee_names:
        return assignee_names[aid]
    return assignee_name(issue)


def issue_title(issue: dict[str, Any], key: str) -> str:
    return ((get_field(issue, "summary") or "") or key).strip()


def collect_issue_flags(
    issue: dict[str, Any],
    index: dict[str, dict[str, Any]],
    unscheduled_keys: set[str],
    config: dict[str, Any] | None = None,
) -> list[str]:
    key = issue.get("key") or ""
    reasons: list[str] = []
    t = issue_type_name(issue)
    if t not in SCHEDULABLE_TYPES:
        return reasons

    parent = get_field(issue, "parent")
    if not parent or not parent.get("key"):
        reasons.append(REASON_PARENT_NOT_MAPPED)
    else:
        parent_key = parent.get("key")
        if parent_key not in index:
            reasons.append(REASON_PARENT_OUT_OF_SCOPE)
        elif resolve_epic(issue, index) is None:
            reasons.append(REASON_EPIC_NOT_MAPPED)

    if is_bug_issue(issue):
        if bug_missing_logged_time(issue, config):
            reasons.append(REASON_MISSING_LOGGED_TIME)
    elif key in unscheduled_keys or estimate_seconds(issue, config) <= 0:
        subtask_oe_sum = (
            subtasks_estimate_seconds(key, index, config)
            if issue_type_name(issue) == "task"
            else 0
        )
        if subtask_oe_sum <= 0 and REASON_MISSING_ESTIMATE not in reasons:
            reasons.append(REASON_MISSING_ESTIMATE)

    if assignee_id(issue) == "unassigned":
        reasons.append(REASON_UNASSIGNED)

    return reasons


def consolidate_dq_rows(
    by_member: dict[str, list[dict[str, str]]],
) -> dict[str, list[dict[str, str]]]:
    """Merge multiple rows for the same (member, key) into one semicolon-separated reason."""
    consolidated: dict[str, list[dict[str, str]]] = {}
    reason_rank = {r: i for i, r in enumerate(REASON_SORT_ORDER)}

    for member, rows in by_member.items():
        grouped: dict[str, dict[str, str]] = {}
        for row in rows:
            key = row["key"]
            if key not in grouped:
                grouped[key] = {"key": key, "title": row["title"], "reasons": []}
            grouped[key]["reasons"].append(row["reason"])

        merged: list[dict[str, str]] = []
        for key in sorted(grouped.keys()):
            entry = grouped[key]
            unique_reasons = sorted(
                set(entry["reasons"]),
                key=lambda r: (reason_rank.get(r, len(REASON_SORT_ORDER)), r),
            )
            merged.append(
                {
                    "key": key,
                    "title": entry["title"],
                    "reason": "; ".join(unique_reasons),
                }
            )
        consolidated[member] = merged

    return consolidated


def count_dq_reasons(by_member: dict[str, list[dict[str, str]]]) -> dict[str, int]:
    """Count each reason label across consolidated rows (split on '; ')."""
    counts: dict[str, int] = defaultdict(int)
    for rows in by_member.values():
        for row in rows:
            for part in row["reason"].split("; "):
                part = part.strip()
                if part:
                    counts[part] += 1
    return dict(counts)


def build_data_quality_by_member(
    issues: list[dict[str, Any]],
    schedule: dict[str, Any],
    timeline: list[dict[str, Any]] | None = None,
    assignee_names: dict[str, str] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, list[dict[str, str]]]:
    """
    Return {member_display_name: [{key, title, reason}, ...]} sorted by member then key.
    One row per ticket per member; multiple reasons joined with '; '.
    """
    names = assignee_names or {}
    index = build_index(issues)
    unscheduled_keys = {u["key"] for u in schedule.get("unscheduled", []) if u.get("key")}

    by_member: dict[str, list[dict[str, str]]] = defaultdict(list)
    seen: set[tuple[str, str, str]] = set()

    def add(member: str, key: str, title: str, reason: str) -> None:
        dedupe = (member, key, reason)
        if dedupe in seen:
            return
        seen.add(dedupe)
        by_member[member].append(
            {"key": key, "title": title[:120], "reason": reason}
        )

    for issue in issues:
        key = issue.get("key")
        if not key:
            continue
        member = assignee_display(issue, names)
        title = issue_title(issue, key)
        for reason in collect_issue_flags(issue, index, unscheduled_keys, config):
            add(member, key, title, reason)

    if timeline:
        for epic in timeline:
            for u in epic.get("unmapped") or []:
                if u.get("additionalEffort"):
                    continue
                ukey = u.get("key")
                if not ukey:
                    continue
                issue = index.get(ukey, {})
                member = u.get("assignee") or (
                    assignee_display(issue, names) if issue else "Unassigned"
                )
                title = u.get("summary") or issue_title(issue, ukey)
                add(member, ukey, title, REASON_TIMELINE_UNMAPPED)

    consolidated = consolidate_dq_rows(dict(by_member))
    return dict(
        sorted(consolidated.items(), key=lambda x: (x[0] == "Unassigned", x[0].lower()))
    )
