"""Epic delivery-stage task setup: detect covered stages and plan skeleton creates."""

from __future__ import annotations

from typing import Any

from sprintkit.config import load_epic_setup_config, project_key_from_issue_key
from sprintkit.jira_model import (
    filter_issues_for_epic,
    get_field,
    is_epic,
    is_task_or_subtask,
)
from sprintkit.stages import (
    STAGE_DEVELOPMENT,
    STAGE_PREPROD,
    STAGE_PROD_FINAL_TESTING,
    STAGE_PROD_RELEASE,
    STAGE_QA_TEST_PLANNING,
    STAGE_STAGE_TESTING,
    STAGE_TECH_SOLUTIONING,
    STAGE_UAT,
    classify_issue,
)

PlatformKey = str
StageKey = str

DEFAULT_TASK_STAGES: dict[str, list[str]] = {
    "backend": [
        STAGE_TECH_SOLUTIONING,
        STAGE_QA_TEST_PLANNING,
        STAGE_DEVELOPMENT,
        STAGE_STAGE_TESTING,
        STAGE_PROD_RELEASE,
        STAGE_PROD_FINAL_TESTING,
    ],
    "mobile": [
        STAGE_TECH_SOLUTIONING,
        STAGE_QA_TEST_PLANNING,
        STAGE_DEVELOPMENT,
        STAGE_STAGE_TESTING,
        STAGE_PREPROD,
        STAGE_UAT,
    ],
    "frontend": [
        STAGE_TECH_SOLUTIONING,
        STAGE_QA_TEST_PLANNING,
        STAGE_DEVELOPMENT,
        STAGE_STAGE_TESTING,
        STAGE_PREPROD,
        STAGE_UAT,
    ],
}

_PLATFORM_PREFIX = {
    "backend": "BE",
    "mobile": "APP",
    "frontend": "WEB",
}

_QA_PLATFORM_PREFIX = {
    "backend": "BE",
    "mobile": "APP",
    "frontend": "WEB",
}

_DEV_DELIVERY_LABEL = {
    "backend": "backend delivery",
    "mobile": "mobile delivery",
    "frontend": "web delivery",
}


def stage_summary(platform: str, stage: str, epic_suffix: str) -> str:
    """Canonical task summary for a delivery stage (JIRA-BEST-PRACTICES pipe format)."""
    suffix = epic_suffix.strip()
    prefix = _PLATFORM_PREFIX.get(platform, platform.upper())
    qa_plat = _QA_PLATFORM_PREFIX.get(platform, prefix)

    if stage == STAGE_TECH_SOLUTIONING:
        return f"{prefix} | Assessment | {suffix}"
    if stage == STAGE_QA_TEST_PLANNING:
        return f"QA | {qa_plat} | Assessment | {suffix}"
    if stage == STAGE_DEVELOPMENT:
        label = _DEV_DELIVERY_LABEL.get(platform, "delivery")
        return f"{prefix} | {suffix} — {label}"
    if stage == STAGE_STAGE_TESTING:
        return f"QA | {qa_plat} | {suffix} — stage testing"
    if stage == STAGE_PREPROD:
        return f"QA | {qa_plat} | Pre-Prod | {suffix} — E2E testing"
    if stage == STAGE_UAT:
        return f"{prefix} | UAT | {suffix} — product sign-off"
    if stage == STAGE_PROD_RELEASE:
        return f"BE | Prod release | {suffix}"
    if stage == STAGE_PROD_FINAL_TESTING:
        return f"BE | Prod final testing | {suffix}"
    raise ValueError(f"Unsupported stage template: {platform}/{stage}")


def teams_role_for_stage(platform: str, stage: str) -> str:
    """Jira Teams field role key for epicSetup.projectDefaults.teamsByRole."""
    if stage in (
        STAGE_QA_TEST_PLANNING,
        STAGE_STAGE_TESTING,
        STAGE_PREPROD,
    ):
        return "qa"
    return platform


def scan_existing_stages(
    issues: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[tuple[PlatformKey, StageKey], list[str]]:
    """Map (platform, stage) to issue keys for work-classified Task/Sub-task issues."""
    timeline_cfg = (config.get("timeline") or {})
    teams_cfg = config.get("teams") or {}
    covered: dict[tuple[str, str], list[str]] = {}

    for issue in issues:
        if is_epic(issue) or not is_task_or_subtask(issue):
            continue
        result = classify_issue(
            issue, timeline_cfg, teams_cfg, config, epic_issues=issues
        )
        if result.get("kind") != "work":
            continue
        platform = result.get("platform")
        stage = result.get("stage")
        key = issue.get("key")
        if not platform or not stage or not key:
            continue
        bucket = covered.setdefault((platform, stage), [])
        if key not in bucket:
            bucket.append(key)

    return covered


def _epic_issue(issues: list[dict[str, Any]], epic_key: str) -> dict[str, Any] | None:
    for issue in issues:
        if issue.get("key") == epic_key:
            return issue
    return None


def _sprint_id_from_epic(epic_issue: dict[str, Any], config: dict[str, Any]) -> Any:
    fields_cfg = (config.get("fields") or {})
    sprint_field = fields_cfg.get("sprint", "customfield_10020")
    sprints = get_field(epic_issue, sprint_field) or []
    if not isinstance(sprints, list):
        return sprints
    for entry in reversed(sprints):
        if isinstance(entry, dict) and entry.get("state") == "active":
            return entry.get("id")
    if sprints and isinstance(sprints[-1], dict):
        return sprints[-1].get("id")
    return None


def jira_create_fields(
    task: dict[str, Any],
    epic_issue: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Build MCP createJiraIssue additional_fields (+ top-level parent/summary)."""
    epic_key = epic_issue.get("key") or ""
    project_key = project_key_from_issue_key(epic_key) or ""
    setup = load_epic_setup_config(config)
    project_defaults = (setup.get("projectDefaults") or {}).get(project_key) or {}

    teams_by_role = project_defaults.get("teamsByRole") or {}
    teams_role = task.get("teamsRole") or teams_role_for_stage(
        task["platform"], task["stage"]
    )
    teams_entry = teams_by_role.get(teams_role)

    estimate = setup.get("placeholderEstimate") or "1h"
    additional: dict[str, Any] = {
        "customfield_10014": epic_key,
        "timetracking": {
            "originalEstimate": estimate,
            "remainingEstimate": estimate,
        },
    }

    sprint_id = _sprint_id_from_epic(epic_issue, config)
    if sprint_id is not None:
        additional["customfield_10020"] = sprint_id

    priority = get_field(epic_issue, "priority")
    if isinstance(priority, dict) and priority.get("name"):
        additional["priority"] = {"name": priority["name"]}

    fix_versions = get_field(epic_issue, "fixVersions")
    if fix_versions:
        additional["fixVersions"] = [
            {"id": v["id"]} if isinstance(v, dict) and v.get("id") else v
            for v in fix_versions
        ]
    elif project_defaults.get("fixVersion"):
        additional["fixVersions"] = [project_defaults["fixVersion"]]

    project_element = get_field(epic_issue, "customfield_10314")
    if isinstance(project_element, dict) and project_element.get("id"):
        additional["customfield_10314"] = {"id": project_element["id"]}
    elif project_defaults.get("projectElement"):
        additional["customfield_10314"] = project_defaults["projectElement"]

    if teams_entry:
        additional["customfield_10218"] = teams_entry

    return {
        "projectKey": project_key,
        "issueTypeName": "Task",
        "summary": task["summary"],
        "parent": epic_key,
        "additional_fields": additional,
    }


def build_setup_plan(
    epic_key: str,
    issues: list[dict[str, Any]],
    platforms: list[str],
    *,
    dev_placeholders: bool,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Build epic setup plan: covered stages, tasks to create, and skipped duplicates."""
    epic_key = epic_key.upper()
    epic_issues = filter_issues_for_epic(issues, epic_key)
    epic_issue = _epic_issue(epic_issues, epic_key)
    if not epic_issue:
        raise ValueError(f"Epic not found in issues: {epic_key}")

    setup = load_epic_setup_config(config)
    task_stages = setup.get("taskStages") or DEFAULT_TASK_STAGES
    epic_summary = (get_field(epic_issue, "summary") or epic_key).strip()

    covered_map = scan_existing_stages(epic_issues, config)
    covered = [
        {"platform": plat, "stage": stage, "issueKeys": keys}
        for (plat, stage), keys in sorted(covered_map.items())
    ]

    to_create: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for platform in platforms:
        stages = task_stages.get(platform) or DEFAULT_TASK_STAGES.get(platform, [])
        for stage in stages:
            if stage == STAGE_DEVELOPMENT and not dev_placeholders:
                continue

            existing_keys = covered_map.get((platform, stage), [])
            if existing_keys:
                skipped.append(
                    {
                        "platform": platform,
                        "stage": stage,
                        "reason": "existing",
                        "issueKey": existing_keys[0],
                        "issueKeys": existing_keys,
                    }
                )
                continue

            summary = stage_summary(platform, stage, epic_summary)
            teams_role = teams_role_for_stage(platform, stage)
            task_row = {
                "platform": platform,
                "stage": stage,
                "summary": summary,
                "teamsRole": teams_role,
            }
            task_row["createPayload"] = jira_create_fields(
                task_row, epic_issue, config
            )
            to_create.append(task_row)

    return {
        "epicKey": epic_key,
        "epicSummary": epic_summary,
        "projectKey": project_key_from_issue_key(epic_key),
        "platforms": platforms,
        "devPlaceholders": dev_placeholders,
        "covered": covered,
        "toCreate": to_create,
        "skipped": skipped,
    }


def format_setup_plan_summary(plan: dict[str, Any], *, create_mode: bool = False) -> str:
    """Human-readable plan for chat (dry-run or post-create)."""
    lines = [
        f"Epic {plan['epicKey']} — {plan['epicSummary']}",
        f"Platforms: {', '.join(plan.get('platforms') or [])}",
        "",
    ]

    covered = plan.get("covered") or []
    if covered:
        lines.append(f"Covered stages ({len(covered)}):")
        for row in covered:
            keys = ", ".join(row.get("issueKeys") or [])
            lines.append(f"  - {row['stage']} / {row['platform']}: {keys}")
    else:
        lines.append("Covered stages (0): none")

    skipped = plan.get("skipped") or []
    lines.append("")
    if skipped:
        lines.append(f"Skipped — already mapped ({len(skipped)}):")
        for row in skipped:
            lines.append(
                f"  - {row['stage']} / {row['platform']}: {row.get('issueKey')} (existing)"
            )
    else:
        lines.append("Skipped — already mapped (0): none")

    to_create = plan.get("toCreate") or []
    lines.append("")
    if to_create:
        label = "To create" if not create_mode else "Create via MCP"
        lines.append(f"{label} ({len(to_create)}):")
        for row in to_create:
            lines.append(f"  - {row['summary']}")
        if not create_mode:
            lines.append("")
            lines.append(
                f"Run with --create or confirm to create {len(to_create)} task(s) in Jira."
            )
    else:
        lines.append("To create (0): epic already has all requested stage tasks.")

    return "\n".join(lines) + "\n"
