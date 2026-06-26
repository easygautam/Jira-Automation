"""Deterministic chat summaries for sprint and epic workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sprintkit.epic_pipeline import EpicEstimationResult
from sprintkit.pipeline import PipelineResult
from sprintkit.render.markdown import fmt_date, fmt_date_range


def sprint_report_summary(
    result: PipelineResult,
    report_path: str | Path,
    *,
    jira_site_url: str | None = None,
) -> str:
    """Fixed-format summary after a sprint report run."""
    sprint = result.sprint_meta
    window = fmt_date_range(
        sprint.get("sprintStart", ""),
        sprint.get("sprintEnd", ""),
    )
    counts = result.status_counts
    lines = [
        f"Sprint report — {sprint.get('sprintName', 'Active Sprint')}",
        f"Sprint window: {window}",
        "",
        "Status:",
        f"- on_track: {counts.get('on_track', 0)}",
        f"- at_risk: {counts.get('at_risk', 0)}",
        f"- delayed: {counts.get('delayed', 0)}",
        f"- blocked: {counts.get('blocked', 0)}",
        "",
        f"Scheduled: {len(result.schedule.get('scheduled', []))} · "
        f"Unscheduled: {len(result.schedule.get('unscheduled', []))}",
        f"Report: {Path(report_path).resolve()}",
    ]
    if result.warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {w}" for w in result.warnings[:5])
    if jira_site_url:
        lines.extend(["", f"Jira: {jira_site_url.rstrip('/')}"])
    return "\n".join(lines) + "\n"


def epic_estimation_summary(
    result: EpicEstimationResult,
    *,
    canvas_path: str | Path | None = None,
    slack_permalink: str | None = None,
) -> str:
    """Fixed-format summary after epic estimation."""
    lines = [
        f"Epic estimation — {result.epic_key}",
        result.prd_name,
        "",
        f"Delivery start: {fmt_date(result.delivery_start) or '—'}",
        f"Go-live: {fmt_date(result.go_live) or '—'}",
    ]
    if result.warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {w}" for w in result.warnings[:5])
    if canvas_path:
        lines.extend(["", f"Canvas: {Path(canvas_path).resolve()}"])
    if slack_permalink:
        lines.extend(["", f"Slack: {slack_permalink}"])
    return "\n".join(lines) + "\n"
