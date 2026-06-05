"""Step 1 — extract the active sprint window from the Jira sprint field."""

from __future__ import annotations

from typing import Any


def parse_date(value: str | None) -> str | None:
    if not value:
        return None
    return value[:10]


def sprint_field_value(fields: dict[str, Any], field_id: str) -> list[dict[str, Any]]:
    raw = fields.get(field_id)
    if raw is None and field_id.startswith("customfield_"):
        raw = fields.get("sprint")
    if raw is None:
        return []
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if isinstance(raw, dict):
        return [raw]
    return []


def extract_active_sprint(
    issues: list[dict[str, Any]],
    sprint_field: str,
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for issue in issues:
        fields = issue.get("fields") or {}
        for sprint in sprint_field_value(fields, sprint_field):
            candidates.append(sprint)

    if not candidates:
        raise ValueError(
            f"No sprint data found in field '{sprint_field}'. "
            "Re-fetch issues including the Sprint field or run field discovery."
        )

    active = [s for s in candidates if (s.get("state") or "").lower() == "active"]
    pool = active if active else candidates

    def sort_key(s: dict[str, Any]) -> str:
        return s.get("startDate") or s.get("endDate") or ""

    chosen = max(pool, key=sort_key)
    start = parse_date(chosen.get("startDate"))
    end = parse_date(chosen.get("endDate"))

    if not start or not end:
        raise ValueError(
            f"Sprint '{chosen.get('name')}' missing startDate/endDate in field '{sprint_field}'."
        )

    return {
        "sprintId": chosen.get("id"),
        "sprintName": chosen.get("name"),
        "sprintStart": start,
        "sprintEnd": end,
        "state": chosen.get("state", "active"),
    }
