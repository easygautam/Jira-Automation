"""Assemble the full sprint report markdown from pipeline outputs."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from sprintkit.delta import compute_schedule_delta
from sprintkit.jira_model import epic_jira_sort_key, is_epic_issue
from sprintkit.quality import build_data_quality_by_member
from sprintkit.render.markdown import linkify_bare_issue_keys, resolve_jira_site_url
from sprintkit.render.sections import (
    render_bug_sections,
    render_data_quality_section,
    render_delivery_items,
    render_executive_summary,
    render_recommended_actions,
    render_schedule_delta_section,
    render_team_tasks_plan,
    render_timeline_sections,
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
    est_by_key = {x["key"]: x.get("estimateSeconds", 0) for x in engine.get("items", [])}
    engine_items = engine.get("items", [])

    assignee_names: dict[str, str] = {}
    for i in issues:
        a = i.get("fields", {}).get("assignee")
        if a:
            aid = a.get("accountId") or a.get("displayName")
            assignee_names[aid] = a.get("displayName", aid)

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

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    by_assignee: dict[str, list] = defaultdict(list)
    for row in scheduled:
        by_assignee[row["assignee"]].append(row)

    timeline_epic_keys = (
        {e.get("epicKey") for e in timeline if e.get("epicKey")} if timeline else set()
    )

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
        f"**Sprint window:** {sprint_start} → {sprint_end}",
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
            timeline_epic_keys,
            jira_site_url,
            config,
        )
    )

    if timeline:
        lines.extend(render_timeline_sections(timeline, jira_site_url))

    if bug_effort:
        bug_by_key = {e["epicKey"]: e for e in bug_effort}
        ordered_bug = [bug_by_key[k] for k in ordered_epic_keys if k in bug_by_key]
        lines.extend(render_bug_sections(ordered_bug, jira_site_url))

    lines.extend(
        render_team_tasks_plan(
            by_assignee,
            assignee_names,
            issue_by_key,
            est_by_key,
            jira_site_url,
            config,
        )
    )

    quality_by_member = build_data_quality_by_member(
        issues, schedule, timeline, assignee_names, config
    )
    lines.extend(render_data_quality_section(quality_by_member, jira_site_url))

    if prior_schedule:
        delta = compute_schedule_delta(prior_schedule, schedule)
        lines.extend(render_schedule_delta_section(delta, jira_site_url))

    lines.extend(render_recommended_actions(quality_by_member))

    report = "\n".join(lines)
    project_key = (config or {}).get("jira", {}).get("projectKey") or project
    return linkify_bare_issue_keys(report, jira_site_url, project_key=project_key)
