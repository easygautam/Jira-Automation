#!/usr/bin/env python3
"""Collect sprint data-quality flags grouped by assignee."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from jira_normalize import (
    assignee_id,
    build_index,
    effective_estimate_seconds,
    get_field,
    has_actionable_bug_effort,
    issue_type_name,
    resolve_epic,
)

SCHEDULABLE_TYPES = frozenset(
    {"task", "sub-task", "subtask", "bug", "test execution"}
)

REASON_MISSING_ESTIMATE = "Missing estimates"
REASON_PARENT_NOT_MAPPED = "Parent not mapped"
REASON_EPIC_NOT_MAPPED = "Epic not mapped"
REASON_PARENT_OUT_OF_SCOPE = "Parent not in sprint"
REASON_TIMELINE_UNMAPPED = "Timeline mapping"
REASON_UNASSIGNED = "Unassigned"


def assignee_display(issue: dict[str, Any], assignee_names: dict[str, str]) -> str:
    aid = assignee_id(issue)
    if aid == "unassigned":
        return "Unassigned"
    return assignee_names.get(aid, aid)


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

    if has_actionable_bug_effort(issue, config):
        pass
    elif key in unscheduled_keys or effective_estimate_seconds(issue, config) <= 0:
        if REASON_MISSING_ESTIMATE not in reasons:
            reasons.append(REASON_MISSING_ESTIMATE)

    if assignee_id(issue) == "unassigned":
        reasons.append(REASON_UNASSIGNED)

    return reasons


def build_data_quality_by_member(
    issues: list[dict[str, Any]],
    schedule: dict[str, Any],
    engine: dict[str, Any],
    timeline: list[dict[str, Any]] | None = None,
    assignee_names: dict[str, str] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, list[dict[str, str]]]:
    """
    Return {member_display_name: [{key, title, reason}, ...]} sorted by member then key.
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

    issue_by_key = {i["key"]: i for i in issues if i.get("key")}

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
                ukey = u.get("key")
                if not ukey:
                    continue
                issue = issue_by_key.get(ukey, {})
                member = u.get("assignee") or (
                    assignee_display(issue, names) if issue else "Unassigned"
                )
                title = u.get("summary") or issue_title(issue, ukey)
                add(member, ukey, title, REASON_TIMELINE_UNMAPPED)

    for member in by_member:
        by_member[member].sort(key=lambda r: (r["reason"], r["key"]))

    return dict(
        sorted(by_member.items(), key=lambda x: (x[0] == "Unassigned", x[0].lower()))
    )


def main() -> None:
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Build data-quality JSON by member")
    parser.add_argument("--issues", required=True)
    parser.add_argument("--schedule", required=True)
    parser.add_argument("--engine-input", required=True)
    parser.add_argument("--timeline-breakdown", default=None)
    parser.add_argument("--config", default=".cursor/config/em-config.yaml")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    def load(path: str) -> Any:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(payload, dict) and "issues" in payload:
            return payload["issues"]
        return payload

    issues = load(args.issues)
    schedule = json.loads(Path(args.schedule).read_text(encoding="utf-8"))
    engine = json.loads(Path(args.engine_input).read_text(encoding="utf-8"))
    timeline = None
    if args.timeline_breakdown and Path(args.timeline_breakdown).exists():
        timeline = json.loads(Path(args.timeline_breakdown).read_text(encoding="utf-8"))

    assignee_names: dict[str, str] = {}
    for i in issues:
        a = get_field(i, "assignee")
        if a:
            aid = a.get("accountId") or a.get("displayName")
            assignee_names[aid] = a.get("displayName", aid)

    config: dict[str, Any] | None = None
    config_path = Path(args.config)
    if config_path.exists():
        try:
            import yaml

            config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except ImportError:
            pass

    result = build_data_quality_by_member(
        issues, schedule, engine, timeline, assignee_names, config
    )
    out = json.dumps(result, indent=2)
    if args.output:
        Path(args.output).write_text(out + "\n", encoding="utf-8")
    else:
        print(out)


if __name__ == "__main__":
    main()
