"""One renderer per report section; each returns a list of markdown lines."""

from __future__ import annotations

from typing import Any

from sprintkit.delta import delta_has_changes
from sprintkit.jira_model import (
    count_unscheduled_breakdown,
    epic_summary,
    lookup_status_phase,
)
from sprintkit.quality import (
    REASON_MISSING_ESTIMATE,
    REASON_MISSING_LOGGED_TIME,
    count_dq_reasons,
)
from sprintkit.render.markdown import (
    epic_prd_anchor,
    epic_title_link,
    escape_md_cell,
    fmt_hours,
    fmt_resources,
    format_effort,
    jira_issue_keys_linked,
    jira_issue_link,
)
from sprintkit.teams import team_from_issue
from sprintkit.timeline import side_display

STATUS_RANK = {"blocked": 0, "delayed": 1, "at_risk": 2, "on_track": 3, "tbd": 4}
SCHEDULE_TEAM_ORDER = ("Backend", "Web", "Mobile", "QA", "Other")
BUG_FIX_SIDE_COLUMNS = ("Backend", "Web", "Mobile", "QA", "Other")
TEAM_PLAN_ORDER = ("Backend", "Web", "Mobile", "QA", "Other")


# --- shared epic helpers --------------------------------------------------


def worst_status(statuses: list[str]) -> str:
    if not statuses:
        return "tbd"
    return min(statuses, key=lambda s: STATUS_RANK.get(s, 99))


def parent_key(issue: dict) -> str | None:
    """Immediate parent key (used for phase rollup on direct children)."""
    parent = issue.get("fields", {}).get("parent")
    return parent.get("key") if parent else None


def phase_for_epic(epic_key: str, issues: list[dict], config: dict[str, Any] | None = None) -> str:
    statuses = []
    for i in issues:
        pk = parent_key(i)
        if pk == epic_key or i.get("key") == epic_key:
            s = (i.get("fields", {}).get("status") or {}).get("name", "")
            statuses.append(lookup_status_phase(s, config))
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


# --- section renderers ----------------------------------------------------


def render_executive_summary(
    status_counts: dict[str, int],
    unscheduled: list[dict[str, Any]],
    issue_by_key: dict[str, dict],
    config: dict[str, Any] | None,
) -> list[str]:
    lines = [
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
    active_bugs, tasks_missing, other_unsched = count_unscheduled_breakdown(
        unscheduled, issue_by_key, config
    )
    if unscheduled:
        detail: list[str] = []
        if active_bugs:
            detail.append(f"{active_bugs} active bugs (estimate not required yet)")
        if tasks_missing:
            detail.append(f"{tasks_missing} tasks missing Original Estimate")
        if other_unsched:
            detail.append(f"{other_unsched} other (inactive bugs / no effort)")
        if detail:
            lines.append(
                f"{len(unscheduled)} items unscheduled, including "
                f"{', '.join(detail)}. "
                f"{risk_n} scheduled items are at risk or delayed relative to sprint end."
            )
        else:
            lines.append(
                f"{len(unscheduled)} items unscheduled. "
                f"{risk_n} scheduled items are at risk or delayed relative to sprint end."
            )
    else:
        lines.append(
            f"{status_counts.get('on_track', 0)} items on track; "
            f"{risk_n} need attention before sprint end."
        )
    lines.append("")
    return lines


def render_delivery_items(
    ordered_epic_keys: list[str],
    issues: list[dict],
    issue_by_key: dict[str, dict],
    scheduled: list[dict[str, Any]],
    unscheduled: list[dict[str, Any]],
    engine_items: list[dict[str, Any]],
    timeline_epic_keys: set[str],
    jira_site_url: str | None,
    config: dict[str, Any] | None,
) -> list[str]:
    from sprintkit.jira_model import is_epic_issue

    lines = ["## Delivery items (Epics)", ""]
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

    for epic_key in ordered_epic_keys:
        epic_issue = issue_by_key.get(epic_key)
        if epic_issue and not is_epic_issue(epic_issue):
            continue
        epic_title = epic_summary(epic_key, issues, issue_by_key)
        title_cell = epic_title_link(
            epic_title, epic_key, epic_key in timeline_epic_keys
        )
        epic_link = jira_issue_link(jira_site_url, epic_key)
        rollup = compute_epic_rollup(epic_key, scheduled, unscheduled, engine_items)
        phase = phase_for_epic(epic_key, issues, config)
        start_s = rollup["start"] or "TBD"
        due_s = rollup["due"] or "TBD"
        status_s = rollup["status"] if rollup["status"] != "tbd" else "TBD"
        lines.append(
            f"| {epic_link} | {title_cell} | {start_s} | {due_s} | {phase} | {status_s} "
            f"| {rollup['scheduled_count']} | {rollup['unscheduled_count']} |"
        )

    lines.append("")
    return lines


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
        "**Calc days** = ceil((Efforts + Leave) / (Resources × 6h)).",
        "",
    ]

    for epic in timeline:
        epic_key = epic.get("epicKey", "")
        prd = escape_md_cell(epic.get("prdName") or epic_key)
        epic_link = jira_issue_link(jira_site_url, epic_key)
        exec_stages = epic.get("executionStages") or {}

        lines.append(f'<span id="{epic_prd_anchor(epic_key)}"></span>')
        lines.append("")
        lines.append(f"### {epic_link} — {prd}")
        lines.append("")
        lines.append("#### Teams plan")
        lines.append("")
        lines.append(
            "| Team | Peak resources | Total effort (h) | Leave (h) | Tasks |"
        )
        lines.append(
            "|------|----------------|------------------|-----------|-------|"
        )
        summary_by_side = epic.get("teamSummary") or {}
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
        members_by_side = epic.get("membersBySide") or {}
        for side in TEAM_PLAN_ORDER:
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
                "Calc days | Issues | Mapped tasks |"
            )
            lines.append(
                "|--------|-------------|-------------------|---------------------|"
                "-----------|--------|--------------|"
            )
            for m in members:
                calc = m.get("calculatedDays")
                calc_s = str(calc) if calc is not None else "—"
                tasks_s = escape_md_cell(", ".join(m.get("tasks") or [])[:80]) or "—"
                issues_s = jira_issue_keys_linked(jira_site_url, m.get("issueKeys"))
                lines.append(
                    f"| {escape_md_cell(m.get('member', ''))} | "
                    f"{fmt_hours(m.get('effortsHours'))} | "
                    f"{fmt_hours(m.get('plannedLeaveHours'))} | "
                    f"{fmt_hours(m.get('unplannedDelayHours'))} | "
                    f"{calc_s} | "
                    f"{issues_s} | {tasks_s} |"
                )
        stage_header = "| Stage | Resources | Efforts (h) | Leave (h) | Calc days |"
        stage_sep = "|-------|-----------|-------------|-----------|-----------|"

        def _render_stage_table(stage_rows: list[dict[str, Any]]) -> None:
            lines.append(stage_header)
            lines.append(stage_sep)
            for row in stage_rows:
                calc = row.get("calculatedDays")
                calc_s = str(calc) if calc is not None else "—"
                src = row.get("source")
                stage_label = row.get("stage", "")
                if src == "synthetic":
                    stage_label = f"{stage_label} (est.)"
                combined_leave = (row.get("plannedLeaveHours") or 0) + (
                    row.get("unplannedDelayHours") or 0
                )
                lines.append(
                    f"| {escape_md_cell(stage_label)} | "
                    f"{fmt_resources(row.get('resources'))} | "
                    f"{fmt_hours(row.get('effortsHours'))} | "
                    f"{fmt_hours(combined_leave or None)} | "
                    f"{calc_s} |"
                )
            lines.append("")

        platform_blocks = [
            (label, exec_stages.get(plat_key))
            for plat_key, label in (
                ("backend", "Backend"),
                ("frontend", "Web"),
                ("mobile", "Mobile"),
            )
        ]
        active_platforms = [
            (label, block)
            for label, block in platform_blocks
            if block and block.get("hasWork") and block.get("stages")
        ]

        if active_platforms:
            lines.append("")
            lines.append("#### Execution stages")
            lines.append("")
            for label, block in active_platforms:
                lines.append(f"**{label}**")
                lines.append("")
                _render_stage_table(block["stages"])

        unmapped = epic.get("unmapped") or []
        if unmapped:
            if lines and lines[-1] != "":
                lines.append("")
            lines.append("#### Unmapped sprint work")
            lines.append("")
            for u in unmapped:
                key_link = jira_issue_link(jira_site_url, u.get("key"))
                summary = escape_md_cell(u.get("summary", ""))
                hrs = fmt_hours(u.get("effortsHours"))
                lines.append(f"- {key_link}: {summary} ({hrs} h)")
            lines.append("")

    return lines


def render_bug_sections(
    bug_data: list[dict[str, Any]],
    jira_site_url: str | None,
) -> list[str]:
    if not bug_data:
        return []

    header_sides = " | ".join(BUG_FIX_SIDE_COLUMNS)
    sep_sides = "|".join(["-----"] * len(BUG_FIX_SIDE_COLUMNS))
    lines = [
        "## Bug fix effort",
        "",
        "Jira **Bug** issues — worklog **time spent** (h) by epic and team side. "
        "Each bug counts once on its team's side; columns reconcile to **Total**.",
        "",
        f"| Epic ID | Epic Name | {header_sides} | Total | Bugs |",
        f"|---------|-----------|{sep_sides}|-------|------|",
    ]

    col_totals = {col: 0.0 for col in BUG_FIX_SIDE_COLUMNS}
    grand_total = 0.0
    for epic in bug_data:
        epic_key = epic.get("epicKey", "")
        prd = escape_md_cell(epic.get("prdName") or epic_key)
        epic_id = jira_issue_link(jira_site_url, epic_key)
        side_hours = epic.get("sideHours") or {}
        cells = []
        for col in BUG_FIX_SIDE_COLUMNS:
            h = side_hours.get(col, 0) or 0
            col_totals[col] += h
            cells.append(fmt_hours(h) if h else "—")
        total = epic.get("totalBugHours")
        grand_total += total or 0
        bug_n = epic.get("bugCount", 0)
        lines.append(
            f"| {epic_id} | {prd} | {' | '.join(cells)} | {fmt_hours(total)} | {bug_n} |"
        )

    lines.append("")
    side_summary = ", ".join(
        f"{col} {fmt_hours(round(col_totals[col], 1))}" for col in BUG_FIX_SIDE_COLUMNS
    )
    lines.append(
        f"**Sprint bug effort total:** {fmt_hours(round(grand_total, 1))} h ({side_summary})"
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
                f"{fmt_hours(m.get('effortsHours'))} | {m.get('bugCount', 0)} |"
            )
        lines.append("")

    return lines


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

    members: list[tuple[str, list, list]] = []
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


def render_data_quality_section(
    by_member: dict[str, list[dict[str, str]]],
    jira_site_url: str | None,
) -> list[str]:
    lines = [
        "## Data quality flags",
        "",
        "Issues by assignee that need cleanup before planning is reliable. "
        "Task start/due in reports are **calculated** from estimates — not read from Jira. "
        "Bugs in To Do / In Progress / Hold / Deferred are not flagged for missing time; "
        "Not a Bug and similar rejected statuses skip worklog checks; "
        "other resolved bugs must have worklog time logged.",
        "",
    ]
    total_rows = sum(len(rows) for rows in by_member.values())
    if total_rows == 0:
        lines.append("No data-quality issues detected for sprint work items.")
        lines.append("")
        return lines

    lines.append(f"**Total flagged tickets:** {total_rows} across {len(by_member)} members")
    lines.append("")

    reason_counts = count_dq_reasons(by_member)
    if reason_counts:
        lines.append("| Reason | Count |")
        lines.append("|--------|-------|")
        for reason in sorted(reason_counts.keys()):
            lines.append(f"| {escape_md_cell(reason)} | {reason_counts[reason]} |")
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


def render_schedule_delta_section(
    delta: dict[str, list[dict[str, Any]]],
    jira_site_url: str | None,
) -> list[str]:
    if not delta_has_changes(delta):
        return []

    lines = [
        "## Schedule Delta",
        "",
        "Changes vs prior schedule snapshot (`prior-schedule.json`).",
        "",
    ]

    def add_table(title: str, rows: list[dict[str, Any]], headers: list[str], fmt_row) -> None:
        if not rows:
            return
        lines.append(f"### {title} ({len(rows)})")
        lines.append("")
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
        for row in rows:
            lines.append(fmt_row(row))
        lines.append("")

    add_table(
        "Newly scheduled",
        delta.get("newly_scheduled") or [],
        ["Ticket", "Start", "Due", "Status"],
        lambda r: (
            f"| {jira_issue_link(jira_site_url, r['key'])} | {r.get('startDate', '—')} | "
            f"{r.get('dueDate', '—')} | {r.get('status', '—')} |"
        ),
    )
    add_table(
        "Newly unscheduled",
        delta.get("newly_unscheduled") or [],
        ["Ticket", "Prior start", "Prior due", "Reason"],
        lambda r: (
            f"| {jira_issue_link(jira_site_url, r['key'])} | {r.get('priorStart', '—')} | "
            f"{r.get('priorDue', '—')} | {r.get('reason', '—')} |"
        ),
    )
    add_table(
        "Date changes",
        delta.get("date_changes") or [],
        ["Ticket", "Prior start", "Prior due", "New start", "New due"],
        lambda r: (
            f"| {jira_issue_link(jira_site_url, r['key'])} | {r.get('priorStart', '—')} | "
            f"{r.get('priorDue', '—')} | {r.get('startDate', '—')} | {r.get('dueDate', '—')} |"
        ),
    )
    add_table(
        "Status changes",
        delta.get("status_changes") or [],
        ["Ticket", "Prior status", "New status"],
        lambda r: (
            f"| {jira_issue_link(jira_site_url, r['key'])} | {r.get('priorStatus', '—')} | "
            f"{r.get('status', '—')} |"
        ),
    )

    return lines


def render_recommended_actions(
    quality_by_member: dict[str, list[dict[str, str]]],
) -> list[str]:
    lines = ["## Recommended actions", ""]
    reason_counts = count_dq_reasons(quality_by_member)
    missing_est_n = reason_counts.get(REASON_MISSING_ESTIMATE, 0)
    missing_log_n = reason_counts.get(REASON_MISSING_LOGGED_TIME, 0)
    n = 1
    if missing_est_n:
        lines.append(
            f"{n}. Add Original Estimate on {missing_est_n} task(s) missing estimates "
            "(Jira start/due not required)."
        )
        n += 1
    if missing_log_n:
        lines.append(
            f"{n}. Log work time on {missing_log_n} bug(s) past active workflow states."
        )
        n += 1
    lines.append(f"{n}. Review delayed/at-risk epics before sprint end.")
    lines.append("")
    return lines
