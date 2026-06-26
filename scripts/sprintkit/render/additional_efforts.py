"""Build platform-grouped Additional efforts table rows from unmapped timeline items."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sprintkit.render.markdown import (
    escape_md_cell,
    fmt_hours,
    fmt_hours_with_unit,
    jira_issue_keys_linked,
)
from sprintkit.timeline import TEAM_PLAN_SIDES


def build_additional_efforts_rows(
    unmapped: list[dict[str, Any]],
    *,
    jira_site_url: str | None,
    team_order: tuple[str, ...] = tuple(TEAM_PLAN_SIDES),
    link_keys: Any | None = None,
) -> list[dict[str, Any]]:
    """
    Aggregate unmapped items into team rows.

    Returns [{team, effortHours, details}] where details lists member groups:
    ``Name (Nh) - linked keys``. Pass ``link_keys(site, keys)`` to customize
    key formatting (e.g. Slack ``<url|KEY>``).
    """
    if not unmapped:
        return []

    if link_keys is None:
        link_keys = jira_issue_keys_linked

    by_team: dict[str, dict[str, dict[str, Any]]] = defaultdict(
        lambda: defaultdict(lambda: {"hours": 0.0, "keys": []})
    )

    for item in unmapped:
        team = item.get("team") or "Other"
        member = item.get("assignee") or "Unassigned"
        hours = float(item.get("effortsHours") or 0)
        key = item.get("key")
        bucket = by_team[team][member]
        bucket["hours"] += hours
        if key:
            bucket["keys"].append(key)

    def _emit_rows() -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        ordered = list(team_order) + [
            t for t in sorted(by_team.keys()) if t not in team_order
        ]
        for team in ordered:
            if team in seen or team not in by_team:
                continue
            members = by_team[team]
            total_hours = sum(m["hours"] for m in members.values())
            if total_hours <= 0:
                continue
            seen.add(team)
            detail_parts: list[str] = []
            for member in sorted(
                members.keys(), key=lambda m: (m == "Unassigned", m.lower())
            ):
                data = members[member]
                if data["hours"] <= 0 and not data["keys"]:
                    continue
                keys_linked = link_keys(jira_site_url, data["keys"])
                detail_parts.append(
                    f"{member} ({fmt_hours_with_unit(data['hours'])}) - {keys_linked}"
                )
            out.append(
                {
                    "team": team,
                    "effortHours": round(total_hours, 2),
                    "details": "; ".join(detail_parts),
                }
            )
        return out

    return _emit_rows()


def render_additional_efforts_markdown(
    unmapped: list[dict[str, Any]],
    *,
    jira_site_url: str | None,
    heading: str = "## Additional efforts",
    team_order: tuple[str, ...] = tuple(TEAM_PLAN_SIDES),
) -> list[str]:
    """Return markdown lines for the Additional efforts table (empty if no rows)."""
    rows = build_additional_efforts_rows(
        unmapped, jira_site_url=jira_site_url, team_order=team_order
    )
    if not rows:
        return []

    lines = ["", heading, "", "| Team | Effort (h) | Details |", "|------|------------|---------|"]
    for row in rows:
        lines.append(
            f"| {escape_md_cell(row['team'])} | {fmt_hours(row['effortHours'])} | "
            f"{row['details']} |"
        )
    return lines
