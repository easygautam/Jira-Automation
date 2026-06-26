"""Assemble the full sprint report markdown from pipeline outputs."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from sprintkit.jira_model import epic_jira_sort_key, is_epic_issue
from sprintkit.render.markdown import fmt_date, fmt_date_range, linkify_bare_issue_keys, resolve_jira_site_url
from sprintkit.render.sections import (
    render_delivery_items,
    render_epic_quality_report,
    render_executive_summary,
)


def render_report(
    issues: list[dict],
    schedule: dict,
    engine: dict,
    project: str,
    sprint_label: str,
    sprint_meta: dict | None,
    jira_site_url: str | None = None,
    timeline: list[dict[str, Any]] | None = None,
    bug_effort: list[dict[str, Any]] | None = None,
    config: dict[str, Any] | None = None,
    prior_schedule: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
) -> str:
    jira_site_url = resolve_jira_site_url(jira_site_url, config, issues)

    issue_by_key = {i["key"]: i for i in issues}
    engine_items = engine.get("items", [])

    scheduled = schedule.get("scheduled", [])
    unscheduled = schedule.get("unscheduled", [])
    status_counts: dict[str, int] = defaultdict(int)
    for s in scheduled:
        status_counts[s.get("status", "on_track")] += 1

    sprint_start = engine.get("sprintStart", "")
    sprint_end = engine.get("sprintEnd", "")
    if sprint_meta:
        sprint_start = sprint_meta.get("sprintStart", sprint_start)
        sprint_end = sprint_meta.get("sprintEnd", sprint_end)
        sprint_label = sprint_meta.get("sprintName", sprint_label)

    now_dt = datetime.now(timezone.utc)
    now = f"{fmt_date(now_dt.date().isoformat())} {now_dt.strftime('%H:%M')} UTC"

    epic_keys = {i["key"] for i in issues if is_epic_issue(i)}
    for row in scheduled:
        if row.get("epicKey"):
            epic_keys.add(row["epicKey"])
    ordered_epic_keys = sorted(
        epic_keys, key=lambda k: epic_jira_sort_key(k, issue_by_key, config)
    )

    lines: list[str] = [
        f"# Sprint Report — {project} — {sprint_label}",
        "",
        f"**Generated:** {now}  ",
        f"**Sprint window:** {fmt_date_range(sprint_start, sprint_end)}",
        "",
    ]

    lines.extend(
        render_executive_summary(
            status_counts, unscheduled, issue_by_key, config, warnings=warnings
        )
    )
    lines.extend(
        render_delivery_items(
            ordered_epic_keys,
            issues,
            issue_by_key,
            scheduled,
            unscheduled,
            engine_items,
            set(),
            jira_site_url,
            config,
            timeline=timeline,
        )
    )

    if bug_effort:
        bug_by_key = {e["epicKey"]: e for e in bug_effort}
        ordered_bug = [bug_by_key[k] for k in ordered_epic_keys if k in bug_by_key]
        lines.extend(render_epic_quality_report(ordered_bug, jira_site_url))

    report = "\n".join(lines)
    project_key = (config or {}).get("jira", {}).get("projectKey") or project
    return linkify_bare_issue_keys(report, jira_site_url, project_key=project_key)
