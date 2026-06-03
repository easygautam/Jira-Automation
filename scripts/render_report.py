#!/usr/bin/env python3
"""Render sprint report markdown from schedule + issues JSON."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATUS_RANK = {"blocked": 0, "delayed": 1, "at_risk": 2, "on_track": 3, "tbd": 4}


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

        lines.append(f"### {epic_link} — {prd}")
        lines.append(
            f"- Delivery window: {d_start} → {d_end} | Go live: {go_live}{cal_s}"
        )
        lines.append("")
        lines.append("#### Members by side")
        lines.append("")
        lines.append(
            "| Side | Peak resources | Total effort (h) | Planned leave (h) | "
            "Unplanned delay (h) | Tasks |"
        )
        lines.append(
            "|------|------------------|------------------|-------------------|"
            "---------------------|-------|"
        )
        for side, summary in sorted((epic.get("teamSummary") or {}).items()):
            lines.append(
                f"| {side} | {_fmt_resources(summary.get('peakResources'))} | "
                f"{_fmt_hours(summary.get('totalEffortHours'))} | "
                f"{_fmt_hours(summary.get('totalLeaveHours'))} | "
                f"{_fmt_hours(summary.get('totalDelayHours'))} | "
                f"{summary.get('taskCount', 0)} |"
            )
        members_by_side = epic.get("membersBySide") or {}
        for side in sorted(members_by_side.keys()):
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
                f"| {escape_md_cell(row.get('task', ''))} | {row.get('team', '')} | "
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
        "Jira **Bug** issue type only (`timeoriginalestimate`). Grouped by epic and assignee.",
        "",
    ]

    grand_total = sum(e.get("totalBugHours") or 0 for e in bug_data)
    lines.append(
        f"**Sprint bug effort total:** {_fmt_hours(grand_total)} h across {len(bug_data)} epics"
    )
    lines.append("")

    for epic in bug_data:
        epic_key = epic.get("epicKey", "")
        prd = escape_md_cell(epic.get("prdName") or epic_key)
        epic_link = jira_issue_link(jira_site_url, epic_key)
        lines.append(f"### {epic_link} — {prd}")
        lines.append(
            f"- Bug issues: {epic.get('bugCount', 0)} | "
            f"Total estimate: {_fmt_hours(epic.get('totalBugHours'))} h"
        )
        lines.append("")

        by_side = epic.get("bySide") or {}
        if by_side:
            lines.append("#### By side")
            lines.append("")
            lines.append("| Side | Members | Total effort (h) |")
            lines.append("|------|---------|------------------|")
            for side, summary in sorted(by_side.items()):
                members_s = ", ".join(summary.get("members") or [])
                lines.append(
                    f"| {escape_md_cell(side)} | {escape_md_cell(members_s)} | "
                    f"{_fmt_hours(summary.get('totalEffortHours'))} |"
                )
            lines.append("")

        lines.append("#### By member")
        lines.append("")
        lines.append("| Member | Side | Effort (h) | Bugs | Start | End |")
        lines.append("|--------|------|------------|------|-------|-----|")
        for m in epic.get("members") or []:
            issues = m.get("issues") or []
            starts = [i["start"] for i in issues if i.get("start")]
            ends = [i["end"] for i in issues if i.get("end")]
            start = min(starts) if starts else None
            end = max(ends) if ends else None
            lines.append(
                f"| {escape_md_cell(m.get('member', ''))} | {m.get('side', '')} | "
                f"{_fmt_hours(m.get('effortsHours'))} | {m.get('issueCount', 0)} | "
                f"{_fmt_date(start)} | {_fmt_date(end)} |"
            )
        lines.append("")
        lines.append("#### Bug issues")
        lines.append("")
        for m in epic.get("members") or []:
            lines.append(f"**{escape_md_cell(m.get('member', ''))}** ({m.get('side', '')})")
            lines.append("")
            for item in m.get("issues") or []:
                key_link = jira_issue_link(jira_site_url, item.get("key"))
                summary = escape_md_cell(item.get("summary", ""))
                hrs = _fmt_hours(item.get("effortsHours"))
                window = f"{_fmt_date(item.get('start'))} → {_fmt_date(item.get('end'))}"
                status = item.get("status") or "—"
                side = item.get("side") or "—"
                lines.append(
                    f"- {key_link} ({side}): {summary} — {hrs} h — {window} — {status}"
                )
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
    violations = schedule.get("violations", [])

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

    lines.append("## Delivery items (Epics)")
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
        epic_summary = escape_md_cell(resolve_epic_summary(epic_key, issues, issue_by_key))
        epic_link = jira_issue_link(jira_site_url, epic_key)
        rollup = compute_epic_rollup(epic_key, scheduled, unscheduled, engine_items)
        phase = phase_for_epic(epic_key, issues, status_map)
        start_s = rollup["start"] or "TBD"
        due_s = rollup["due"] or "TBD"
        status_s = rollup["status"] if rollup["status"] != "tbd" else "TBD"
        lines.append(
            f"| {epic_link} | {epic_summary} | {start_s} | {due_s} | {phase} | {status_s} "
            f"| {rollup['scheduled_count']} | {rollup['unscheduled_count']} |"
        )

    lines.append("")
    if timeline:
        lines.extend(render_timeline_sections(timeline, jira_site_url))
    if bug_effort:
        lines.extend(render_bug_sections(bug_effort, jira_site_url))
    lines.append("## Schedule by assignee")
    lines.append("")

    for assignee_id, rows in sorted(by_assignee.items(), key=lambda x: assignee_names.get(x[0], x[0])):
        display = assignee_names.get(assignee_id, assignee_id)
        lines.append(f"### {display}")
        lines.append("")
        lines.append("| Key | Story | Epic | Effort | Start | Due | Status | Notes |")
        lines.append("|-----|-------|------|--------|-------|-----|--------|-------|")
        for r in rows:
            issue = issue_by_key.get(r["key"], {})
            summary = (issue.get("fields") or {}).get("summary", "")[:40]
            notes = "; ".join(r.get("dependencyNotes") or []) or summary
            key_link = jira_issue_link(jira_site_url, r["key"])
            story_link = jira_issue_link(jira_site_url, r.get("storyKey"))
            epic_col = jira_issue_link(jira_site_url, r.get("epicKey"))
            lines.append(
                f"| {key_link} | {story_link} | {epic_col} "
                f"| {format_effort(est_by_key.get(r['key']))} | {r['startDate']} | {r['dueDate']} "
                f"| {r['status']} | {notes} |"
            )
        lines.append("")

    lines.append("## Data quality flags")
    lines.append("")
    missing = [u["key"] for u in unscheduled if u.get("reason") == "missing_estimate"]
    lines.append(f"- Missing estimates: {', '.join(missing[:30])}{'…' if len(missing) > 30 else ''}")
    lines.append(f"- Unscheduled count: {len(unscheduled)}")
    if violations:
        lines.append(f"- Dependency violations: {len(violations)}")
        for v in violations[:10]:
            lines.append(f"  - {v.get('key')}: {v.get('issue')}")
    else:
        lines.append("- Dependency violations: none")

    lines.append("")
    lines.append("## Recommended actions")
    lines.append("")
    if missing:
        lines.append(f"1. Add Original Estimate on {len(missing)} unscheduled items before planning sign-off.")
    lines.append("2. Review delayed/at-risk epics and tasks before sprint end.")
    lines.append("3. Ensure backend API tasks complete before dependent Mobile/Web/QA work.")
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

    jira_site_url = args.jira_site_url
    if not jira_site_url and Path(args.config).exists():
        try:
            import yaml

            cfg = yaml.safe_load(Path(args.config).read_text()) or {}
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
