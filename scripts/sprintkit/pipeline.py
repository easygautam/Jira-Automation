"""End-to-end pipeline: issues + config -> schedule, breakdowns, report markdown.

This wires the five-step process and the six report deliverables together so the
agent runs a single command instead of chaining six scripts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sprintkit.bugs import build_bug_effort_breakdown
from sprintkit.normalize import normalize
from sprintkit.quality import build_data_quality_by_member, count_dq_reasons
from sprintkit.render.markdown import (
    jira_issue_link,
    linkify_bare_issue_keys,
    resolve_jira_site_url,
)
from sprintkit.render.report import render_report
from sprintkit.schedule import compute_schedule
from sprintkit.sprint_window import extract_active_sprint
from sprintkit.config import config_warnings
from sprintkit.timeline import build_timeline_breakdown, check_timeline_team_consistency


@dataclass
class PipelineResult:
    markdown: str
    sprint_meta: dict[str, Any]
    engine: dict[str, Any]
    schedule: dict[str, Any]
    timeline: list[dict[str, Any]]
    bug_effort: list[dict[str, Any]]
    status_counts: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def resolve_sprint_meta(
    issues: list[dict[str, Any]],
    config: dict[str, Any],
    *,
    sprint_start: str | None = None,
    sprint_end: str | None = None,
    sprint_field: str | None = None,
) -> dict[str, Any]:
    """Active sprint window from Jira; explicit start/end override the field."""
    field_id = sprint_field or (config.get("fields") or {}).get("sprint") or "customfield_10020"
    meta: dict[str, Any] | None = None
    try:
        meta = extract_active_sprint(issues, field_id)
    except ValueError:
        meta = None

    if sprint_start or sprint_end:
        meta = dict(meta or {})
        if sprint_start:
            meta["sprintStart"] = sprint_start
        if sprint_end:
            meta["sprintEnd"] = sprint_end
        meta.setdefault("sprintName", "Active Sprint")
        meta.setdefault("state", "active")

    if not meta or not meta.get("sprintStart") or not meta.get("sprintEnd"):
        raise ValueError(
            "Could not resolve sprint window. Provide --sprint-start/--sprint-end "
            "or fetch issues including the Sprint field."
        )
    return meta


def run_pipeline(
    issues: list[dict[str, Any]],
    config: dict[str, Any],
    *,
    project: str,
    sprint_label: str = "Active Sprint",
    sprint_start: str | None = None,
    sprint_end: str | None = None,
    sprint_field: str | None = None,
    today: str | None = None,
    jira_site_url: str | None = None,
    prior_schedule: dict[str, Any] | None = None,
) -> PipelineResult:
    """Run window -> normalize -> schedule -> timeline -> bugs -> render."""
    sprint_meta = resolve_sprint_meta(
        issues,
        config,
        sprint_start=sprint_start,
        sprint_end=sprint_end,
        sprint_field=sprint_field,
    )

    engine = normalize(
        issues,
        config,
        sprint_meta["sprintStart"],
        sprint_meta["sprintEnd"],
        today or date.today().isoformat(),
    )
    schedule = compute_schedule(engine)
    timeline = build_timeline_breakdown(issues, schedule, config)
    
    from sprintkit.stage_dates import compute_stage_dates
    for epic_row in timeline:
        compute_stage_dates(epic_row, issues, config)

    bug_effort = build_bug_effort_breakdown(issues, schedule, config)

    report_warnings = config_warnings(config)
    report_warnings.extend(check_timeline_team_consistency(timeline))

    markdown = render_report(
        issues,
        schedule,
        engine,
        project,
        sprint_label,
        sprint_meta,
        jira_site_url=jira_site_url,
        timeline=timeline,
        bug_effort=bug_effort,
        config=config,
        prior_schedule=prior_schedule,
        warnings=report_warnings,
    )

    status_counts: dict[str, int] = {}
    for row in schedule.get("scheduled", []):
        s = row.get("status", "on_track")
        status_counts[s] = status_counts.get(s, 0) + 1

    return PipelineResult(
        markdown=markdown,
        sprint_meta=sprint_meta,
        engine=engine,
        schedule=schedule,
        timeline=timeline,
        bug_effort=bug_effort,
        status_counts=status_counts,
        warnings=report_warnings,
    )


def standup_summary(
    result: PipelineResult,
    issues: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
    jira_site_url: str | None = None,
    *,
    project: str | None = None,
) -> str:
    """Short chat-oriented standup text: blockers, overdue, at-risk, DQ counts."""
    issue_by_key = {i["key"]: i for i in issues}
    site = resolve_jira_site_url(jira_site_url, config, issues)
    today = result.engine.get("today", date.today().isoformat())
    sprint_end = result.sprint_meta.get("sprintEnd", "")

    blocked: list[str] = []
    overdue: list[str] = []
    at_risk: list[str] = []
    for row in result.schedule.get("scheduled", []):
        key = row.get("key")
        status = row.get("status")
        due = row.get("dueDate") or ""
        if status == "blocked":
            blocked.append(key)
        elif status == "delayed" or (due and due < today):
            overdue.append(key)
        elif status == "at_risk":
            at_risk.append(key)

    def _summ(key: str) -> str:
        issue = issue_by_key.get(key, {})
        title = ((issue.get("fields") or {}).get("summary") or key)[:70]
        return f"- {jira_issue_link(site, key)}: {title}"

    lines = [
        f"Standup — {result.sprint_meta.get('sprintName', 'Active Sprint')} "
        f"(today {today}, sprint ends {sprint_end})",
        "",
        f"Status: on_track {result.status_counts.get('on_track', 0)}, "
        f"at_risk {result.status_counts.get('at_risk', 0)}, "
        f"delayed {result.status_counts.get('delayed', 0)}, "
        f"blocked {result.status_counts.get('blocked', 0)}",
        "",
    ]
    if blocked:
        lines.append(f"Blocked ({len(blocked)}):")
        lines.extend(_summ(k) for k in blocked[:10])
        lines.append("")
    if overdue:
        lines.append(f"Delayed / overdue ({len(overdue)}):")
        lines.extend(_summ(k) for k in overdue[:10])
        lines.append("")
    if at_risk:
        lines.append(f"At risk ({len(at_risk)}):")
        lines.extend(_summ(k) for k in at_risk[:10])
        lines.append("")

    quality = build_data_quality_by_member(
        issues, result.schedule, result.timeline, None, config
    )
    flagged = sum(len(v) for v in quality.values())
    reasons = count_dq_reasons(quality)
    if flagged:
        top = ", ".join(f"{r} {n}" for r, n in sorted(reasons.items()))
        lines.append(f"Data quality: {flagged} flagged tickets ({top}).")

    text = "\n".join(lines).rstrip() + "\n"
    project_key = project or (config or {}).get("jira", {}).get("projectKey")
    return linkify_bare_issue_keys(text, site, project_key=project_key)
