"""Epic estimation pipeline: single epic → timeline → stage dates → display payload."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sprintkit.config import config_warnings
from sprintkit.jira_model import epic_summary, filter_issues_for_epic, is_epic_issue
from sprintkit.quality import build_data_quality_by_member, count_dq_reasons
from sprintkit.render.epic_sections import build_epic_display_payload
from sprintkit.render.markdown import resolve_jira_site_url
from sprintkit.stage_dates import compute_stage_dates
from sprintkit.timeline import build_timeline_breakdown, check_timeline_team_consistency


@dataclass
class EpicEstimationResult:
    epic_key: str
    prd_name: str
    delivery_start: str | None
    go_live: str | None
    timeline: dict[str, Any]
    markdown: str
    canvas_data: dict[str, Any]
    warnings: list[str] = field(default_factory=list)
    data_quality: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    unmapped_count: int = 0


def run_epic_estimation(
    issues: list[dict[str, Any]],
    config: dict[str, Any],
    epic_key: str,
    *,
    project: str = "VP",
    jira_site_url: str | None = None,
) -> EpicEstimationResult:
    """Run effort mapping and stage date calculation for one epic."""
    epic_issues = filter_issues_for_epic(issues, epic_key)
    if not epic_issues:
        raise ValueError(f"No issues found for epic {epic_key}")

    has_epic = any(i.get("key") == epic_key and is_epic_issue(i) for i in epic_issues)
    if not has_epic:
        raise ValueError(f"Epic {epic_key} not present in fetched issues")

    empty_schedule: dict[str, Any] = {"scheduled": [], "unscheduled": []}
    timeline_list = build_timeline_breakdown(epic_issues, empty_schedule, config)
    epic_row = next((e for e in timeline_list if e.get("epicKey") == epic_key), None)
    if not epic_row:
        raise ValueError(f"Could not build timeline for epic {epic_key}")

    compute_stage_dates(epic_row, epic_issues, config)

    warnings = config_warnings(config)
    warnings.extend(check_timeline_team_consistency([epic_row]))

    site = resolve_jira_site_url(jira_site_url, config, epic_issues)
    prd_name = epic_summary(epic_key, epic_issues, {i["key"]: i for i in epic_issues if i.get("key")})
    quality = build_data_quality_by_member(
        epic_issues, empty_schedule, [epic_row], None, config
    )
    unmapped = epic_row.get("unmapped") or []

    payload = build_epic_display_payload(
        epic_key,
        prd_name,
        epic_row,
        quality,
        jira_site_url=site,
        project=project,
    )

    return EpicEstimationResult(
        epic_key=epic_key,
        prd_name=prd_name,
        delivery_start=epic_row.get("deliveryStart"),
        go_live=epic_row.get("goLive"),
        timeline=epic_row,
        markdown=payload["markdown"],
        canvas_data=payload["canvas"],
        warnings=warnings,
        data_quality=quality,
        unmapped_count=len(unmapped),
    )


def result_to_json(result: EpicEstimationResult) -> dict[str, Any]:
    """Serialize for CLI stdout."""
    dq_counts = count_dq_reasons(result.data_quality)
    return {
        "epicKey": result.epic_key,
        "prdName": result.prd_name,
        "deliveryStart": result.delivery_start,
        "goLive": result.go_live,
        "deliveryEnd": result.timeline.get("deliveryEnd"),
        "timeline": result.timeline,
        "markdown": result.markdown,
        "canvas": result.canvas_data,
        "warnings": result.warnings,
        "unmappedCount": result.unmapped_count,
        "dataQualityCounts": dq_counts,
    }
