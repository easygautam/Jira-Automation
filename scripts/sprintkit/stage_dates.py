"""Compute per-platform stage Start/End dates for epic estimation."""

from __future__ import annotations

import math
from datetime import date
from typing import Any

from sprintkit.jira_model import (
    build_index,
    get_field,
    is_epic_issue,
    issue_type_name,
    jira_start_date,
)
from sprintkit.schedule import add_business_days, is_working_day, next_working_day
from sprintkit.stages import (
    PLATFORM_KEYS,
    STAGE_DEVELOPMENT,
    STAGE_GO_LIVE,
    STAGE_TECH_SOLUTIONING,
)

_START_ANCHOR_TYPES = frozenset({"task", "sub-task", "subtask", "story"})


def _working_days(config: dict[str, Any]) -> set[int]:
    scheduling = config.get("scheduling") or {}
    return set(scheduling.get("workingDayInts", [0, 1, 2, 3, 4]))


def _start_anchor_keys(
    issue_keys: list[str],
    index: dict[str, dict[str, Any]],
) -> list[str]:
    """Expand issue keys with Task/Story ancestors (stop at Epic)."""
    keys: set[str] = set()
    for key in issue_keys:
        if not key:
            continue
        current = index.get(key)
        if not current:
            continue
        keys.add(key)
        while current:
            parent = get_field(current, "parent")
            if not parent or not parent.get("key"):
                break
            pk = parent["key"]
            parent_issue = index.get(pk)
            if not parent_issue:
                break
            if is_epic_issue(parent_issue):
                break
            if issue_type_name(parent_issue).lower() in _START_ANCHOR_TYPES:
                keys.add(pk)
            current = parent_issue
    return list(keys)


def _min_jira_start(
    issue_keys: list[str],
    index: dict[str, dict[str, Any]],
    config: dict[str, Any],
) -> date | None:
    dates: list[date] = []
    for key in _start_anchor_keys(issue_keys, index):
        issue = index.get(key)
        if not issue:
            continue
        parsed = jira_start_date(issue, config)
        if parsed:
            dates.append(parsed)
    return min(dates) if dates else None


def _stage_end(
    start: date | None, calc_days: float | None, working_days: set[int]
) -> date | None:
    if not start:
        return None
    if calc_days is None or calc_days <= 0:
        return start
    # Sub-day effort stays on one calendar day; multi-day uses whole business days.
    if calc_days < 1:
        return start
    duration = math.ceil(calc_days)
    return add_business_days(start, duration, working_days)


def _effective_calc_days(stage_row: dict[str, Any], hours_per_day: float = 6.0) -> float | None:
    """Resolve calc days, defaulting to 1 resource for synthetic effort-only stages."""
    calc = stage_row.get("calculatedDays")
    if calc is not None:
        return float(calc)
    efforts = stage_row.get("effortsHours")
    if efforts is None or float(efforts) <= 0:
        return None
    resources = stage_row.get("resources")
    res = float(resources) if resources else 1.0
    if res <= 0:
        res = 1.0
    leave = (stage_row.get("plannedLeaveHours") or 0) + (
        stage_row.get("unplannedDelayHours") or 0
    )
    total = float(efforts) + float(leave)
    return round(total / (res * hours_per_day), 2)


def _chain_start(
    prior_end: date,
    prior_calc_days: float | None,
    working_days: set[int],
) -> date:
    """Next stage start: same day if prior was sub-day, else next business day."""
    if prior_calc_days is not None and prior_calc_days < 1:
        return prior_end
    return next_working_day(prior_end, working_days)


def _stage_has_work(stage_row: dict[str, Any]) -> bool:
    """True when the stage has mapped Jira tasks or non-zero effort."""
    if stage_row.get("issueKeys"):
        return True
    efforts = stage_row.get("effortsHours")
    return efforts is not None and float(efforts) > 0


def _business_days_apart(earlier: date, later: date, working_days: set[int]) -> int:
    """Working days in (earlier, later] when later > earlier."""
    if later <= earlier:
        return 0
    count = 0
    current = next_working_day(earlier, working_days)
    while current <= later:
        if is_working_day(current, working_days):
            count += 1
        if current >= later:
            break
        current = next_working_day(current, working_days)
    return count


def signed_business_day_gap(from_date: date, to_date: date, working_days: set[int]) -> float:
    """Signed business-day gap from from_date to to_date (FE end relative to BE end)."""
    if to_date == from_date:
        return 0.0
    if to_date > from_date:
        return float(_business_days_apart(from_date, to_date, working_days))
    return -float(_business_days_apart(to_date, from_date, working_days))


def backend_verification_required_days(
    stage_row: dict[str, Any],
    buffers: dict[str, Any],
    hours_per_day: float,
) -> float | None:
    efforts = stage_row.get("effortsHours")
    if efforts is None or float(efforts) <= 0:
        return None
    pct = float(buffers.get("backendVerificationPercentOfFeDevelopment", 0.15))
    max_days = float(buffers.get("backendVerificationMaxDays", 2))
    required_hours = min(float(efforts) * pct, max_days * hours_per_day)
    # Verification is calendar time on the platform, not split across dev resources.
    return round(required_hours / hours_per_day, 2)


def _extend_by_buffer_days(
    end: date, buffer_days: float, working_days: set[int]
) -> date:
    if buffer_days <= 0:
        return end
    steps = 1 if buffer_days < 1 else math.ceil(buffer_days)
    current = end
    for _ in range(steps):
        current = next_working_day(current, working_days)
    return current


def _apply_backend_verification_buffer(
    stage_row: dict[str, Any],
    end: date | None,
    be_development_end: date | None,
    buffers: dict[str, Any],
    hours_per_day: float,
    working_days: set[int],
) -> date | None:
    """Extend Web/Mobile Development end when post-BE verification window is too short."""
    if end is None or be_development_end is None:
        return end
    required_days = backend_verification_required_days(stage_row, buffers, hours_per_day)
    if required_days is None:
        return end
    remaining_days = signed_business_day_gap(be_development_end, end, working_days)
    if remaining_days >= required_days:
        stage_row.pop("backendVerificationBufferDays", None)
        stage_row.pop("backendVerificationRequiredDays", None)
        return end
    buffer_days = round(required_days - remaining_days, 2)
    stage_row["backendVerificationRequiredDays"] = required_days
    stage_row["backendVerificationBufferDays"] = buffer_days
    return _extend_by_buffer_days(end, buffer_days, working_days)


def compute_stage_dates(
    epic_row: dict[str, Any],
    issues: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Attach start/end on each stage row and epic-level deliveryStart/goLive."""
    index = build_index(issues)
    working_days = _working_days(config)
    exec_stages = epic_row.get("executionStages") or {}
    timeline_cfg = config.get("timeline") or {}
    hours_per_day = float(timeline_cfg.get("hoursPerDay", 6))
    buffers = timeline_cfg.get("effortBuffers") or {}

    all_starts: list[date] = []
    all_ends: list[date] = []
    go_live: date | None = None
    be_development_end: date | None = None

    # Backend first so BE Development end is available for Web/Mobile verification buffer.
    for platform in PLATFORM_KEYS:
        block = exec_stages.get(platform) or {}
        stages = block.get("stages") or []
        prior_end: date | None = None
        prior_calc_days: float | None = None

        for stage_row in stages:
            stage_name = stage_row.get("stage", "")
            if not _stage_has_work(stage_row):
                stage_row["start"] = None
                stage_row["end"] = None
                continue

            calc_days = _effective_calc_days(stage_row, hours_per_day)
            if stage_row.get("calculatedDays") is None and calc_days is not None:
                stage_row["calculatedDays"] = calc_days
            issue_keys = stage_row.get("issueKeys") or []
            start: date | None = None

            if stage_name == STAGE_TECH_SOLUTIONING:
                start = _min_jira_start(issue_keys, index, config)
            elif stage_name == STAGE_DEVELOPMENT:
                start = _min_jira_start(issue_keys, index, config)
            else:
                if prior_end is not None:
                    start = _chain_start(prior_end, prior_calc_days, working_days)
                jira_anchor = _min_jira_start(issue_keys, index, config) if issue_keys else None
                if jira_anchor is not None:
                    start = max(start, jira_anchor) if start is not None else jira_anchor

            end = _stage_end(start, calc_days, working_days)
            if (
                stage_name == STAGE_DEVELOPMENT
                and platform in ("frontend", "mobile")
            ):
                end = _apply_backend_verification_buffer(
                    stage_row,
                    end,
                    be_development_end,
                    buffers,
                    hours_per_day,
                    working_days,
                )
            stage_row["start"] = start.isoformat() if start else None
            stage_row["end"] = end.isoformat() if end else None

            if start:
                all_starts.append(start)
            if end:
                all_ends.append(end)
            if stage_name == STAGE_GO_LIVE and end:
                go_live = end

            if stage_name == STAGE_DEVELOPMENT and platform == "backend" and end:
                be_development_end = end

            prior_end = end if end else prior_end
            prior_calc_days = calc_days if calc_days is not None else prior_calc_days

    epic_row["deliveryStart"] = min(all_starts).isoformat() if all_starts else None
    epic_row["deliveryEnd"] = max(all_ends).isoformat() if all_ends else None
    epic_row["goLive"] = (
        go_live.isoformat()
        if go_live
        else (max(all_ends).isoformat() if all_ends else None)
    )
    return epic_row
