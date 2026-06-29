"""Normalize Jira issues into schedule-engine input (per-assignee work items)."""

from __future__ import annotations

from datetime import date
from typing import Any

from sprintkit.config import DEFAULT_PRIORITY, SCHEDULABLE_TYPES
from sprintkit.jira_model import (
    assignee_id,
    build_index,
    effective_estimate_seconds,
    get_field,
    is_blocked,
    is_epic,
    issue_type_name,
    priority_rank,
    resolve_epic,
    resolve_story,
    task_has_subtasks,
)
from sprintkit.teams import team_from_issue


def normalize(
    issues: list[dict[str, Any]],
    config: dict[str, Any],
    sprint_start: str,
    sprint_end: str,
    today: str | None = None,
) -> dict[str, Any]:
    index = build_index(issues)
    priority_order = config.get("priorityOrder") or DEFAULT_PRIORITY
    teams_cfg = config.get("teams") or {}
    scheduling = config.get("scheduling") or {}

    items: list[dict[str, Any]] = []
    story_rank_counter = 0
    story_ranks: dict[str, int] = {}

    for issue in issues:
        t = issue_type_name(issue)
        if t not in SCHEDULABLE_TYPES:
            continue

        issue_key = issue.get("key") or ""
        if t == "task" and task_has_subtasks(issue_key, index):
            continue

        story = resolve_story(issue, index)
        epic = resolve_epic(issue, index)
        story_key = story.get("key") if story else None
        epic_key = epic.get("key") if epic else None

        if story_key and story_key not in story_ranks:
            story_rank_counter += 1
            story_ranks[story_key] = story_rank_counter

        epic_priority = None
        if epic:
            epic_priority = (get_field(epic, "priority") or {}).get("name")

        team = team_from_issue(issue, teams_cfg, config)

        items.append(
            {
                "key": issue.get("key"),
                "storyKey": story_key,
                "epicKey": epic_key,
                "assignee": assignee_id(issue),
                "estimateSeconds": effective_estimate_seconds(issue, config),
                "epicPriorityRank": priority_rank(epic_priority, priority_order),
                "storyRank": story_ranks.get(story_key or "", 999),
                "team": team,
                "created": get_field(issue, "created") or "",
                "blocked": is_blocked(issue),
                "dependencies": [],
            }
        )

    return {
        "sprintStart": sprint_start,
        "sprintEnd": sprint_end,
        "hoursPerDay": scheduling.get("hoursPerDay", 8),
        "workingDays": scheduling.get("workingDayInts", [0, 1, 2, 3, 4]),
        "today": today or date.today().isoformat(),
        "items": items,
    }
