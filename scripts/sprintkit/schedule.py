"""Deterministic per-assignee sprint scheduler (8h/day, business days)."""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any


def parse_date(value: str) -> date:
    return date.fromisoformat(value[:10])


def is_working_day(d: date, working_days: set[int]) -> bool:
    return d.weekday() in working_days


def next_working_day(d: date, working_days: set[int]) -> date:
    n = d + timedelta(days=1)
    while not is_working_day(n, working_days):
        n += timedelta(days=1)
    return n


def add_business_days(start: date, days: int, working_days: set[int]) -> date:
    if days <= 1:
        return start
    current = start
    remaining = days - 1
    while remaining > 0:
        current = next_working_day(current, working_days)
        remaining -= 1
    return current


def duration_days(estimate_seconds: int, hours_per_day: int) -> int:
    if estimate_seconds <= 0:
        return 0
    seconds_per_day = hours_per_day * 3600
    return max(1, math.ceil(estimate_seconds / seconds_per_day))


def sort_key(item: dict[str, Any]) -> tuple:
    return (
        item.get("epicPriorityRank", 999),
        item.get("storyRank", 999),
        item.get("created", ""),
        item.get("key", ""),
    )


def classify_status(
    due: date,
    sprint_end: date,
    today: date,
    blocked: bool,
    has_estimate: bool,
) -> str:
    if blocked:
        return "blocked"
    if not has_estimate:
        return "at_risk"
    if due > sprint_end:
        return "delayed"
    # due <= sprint_end: at_risk within ~2 days of sprint end, else by overdue/on_track
    if due >= sprint_end - timedelta(days=2):
        return "at_risk"
    if today > due:
        return "delayed"
    return "on_track"


def compute_schedule(data: dict[str, Any]) -> dict[str, Any]:
    sprint_start = parse_date(data["sprintStart"])
    sprint_end = parse_date(data["sprintEnd"])
    today = parse_date(data.get("today", date.today().isoformat()))
    hours_per_day = int(data.get("hoursPerDay", 8))
    working_days = set(data.get("workingDays", [0, 1, 2, 3, 4]))
    items: list[dict[str, Any]] = data.get("items", [])

    scheduled_keys: dict[str, dict[str, Any]] = {}
    by_assignee: dict[str, list[dict[str, Any]]] = {}
    unscheduled: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []

    for item in items:
        assignee = item.get("assignee") or "unassigned"
        by_assignee.setdefault(assignee, []).append(item)

    for assignee, queue in by_assignee.items():
        queue.sort(key=sort_key)
        prev_end: date | None = None

        for item in queue:
            est = int(item.get("estimateSeconds") or 0)
            blocked = bool(item.get("blocked", False))

            if est <= 0 and not blocked:
                unscheduled.append({"key": item["key"], "reason": "missing_estimate"})
                continue

            dur = duration_days(est, hours_per_day)

            start = sprint_start
            if prev_end is not None:
                start = max(start, next_working_day(prev_end, working_days))

            for dep in item.get("dependencies") or []:
                dep_key = dep.get("dependsOnKey")
                if dep_key and dep_key in scheduled_keys:
                    dep_due = parse_date(scheduled_keys[dep_key]["dueDate"])
                    dep_start = next_working_day(dep_due, working_days)
                    if start < dep_start:
                        start = dep_start
                # If dependency is not scheduled (e.g. missing estimate), skip constraint
                # — do not flag a violation; teams are not required to set Jira dates.

            if not is_working_day(start, working_days):
                while not is_working_day(start, working_days):
                    start += timedelta(days=1)

            due = add_business_days(start, dur, working_days) if dur > 0 else start
            status = classify_status(due, sprint_end, today, blocked, est > 0)

            entry = {
                "key": item["key"],
                "storyKey": item.get("storyKey"),
                "epicKey": item.get("epicKey"),
                "assignee": assignee,
                "startDate": start.isoformat(),
                "dueDate": due.isoformat(),
                "durationDays": dur,
                "status": status,
                "dependencyNotes": [],
            }
            scheduled_keys[item["key"]] = entry
            prev_end = due

    return {
        "scheduled": list(scheduled_keys.values()),
        "violations": violations,
        "unscheduled": unscheduled,
    }
