"""Markdown and canvas payload builders for epic estimation display."""

from __future__ import annotations

from typing import Any

from sprintkit.render.markdown import (
    escape_md_cell,
    fmt_hours,
    fmt_resources,
    jira_issue_keys_linked,
    jira_issue_link,
)
from sprintkit.timeline import format_calc_days
from sprintkit.render.sections import TEAM_PLAN_ORDER

PLATFORM_LABELS = {"backend": "Backend", "frontend": "Web", "mobile": "Mobile"}


def _fmt_date(value: str | None) -> str:
    return value if value else "—"


def build_epic_markdown(
    epic_key: str,
    prd_name: str,
    epic_row: dict[str, Any],
    *,
    jira_site_url: str | None,
    quality: dict[str, list[dict[str, str]]] | None = None,
) -> str:
    lines: list[str] = [
        f"# Epic estimation — {jira_issue_link(jira_site_url, epic_key)}",
        "",
        f"**{escape_md_cell(prd_name)}**",
        "",
        f"- Delivery start: {_fmt_date(epic_row.get('deliveryStart'))}",
        f"- Go-live: {_fmt_date(epic_row.get('goLive'))}",
        "",
        "## Teams plan",
        "",
        "| Team | Peak resources | Total effort (h) | Leave (h) | Tasks |",
        "|------|----------------|------------------|-----------|-------|",
    ]

    summary_by_side = epic_row.get("teamSummary") or {}
    for side in TEAM_PLAN_ORDER:
        summary = summary_by_side.get(side)
        if not summary:
            continue
        combined_leave = (summary.get("totalLeaveHours") or 0) + (
            summary.get("totalDelayHours") or 0
        )
        lines.append(
            f"| {side} | {fmt_resources(summary.get('peakResources'))} | "
            f"{fmt_hours(summary.get('totalEffortHours'))} | "
            f"{fmt_hours(combined_leave or None)} | "
            f"{summary.get('taskCount', 0)} |"
        )

    members_by_side = epic_row.get("membersBySide") or {}
    for side in TEAM_PLAN_ORDER:
        members = members_by_side.get(side) or []
        if not members:
            continue
        lines.extend(["", f"### {side} — member breakdown", ""])
        lines.append(
            "| Member | Efforts (h) | Planned leave (h) | Unplanned delay (h) | "
            "Calc days | Issues | Mapped tasks |"
        )
        lines.append(
            "|--------|-------------|-------------------|---------------------|"
            "-----------|--------|--------------|"
        )
        for m in members:
            calc_s = format_calc_days(m.get("calculatedDays"))
            tasks_s = escape_md_cell(", ".join(m.get("tasks") or [])[:80]) or "—"
            issues_s = jira_issue_keys_linked(jira_site_url, m.get("issueKeys"))
            lines.append(
                f"| {escape_md_cell(m.get('member', ''))} | "
                f"{fmt_hours(m.get('effortsHours'))} | "
                f"{fmt_hours(m.get('plannedLeaveHours'))} | "
                f"{fmt_hours(m.get('unplannedDelayHours'))} | "
                f"{calc_s} | {issues_s} | {tasks_s} |"
            )

    exec_stages = epic_row.get("executionStages") or {}
    for plat_key, label in PLATFORM_LABELS.items():
        block = exec_stages.get(plat_key) or {}
        if not block.get("hasWork"):
            continue
        lines.extend(["", f"## Execution stages — {label}", ""])
        lines.append(
            "| Stage | Resources | Efforts (h) | Leave (h) | Calc days | Start | End |"
        )
        lines.append(
            "|-------|-----------|-------------|-----------|-----------|-------|-----|"
        )
        for row in block.get("stages") or []:
            calc_s = format_calc_days(row.get("calculatedDays"))
            stage_label = row.get("stage", "")
            if row.get("source") == "synthetic":
                stage_label = f"{stage_label} (est.)"
            combined_leave = (row.get("plannedLeaveHours") or 0) + (
                row.get("unplannedDelayHours") or 0
            )
            lines.append(
                f"| {escape_md_cell(stage_label)} | "
                f"{fmt_resources(row.get('resources'))} | "
                f"{fmt_hours(row.get('effortsHours'))} | "
                f"{fmt_hours(combined_leave or None)} | "
                f"{calc_s} | {_fmt_date(row.get('start'))} | {_fmt_date(row.get('end'))} |"
            )

    unmapped = epic_row.get("unmapped") or []
    if unmapped:
        lines.extend(["", "## Unmapped work", ""])
        for u in unmapped:
            key = u.get("key", "")
            lines.append(
                f"- {jira_issue_link(jira_site_url, key)}: "
                f"{escape_md_cell(u.get('summary', ''))} "
                f"({fmt_hours(u.get('effortsHours'))} h)"
            )

    if quality:
        flagged = sum(len(v) for v in quality.values())
        if flagged:
            lines.extend(["", "## Data quality flags", ""])
            for member, rows in sorted(quality.items()):
                for row in rows:
                    lines.append(
                        f"- {member} · {jira_issue_link(jira_site_url, row['key'])} · "
                        f"{escape_md_cell(row['reason'])}"
                    )

    return "\n".join(lines).rstrip() + "\n"


def build_canvas_data(
    epic_key: str,
    prd_name: str,
    epic_row: dict[str, Any],
    *,
    jira_site_url: str | None,
    quality: dict[str, list[dict[str, str]]] | None = None,
) -> dict[str, Any]:
    """Structured payload for embedding in a Cursor Canvas."""
    teams_plan: list[dict[str, Any]] = []
    summary_by_side = epic_row.get("teamSummary") or {}
    for side in TEAM_PLAN_ORDER:
        summary = summary_by_side.get(side)
        if not summary:
            continue
        teams_plan.append(
            {
                "team": side,
                "peakResources": summary.get("peakResources"),
                "totalEffortHours": summary.get("totalEffortHours"),
                "leaveHours": (summary.get("totalLeaveHours") or 0)
                + (summary.get("totalDelayHours") or 0),
                "taskCount": summary.get("taskCount", 0),
            }
        )

    members: list[dict[str, Any]] = []
    for side in TEAM_PLAN_ORDER:
        for m in epic_row.get("membersBySide", {}).get(side) or []:
            members.append(
                {
                    "team": side,
                    "member": m.get("member"),
                    "effortsHours": m.get("effortsHours"),
                    "leaveHours": (m.get("plannedLeaveHours") or 0)
                    + (m.get("unplannedDelayHours") or 0),
                    "calculatedDays": m.get("calculatedDays"),
                    "issueKeys": m.get("issueKeys") or [],
                    "tasks": m.get("tasks") or [],
                }
            )

    platforms: list[dict[str, Any]] = []
    exec_stages = epic_row.get("executionStages") or {}
    for plat_key, label in PLATFORM_LABELS.items():
        block = exec_stages.get(plat_key) or {}
        if not block.get("hasWork"):
            continue
        stages: list[dict[str, Any]] = []
        for row in block.get("stages") or []:
            stages.append(
                {
                    "stage": row.get("stage"),
                    "synthetic": row.get("source") == "synthetic",
                    "resources": row.get("resources"),
                    "effortsHours": row.get("effortsHours"),
                    "leaveHours": (row.get("plannedLeaveHours") or 0)
                    + (row.get("unplannedDelayHours") or 0),
                    "calculatedDays": row.get("calculatedDays"),
                    "start": row.get("start"),
                    "end": row.get("end"),
                }
            )
        platforms.append({"platform": label, "stages": stages})

    dq_rows: list[dict[str, str]] = []
    if quality:
        for member, rows in sorted(quality.items()):
            for row in rows:
                dq_rows.append(
                    {"member": member, "key": row["key"], "reason": row["reason"]}
                )

    site = jira_site_url or ""
    return {
        "epicKey": epic_key,
        "epicUrl": f"{site}/browse/{epic_key}" if site else "",
        "prdName": prd_name,
        "deliveryStart": epic_row.get("deliveryStart"),
        "goLive": epic_row.get("goLive"),
        "jiraSiteUrl": site,
        "teamsPlan": teams_plan,
        "members": members,
        "platforms": platforms,
        "unmapped": epic_row.get("unmapped") or [],
        "dataQuality": dq_rows,
    }


def build_epic_display_payload(
    epic_key: str,
    prd_name: str,
    epic_row: dict[str, Any],
    quality: dict[str, list[dict[str, str]]],
    *,
    jira_site_url: str | None,
    project: str,
) -> dict[str, Any]:
    del project  # reserved for future Jira link context
    markdown = build_epic_markdown(
        epic_key, prd_name, epic_row, jira_site_url=jira_site_url, quality=quality
    )
    canvas = build_canvas_data(
        epic_key, prd_name, epic_row, jira_site_url=jira_site_url, quality=quality
    )
    return {"markdown": markdown, "canvas": canvas}
