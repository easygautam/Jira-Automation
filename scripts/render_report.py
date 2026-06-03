#!/usr/bin/env python3
"""Render sprint report markdown from schedule + issues JSON."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from data_quality import build_data_quality_by_member
from jira_teams import team_from_issue
from timeline_breakdown import side_display

STATUS_RANK = {"blocked": 0, "delayed": 1, "at_risk": 2, "on_track": 3, "tbd": 4}
SCHEDULE_TEAM_ORDER = ("Backend", "Web", "Mobile", "QA", "Other")
BUG_FIX_SIDE_COLUMNS = ("Backend", "Web", "Mobile")


def jira_browse_url(site_url: str, issue_key: str) -> str:
    base = site_url.rstrip("/")
    return f"{base}/browse/{issue_key}"


def jira_issue_link(site_url: str | None, issue_key: str | None) -> str:
    if not issue_key:
        return "—"
    if site_url:
        return f"[{issue_key}]({jira_browse_url(site_url, issue_key)})"
    return issue_key


def escape_md_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def resolve_epic_summary(
    epic_key: str,
    issues: list[dict],
    issue_by_key: dict[str, dict],
) -> str:
    epic_issue = issue_by_key.get(epic_key)
    if epic_issue:
        return ((epic_issue.get("fields") or {}).get("summary") or epic_key).strip()
    for issue in issues:
        parent = (issue.get("fields") or {}).get("parent") or {}
        if parent.get("key") == epic_key:
            pf = parent.get("fields") or {}
            if (pf.get("issuetype") or {}).get("name") == "Epic":
                return (pf.get("summary") or epic_key).strip()
    return epic_key


def format_effort(seconds: int | None) -> str:
    if not seconds:
        return "—"
    hours = seconds / 3600
    if hours >= 8:
        days = hours / 8
        return f"{days:.1f}d" if days != int(days) else f"{int(days)}d"
    return f"{int(hours)}h" if hours == int(hours) else f"{hours:.1f}h"


def resolve_epic_key(issue: dict) -> str | None:
    parent = issue.get("fields", {}).get("parent")
    if not parent:
        return None
    pf = parent.get("fields") or {}
    if (pf.get("issuetype") or {}).get("name") == "Epic":
        return parent.get("key")
    return parent.get("key")


def story_key(issue: dict) -> str | None:
    parent = issue.get("fields", {}).get("parent")
    if not parent:
        return None
    pname = ((parent.get("fields") or {}).get("issuetype") or {}).get("name", "")
    if pname == "Story":
        return parent.get("key")
    return parent.get("key")


def is_epic_issue(issue: dict) -> bool:
    it = (issue.get("fields") or {}).get("issuetype") or {}
    if (it.get("name") or "").lower() == "epic":
        return True
    return (it.get("hierarchyLevel") or 0) > 0


def phase_for_epic(epic_key: str, issues: list[dict], status_map: dict) -> str:
    statuses = []
    for i in issues:
        ek = resolve_epic_key(i)
        if ek == epic_key or i.get("key") == epic_key:
            s = (i.get("fields", {}).get("status") or {}).get("name", "")
            statuses.append(status_map.get(s, s or "Unknown"))
    if not statuses:
        return "Unknown"
    phase_order = [
        "PRD Tech Discussion",
        "Tech Assessment",
        "Development",
        "QA Testing",
        "Bug fixes",
        "QA final testing",
        "Pre-Prod Deployments",
        "QA Pre-Prod Testing",
        "Product UAT and Design Review",
        "Ready for Release",
    ]
    best = "PRD Tech Discussion"
    for p in statuses:
        if p in phase_order and phase_order.index(p) >= phase_order.index(best):
            best = p
    return best


def worst_status(statuses: list[str]) -> str:
    if not statuses:
        return "tbd"
    return min(statuses, key=lambda s: STATUS_RANK.get(s, 99))


def schedule_member_anchor(display_name: str) -> str:
    """Markdown fragment id for member detail headers (GitHub-style slug)."""
    cleaned = "".join(
        c if c.isalnum() or c == " " else " " for c in display_name.strip().lower()
    )
    return "-".join(cleaned.split()) or "member"


def epic_prd_anchor(epic_key: str) -> str:
    """Stable fragment id for Timeline breakdown PRD section (epic key)."""
    return f"prd-{epic_key.lower()}"


def epic_title_link(summary: str, epic_key: str, link_to_timeline: bool) -> str:
    """Title cell: anchor to PRD timeline detail when breakdown exists for epic."""
    text = escape_md_cell(summary)
    if link_to_timeline:
        return f"[{text}](#{epic_prd_anchor(epic_key)})"
    return text


def member_team_label(issue: dict, config: dict[str, Any] | None) -> str:
    teams_cfg = (config or {}).get("teams") or {}
    team = team_from_issue(issue, teams_cfg, config)
    side_map = (config or {}).get("timeline", {}).get("sideDisplay") or {}
    return side_display(team, side_map)


def _team_index_sort_key(teams: list[str]) -> tuple[int, str]:
    if not teams:
        return (len(SCHEDULE_TEAM_ORDER), "Other")
    primary = teams[0]
    try:
        return (SCHEDULE_TEAM_ORDER.index(primary), primary)
    except ValueError:
        return (len(SCHEDULE_TEAM_ORDER), primary)


def render_team_tasks_plan(
    by_assignee: dict[str, list],
    assignee_names: dict[str, str],
    issue_by_key: dict[str, dict],
    est_by_key: dict[str, int],
    jira_site_url: str | None,
    config: dict[str, Any] | None,
) -> list[str]:
    """Per-member scheduled task tables (engine-calculated dates)."""
    if not by_assignee:
        return []

    lines = [
        "## Team tasks plan",
        "",
        "Scheduled tasks by assignee. Effort from Original Estimate "
        "(bugs: time spent when OE empty).",
        "",
    ]

    members: list[tuple[str, list]] = []
    for assignee_id, rows in by_assignee.items():
        display = assignee_names.get(assignee_id, assignee_id)
        teams_set: set[str] = set()
        for r in rows:
            issue = issue_by_key.get(r["key"], {})
            if issue:
                teams_set.add(member_team_label(issue, config))
        teams = sorted(teams_set, key=lambda t: _team_index_sort_key([t]))
        members.append((display, teams, rows))

    members.sort(key=lambda x: (_team_index_sort_key(x[1]), x[0].lower()))

    for display, _teams, rows in members:
        lines.append(f"### {display}")
        lines.append("")
        lines.append("| Key | Task title | Epic | Effort | Status |")
        lines.append("|-----|------------|------|--------|--------|")
        for r in rows:
            issue = issue_by_key.get(r["key"], {})
            title = escape_md_cell(
                ((issue.get("fields") or {}).get("summary") or r["key"])[:80]
            )
            key_link = jira_issue_link(jira_site_url, r["key"])
            epic_col = jira_issue_link(jira_site_url, r.get("epicKey"))
            lines.append(
                f"| {key_link} | {title} | {epic_col} "
                f"| {format_effort(est_by_key.get(r['key']))} | {r['status']} |"
            )
        lines.append("")

    return lines


def _member_primary_bug_side(member: dict[str, Any]) -> str | None:
    sides = member.get("sides") or []
    if not sides and member.get("side"):
        sides = [s.strip() for s in str(member.get("side", "")).split(",")]
    for col in BUG_FIX_SIDE_COLUMNS:
        if col in sides:
            return col
    return None


def _bug_hours_by_side(epic: dict[str, Any]) -> dict[str, float]:
    totals = {col: 0.0 for col in BUG_FIX_SIDE_COLUMNS}
    for m in epic.get("members") or []:
        side = _member_primary_bug_side(m)
        if side:
            totals[side] += m.get("effortsHours") or 0
    return totals


def _fmt_hours(val: float | None) -> str:
    if val is None or val == 0:
        return "—"
    return str(val) if val == int(val) else f"{val:.1f}"


def _fmt_date(val: str | None) -> str:
    return val or "TBD"


def _fmt_resources(val: float | None) -> str:
    if val is None or val <= 0:
        return "—"
    return f"{val:.1f}"


def render_timeline_sections(
    timeline: list[dict[str, Any]],
    jira_site_url: str | None,
) -> list[str]:
    if not timeline:
        return []

    lines = [
        '<span id="timeline-breakdown-jira"></span>',
        "",
        "## Timeline breakdown (Jira)",
        "",
        "**Effort** includes **Task** and **Sub-task** issue types only (bugs excluded).  ",
        "Bug effort is in **Bug fix effort** below (same file).",
        "",
        "**Calc days** = ceil((Efforts + Planned Leave + Unplanned Delays) / (Resources × 6h)).  ",
        "**Start/End** = min/max scheduled dates for Jira work in that row.",
        "",
    ]

    for epic in timeline:
        epic_key = epic.get("epicKey", "")
        prd = escape_md_cell(epic.get("prdName") or epic_key)
        epic_link = jira_issue_link(jira_site_url, epic_key)
        d_start = _fmt_date(epic.get("deliveryStart"))
        d_end = _fmt_date(epic.get("deliveryEnd"))
        go_live = _fmt_date(epic.get("goLive"))
        cal_days = epic.get("calendarDeliveryDays")
        cal_s = f" | Calendar days: {cal_days}" if cal_days else ""

        lines.append(f'<span id="{epic_prd_anchor(epic_key)}"></span>')
        lines.append("")
        lines.append(f"### {epic_link} — {prd}")
        lines.append(
            f"- Delivery window: {d_start} → {d_end} | Go live: {go_live}{cal_s}"
        )
        lines.append("")
        lines.append("#### Teams plan")
        lines.append("")
        lines.append(
            "| Team | Peak resources | Total effort (h) | Planned leave (h) | "
            "Unplanned delay (h) | Tasks |"
        )
        lines.append(
            "|------|----------------|------------------|-------------------|"
            "---------------------|-------|"
        )
        team_order = ("Backend", "Web", "Mobile", "QA", "Other")
        summary_by_side = epic.get("teamSummary") or {}
        for side in team_order:
            summary = summary_by_side.get(side)
            if not summary:
                continue
            lines.append(
                f"| {side} | {_fmt_resources(summary.get('peakResources'))} | "
                f"{_fmt_hours(summary.get('totalEffortHours'))} | "
                f"{_fmt_hours(summary.get('totalLeaveHours'))} | "
                f"{_fmt_hours(summary.get('totalDelayHours'))} | "
                f"{summary.get('taskCount', 0)} |"
            )
        members_by_side = epic.get("membersBySide") or {}
        for side in team_order:
            if side not in members_by_side:
                continue
            members = members_by_side[side]
            if not members:
                continue
            lines.append("")
            lines.append(f"**{side}** — member breakdown")
            lines.append("")
            lines.append(
                "| Member | Efforts (h) | Planned leave (h) | Unplanned delay (h) | "
                "Start | End | Calc days | Issues | Mapped tasks |"
            )
            lines.append(
                "|--------|-------------|-------------------|---------------------|"
                "-------|-----|-----------|--------|--------------|"
            )
            for m in members:
                calc = m.get("calculatedDays")
                calc_s = str(calc) if calc is not None else "—"
                tasks_s = escape_md_cell(", ".join(m.get("tasks") or [])[:80]) or "—"
                issues_s = ", ".join(m.get("issueKeys") or [])[:60]
                if len(m.get("issueKeys") or []) > 4:
                    issues_s += "…"
                lines.append(
                    f"| {escape_md_cell(m.get('member', ''))} | "
                    f"{_fmt_hours(m.get('effortsHours'))} | "
                    f"{_fmt_hours(m.get('plannedLeaveHours'))} | "
                    f"{_fmt_hours(m.get('unplannedDelayHours'))} | "
                    f"{_fmt_date(m.get('start'))} | {_fmt_date(m.get('end'))} | {calc_s} | "
                    f"{escape_md_cell(issues_s)} | {tasks_s} |"
                )
        lines.append("")
        lines.append("#### Task breakdown")
        lines.append("")
        lines.append(
            "| Task | Side | Resources | Efforts (h) | Leave (h) | Delay (h) | "
            "Start | End | Calc days |"
        )
        lines.append(
            "|------|------|-----------|-------------|-----------|-----------|"
            "-------|-----|-----------|"
        )
        for row in epic.get("tasks") or []:
            calc = row.get("calculatedDays")
            calc_s = str(calc) if calc is not None else "—"
            lines.append(
                f"| {escape_md_cell(row.get('task', ''))} | {row.get('team') or '—'} | "
                f"{_fmt_resources(row.get('resources'))} | "
                f"{_fmt_hours(row.get('effortsHours'))} | "
                f"{_fmt_hours(row.get('plannedLeaveHours'))} | "
                f"{_fmt_hours(row.get('unplannedDelayHours'))} | "
                f"{_fmt_date(row.get('start'))} | {_fmt_date(row.get('end'))} | {calc_s} |"
            )
        lines.append("")

        unmapped = epic.get("unmapped") or []
        if unmapped:
            lines.append("#### Unmapped sprint work")
            lines.append("")
            for u in unmapped:
                key_link = jira_issue_link(jira_site_url, u.get("key"))
                summary = escape_md_cell(u.get("summary", ""))
                hrs = _fmt_hours(u.get("effortsHours"))
                lines.append(f"- {key_link}: {summary} ({hrs} h)")
            lines.append("")

    return lines


def render_bug_sections(
    bug_data: list[dict[str, Any]],
    jira_site_url: str | None,
) -> list[str]:
    if not bug_data:
        return []

    lines = [
        "## Bug fix effort",
        "",
        "Jira **Bug** issues — worklog **time spent** (h) by epic and engineering side. "
        "QA/Other effort appears in member detail only.",
        "",
        "| Epic ID | Epic Name | Backend | Web | Mobile | Bugs |",
        "|---------|-----------|---------|-----|--------|------|",
    ]

    col_totals = {col: 0.0 for col in BUG_FIX_SIDE_COLUMNS}
    for epic in bug_data:
        epic_key = epic.get("epicKey", "")
        prd = escape_md_cell(epic.get("prdName") or epic_key)
        epic_id = jira_issue_link(jira_site_url, epic_key) if jira_site_url else epic_key
        by_side = _bug_hours_by_side(epic)
        cells = []
        for col in BUG_FIX_SIDE_COLUMNS:
            h = by_side[col]
            col_totals[col] += h
            cells.append(_fmt_hours(h) if h else "—")
        bug_n = epic.get("bugCount", 0)
        lines.append(f"| {epic_id} | {prd} | {' | '.join(cells)} | {bug_n} |")

    lines.append("")
    grand_total = sum(col_totals.values())
    lines.append(
        f"**Sprint bug effort total:** {_fmt_hours(grand_total)} h "
        f"(Backend {_fmt_hours(col_totals['Backend'])}, "
        f"Web {_fmt_hours(col_totals['Web'])}, "
        f"Mobile {_fmt_hours(col_totals['Mobile'])})"
    )
    lines.append("")

    for epic in bug_data:
        epic_key = epic.get("epicKey", "")
        prd = escape_md_cell(epic.get("prdName") or epic_key)
        epic_link = jira_issue_link(jira_site_url, epic_key)
        members = epic.get("members") or []
        bug_n = epic.get("bugCount", 0)
        if not members and bug_n == 0:
            continue
        lines.append(f"### {epic_link} — {prd}")
        if not members and bug_n > 0:
            lines.append("")
            lines.append(f"_{bug_n} bugs in scope; no worklog time logged yet._")
            lines.append("")
            continue
        lines.append("")
        lines.append("| Member | Bug effort (h) | Bug count |")
        lines.append("|--------|----------------|-----------|")
        for m in members:
            lines.append(
                f"| {escape_md_cell(m.get('member', ''))} | "
                f"{_fmt_hours(m.get('effortsHours'))} | {m.get('bugCount', 0)} |"
            )
        lines.append("")

    return lines


def render_data_quality_section(
    by_member: dict[str, list[dict[str, str]]],
    jira_site_url: str | None,
) -> list[str]:
    lines = [
        "## Data quality flags",
        "",
        "Issues by assignee that need cleanup before planning is reliable. "
        "Task start/due in reports are **calculated** from estimates — not read from Jira.",
        "",
    ]
    total_rows = sum(len(rows) for rows in by_member.values())
    if total_rows == 0:
        lines.append("No data-quality issues detected for sprint work items.")
        lines.append("")
        return lines

    lines.append(f"**Total flagged rows:** {total_rows} across {len(by_member)} members")
    lines.append("")

    for member, rows in by_member.items():
        lines.append(f"### {escape_md_cell(member)}")
        lines.append("")
        lines.append("| Ticket | Title | Reason |")
        lines.append("|--------|-------|--------|")
        for row in rows:
            key_link = jira_issue_link(jira_site_url, row.get("key"))
            title = escape_md_cell(row.get("title", ""))
            reason = escape_md_cell(row.get("reason", ""))
            lines.append(f"| {key_link} | {title} | {reason} |")
        lines.append("")

    return lines


def compute_epic_rollup(
    epic_key: str,
    scheduled: list[dict[str, Any]],
    unscheduled: list[dict[str, Any]],
    engine_items: list[dict[str, Any]],
) -> dict[str, Any]:
    rows = [r for r in scheduled if r.get("epicKey") == epic_key]
    unsched_keys = {
        u["key"]
        for u in unscheduled
        if engine_items
        and any(
            x.get("key") == u.get("key") and x.get("epicKey") == epic_key
            for x in engine_items
        )
    }
    # fallback: count unscheduled by epic from engine items
    if not unsched_keys:
        unsched_keys = {
            u["key"]
            for u in unscheduled
            for x in engine_items
            if x.get("key") == u.get("key") and x.get("epicKey") == epic_key
        }

    if not rows:
        return {
            "start": None,
            "due": None,
            "status": "tbd",
            "scheduled_count": 0,
            "unscheduled_count": len(unsched_keys),
        }

    return {
        "start": min(r["startDate"] for r in rows),
        "due": max(r["dueDate"] for r in rows),
        "status": worst_status([r.get("status", "on_track") for r in rows]),
        "scheduled_count": len(rows),
        "unscheduled_count": len(unsched_keys),
    }


def epic_priority_rank(epic_key: str, engine_items: list[dict[str, Any]]) -> int:
    ranks = [x.get("epicPriorityRank", 999) for x in engine_items if x.get("epicKey") == epic_key]
    return min(ranks) if ranks else 999


def render_report(
    issues: list[dict],
    schedule: dict,
    engine: dict,
    project: str,
    sprint_label: str,
    sprint_meta: dict | None,
    status_map: dict[str, str],
    jira_site_url: str | None = None,
    timeline: list[dict[str, Any]] | None = None,
    bug_effort: list[dict[str, Any]] | None = None,
    config: dict[str, Any] | None = None,
) -> str:
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

    lines = [
        f"# Sprint Report — {project} — {sprint_label}",
        "",
        f"**Generated:** {now}  ",
        f"**Sprint window:** {sprint_start} → {sprint_end}",
        "",
        "## Executive summary",
        "",
        "| Metric | Count |",
        "|--------|-------|",
        f"| On track | {status_counts.get('on_track', 0)} |",
        f"| At risk | {status_counts.get('at_risk', 0)} |",
        f"| Delayed | {status_counts.get('delayed', 0)} |",
        f"| Blocked | {status_counts.get('blocked', 0)} |",
        f"| Unscheduled (missing estimate) | {len(unscheduled)} |",
        "",
    ]

    risk_n = status_counts.get("delayed", 0) + status_counts.get("at_risk", 0)
    if unscheduled:
        lines.append(
            f"{len(unscheduled)} items lack Original Estimate and could not be scheduled. "
            f"{risk_n} scheduled items are at risk or delayed relative to sprint end."
        )
    else:
        lines.append(
            f"{status_counts.get('on_track', 0)} items on track; "
            f"{risk_n} need attention before sprint end."
        )
    lines.append("")

    timeline_epic_keys = (
        {e.get("epicKey") for e in timeline if e.get("epicKey")} if timeline else set()
    )

    lines.append("## Delivery items (Epics)")
    lines.append("")
    if timeline_epic_keys:
        lines.append(
            "Click a **Title** to jump to that epic's PRD detail in "
            "[Timeline breakdown](#timeline-breakdown-jira) below."
        )
        lines.append("")
    lines.append(
        "| Epic | Title | Start | Due | Phase | Status | Scheduled tasks | Unscheduled |"
    )
    lines.append(
        "|------|-------|-------|-----|-------|--------|-----------------|-------------|"
    )

    epic_keys = {i["key"] for i in issues if is_epic_issue(i)}
    for row in scheduled:
        if row.get("epicKey"):
            epic_keys.add(row["epicKey"])

    def epic_sort_key(key: str) -> tuple:
        rollup = compute_epic_rollup(key, scheduled, unscheduled, engine_items)
        return (epic_priority_rank(key, engine_items), rollup.get("due") or "9999", key)

    for epic_key in sorted(epic_keys, key=epic_sort_key):
        epic_issue = issue_by_key.get(epic_key)
        if epic_issue and not is_epic_issue(epic_issue):
            continue
        epic_summary = resolve_epic_summary(epic_key, issues, issue_by_key)
        title_cell = epic_title_link(
            epic_summary, epic_key, epic_key in timeline_epic_keys
        )
        epic_link = jira_issue_link(jira_site_url, epic_key)
        rollup = compute_epic_rollup(epic_key, scheduled, unscheduled, engine_items)
        phase = phase_for_epic(epic_key, issues, status_map)
        start_s = rollup["start"] or "TBD"
        due_s = rollup["due"] or "TBD"
        status_s = rollup["status"] if rollup["status"] != "tbd" else "TBD"
        lines.append(
            f"| {epic_link} | {title_cell} | {start_s} | {due_s} | {phase} | {status_s} "
            f"| {rollup['scheduled_count']} | {rollup['unscheduled_count']} |"
        )

    lines.append("")
    if timeline:
        lines.extend(render_timeline_sections(timeline, jira_site_url))
    if bug_effort:
        bug_by_key = {e["epicKey"]: e for e in bug_effort}
        ordered_bug = [
            bug_by_key[k]
            for k in sorted(epic_keys, key=epic_sort_key)
            if k in bug_by_key
        ]
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
        issues, schedule, engine, timeline, assignee_names, config
    )
    lines.extend(render_data_quality_section(quality_by_member, jira_site_url))

    lines.append("## Recommended actions")
    lines.append("")
    missing_n = len([u for u in unscheduled if u.get("reason") == "missing_estimate"])
    n = 1
    if missing_n:
        lines.append(
            f"{n}. Add Original Estimate on {missing_n} unscheduled items (Jira start/due not required)."
        )
        n += 1
    lines.append(f"{n}. Review delayed/at-risk epics before sprint end.")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--issues", default="scripts/.tmp/issues.json")
    parser.add_argument("--schedule", default="scripts/.tmp/schedule.json")
    parser.add_argument("--engine-input", default="scripts/.tmp/engine-input.json")
    parser.add_argument("--sprint-meta", default="scripts/.tmp/sprint-meta.json")
    parser.add_argument("--project", default="VP")
    parser.add_argument("--sprint-label", default="Active Sprint")
    parser.add_argument("--output", default=None)
    parser.add_argument("--config", default=".cursor/config/em-config.yaml")
    parser.add_argument("--jira-site-url", default=None, help="Override jira.siteUrl from config")
    parser.add_argument(
        "--timeline-breakdown",
        default="scripts/.tmp/timeline-breakdown.json",
        help="Timeline breakdown JSON (optional)",
    )
    parser.add_argument(
        "--bug-breakdown",
        default="scripts/.tmp/bug-effort-breakdown.json",
        help="Bug effort JSON from bug_effort_breakdown.py (optional)",
    )
    args = parser.parse_args()

    issues_payload = json.loads(Path(args.issues).read_text())
    issues = (
        issues_payload
        if isinstance(issues_payload, list)
        else issues_payload.get("issues", issues_payload)
    )
    schedule = json.loads(Path(args.schedule).read_text())
    engine = json.loads(Path(args.engine_input).read_text())

    cfg: dict | None = None
    jira_site_url = args.jira_site_url
    if Path(args.config).exists():
        try:
            import yaml

            cfg = yaml.safe_load(Path(args.config).read_text()) or {}
            if not jira_site_url:
                jira_site_url = (cfg.get("jira") or {}).get("siteUrl")
        except ImportError:
            pass

    sprint_meta = None
    meta_path = Path(args.sprint_meta)
    if meta_path.exists():
        sprint_meta = json.loads(meta_path.read_text())

    status_map = {
        "TO  DO": "PRD Tech Discussion",
        "To Do": "PRD Tech Discussion",
        "In Progress": "Development",
        "Done": "Ready for Release",
        "QA": "QA Testing",
    }

    timeline_data = None
    tb_path = Path(args.timeline_breakdown)
    if tb_path.exists():
        timeline_data = json.loads(tb_path.read_text(encoding="utf-8"))

    bug_data = None
    bug_path = Path(args.bug_breakdown)
    if bug_path.exists():
        bug_data = json.loads(bug_path.read_text(encoding="utf-8"))

    body = render_report(
        issues,
        schedule,
        engine,
        args.project,
        args.sprint_label,
        sprint_meta,
        status_map,
        jira_site_url=jira_site_url,
        timeline=timeline_data,
        bug_effort=bug_data,
        config=cfg,
    )

    out_path = args.output or f"reports/sprint-{datetime.now().strftime('%Y-%m-%d')}.md"
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(body, encoding="utf-8")

    scheduled = schedule.get("scheduled", [])
    status_counts: dict[str, int] = defaultdict(int)
    for s in scheduled:
        status_counts[s.get("status", "on_track")] += 1

    print(out_path)
    print(
        json.dumps(
            {
                "status_counts": dict(status_counts),
                "scheduled": len(scheduled),
                "unscheduled": len(schedule.get("unscheduled", [])),
                "sprint": sprint_meta,
            }
        )
    )


if __name__ == "__main__":
    main()
