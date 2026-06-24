"""Steps 3 & 4 — classify each issue into a leave bucket or a platform stage.

`classify_issue` is the single entry point: it returns one of

* ``{"kind": "leave", "leaveType": ..., "team": ..., "comment": ...}``
* ``{"kind": "work", "platform": ..., "stage": ..., "team": ..., "issueKey": ...}``
* ``{"kind": "unmapped", "platform": None, "stage": None, "team": ...}``

Stage mapping uses pipe-segment positions only (no keyword substring search).
"""

from __future__ import annotations

from typing import Any

from sprintkit.jira_model import (
    assignee_name,
    get_field,
    is_bug_issue,
    is_task_or_subtask,
    issue_type_name,
)
from sprintkit.teams import (
    TEAM_OTHER,
    _prefix_tokens,
    delivery_platform,
    is_jira_teams_uat_value,
    jira_teams_field_value,
    load_prefix_alias_sets,
    team_from_first_prefix,
    team_from_issue,
    team_from_jira_field,
    team_from_jira_field_value,
    team_from_prefix_tokens,
    team_from_title,
)

PLATFORM_KEYS = ("backend", "frontend", "mobile")
PLATFORM_SIDE = {"backend": "Backend", "frontend": "Web", "mobile": "Mobile"}

TEAM_PRODUCT_DESIGN = "product_design"

STAGE_TECH_SOLUTIONING = "Tech Solutioning"
STAGE_QA_TEST_PLANNING = "QA Test Planning"
STAGE_DEVELOPMENT = "Development"
STAGE_STAGE_TESTING = "Stage testing"
STAGE_BUG_FIXES = "Bug fixes"
STAGE_STAGE_FINAL_TESTING = "Stage final testing"
STAGE_PROD_RELEASE = "Prod release"
STAGE_PROD_FINAL_TESTING = "Prod final testing"
STAGE_PREPROD = "Pre-Prod testing"
STAGE_UAT = "UAT"
STAGE_GO_LIVE = "Go live date"

DEFAULT_EXECUTION_STAGES: dict[str, list[str]] = {
    "backend": [
        STAGE_TECH_SOLUTIONING,
        STAGE_QA_TEST_PLANNING,
        STAGE_DEVELOPMENT,
        STAGE_STAGE_TESTING,
        STAGE_BUG_FIXES,
        STAGE_STAGE_FINAL_TESTING,
        STAGE_PROD_RELEASE,
        STAGE_PROD_FINAL_TESTING,
        STAGE_GO_LIVE,
    ],
    "frontend": [
        STAGE_TECH_SOLUTIONING,
        STAGE_QA_TEST_PLANNING,
        STAGE_DEVELOPMENT,
        STAGE_STAGE_TESTING,
        STAGE_BUG_FIXES,
        STAGE_STAGE_FINAL_TESTING,
        STAGE_PREPROD,
        STAGE_UAT,
        STAGE_GO_LIVE,
    ],
    "mobile": [
        STAGE_TECH_SOLUTIONING,
        STAGE_QA_TEST_PLANNING,
        STAGE_DEVELOPMENT,
        STAGE_STAGE_TESTING,
        STAGE_BUG_FIXES,
        STAGE_STAGE_FINAL_TESTING,
        STAGE_PREPROD,
        STAGE_UAT,
        STAGE_GO_LIVE,
    ],
}

# Defaults when timeline.defaultTaskByTeam is absent (e.g. config not loaded)
_DEFAULT_TASK_BY_TEAM: dict[str, str] = {
    "backend": "Development",
    "frontend": "Development",
    "mobile": "Development",
}

_WEB_MOBILE_PREPROD_SEG3 = frozenset(
    {"pre-prod", "pre prod", "pre-prod testing", "final testing", "prod testing"}
)

_BACKEND_PROD_RELEASE_SEG = frozenset({"prod release", "production release"})
_BACKEND_PROD_FINAL_SEG = frozenset(
    {"prod final testing", "prod final", "production final testing", "production final"}
)


# --- prefix/stage helpers -------------------------------------------------


def _pipe_segments(summary: str) -> list[str]:
    return [p.strip() for p in summary.split("|")]


def _summary_has_assessment_segment(summary: str) -> bool:
    """True when a pipe segment is Assessment (e.g. BE | Assessment)."""
    if "|" not in summary:
        return False
    parts = [p.strip().casefold() for p in summary.split("|")]
    return any(p == "assessment" or p.endswith(" assessment") for p in parts[1:]) or (
        parts[-1] == "assessment"
    )


def platform_from_pipe_segment(
    segment: str,
    config: dict[str, Any] | None = None,
) -> str | None:
    """Map a single pipe segment to backend | frontend | mobile, or None."""
    alias_sets = load_prefix_alias_sets(config)
    team = team_from_prefix_tokens(_prefix_tokens(segment), alias_sets)
    if team in PLATFORM_KEYS:
        return team
    return None


def platform_uat_from_segments(
    summary: str,
    config: dict[str, Any] | None = None,
) -> str | None:
    """{WEB|APP|BE} | UAT | … → platform key when segment 2 is UAT."""
    parts = _pipe_segments(summary)
    if len(parts) < 2:
        return None
    platform = platform_from_pipe_segment(parts[0], config)
    if platform and parts[1].casefold() == "uat":
        return platform
    return None


def qa_platform_from_segment(
    summary: str,
    config: dict[str, Any] | None = None,
) -> str | None:
    """
    Platform for QA work from the second pipe segment only (QA | App | …).
    None when segment 2 is missing or not App/Web/BE.
    """
    parts = _pipe_segments(summary)
    if not parts or parts[0].casefold() != "qa":
        return None
    if len(parts) < 2:
        return None
    return platform_from_pipe_segment(parts[1], config)


def qa_stage_from_segments(
    summary: str,
    config: dict[str, Any] | None = None,
) -> tuple[str, str] | None:
    """
    QA | {Platform} | {stage segment} | … → (platform, stage) from segment 3 only.
    Web/Mobile pre-prod aliases → Pre-Prod testing.
    Backend final testing → Prod final testing.
    """
    parts = _pipe_segments(summary)
    if len(parts) < 3 or parts[0].casefold() != "qa":
        return None
    platform = platform_from_pipe_segment(parts[1], config)
    if not platform:
        return None
    seg3 = parts[2].casefold()
    if platform in ("frontend", "mobile") and seg3 in _WEB_MOBILE_PREPROD_SEG3:
        return platform, STAGE_PREPROD
    if platform == "backend":
        if seg3 == "final testing":
            return platform, STAGE_PROD_FINAL_TESTING
        if seg3 in _BACKEND_PROD_RELEASE_SEG:
            return platform, STAGE_PROD_RELEASE
        if seg3 in _BACKEND_PROD_FINAL_SEG:
            return platform, STAGE_PROD_FINAL_TESTING
    return None


def platform_release_from_segments(
    summary: str,
    config: dict[str, Any] | None = None,
) -> tuple[str, str] | None:
    """
    {Platform} | {release segment} | … from segment 2 (non-QA platform-prefixed tasks).
    """
    parts = _pipe_segments(summary)
    if len(parts) < 2:
        return None
    platform = platform_from_pipe_segment(parts[0], config)
    if not platform:
        return None
    seg2 = parts[1].casefold()
    if seg2 in _BACKEND_PROD_RELEASE_SEG:
        return platform, STAGE_PROD_RELEASE
    if seg2 in _BACKEND_PROD_FINAL_SEG:
        return platform, STAGE_PROD_FINAL_TESTING
    if seg2 == "go live":
        return platform, STAGE_GO_LIVE
    return None


def assessment_target(
    summary: str,
    config: dict[str, Any] | None = None,
) -> str | None:
    """
    Platform key for Tech Solutioning stage on dev assessment tasks.
    None for QA titles (handled in QA classify block) or non-assessment titles.
    """
    if not _summary_has_assessment_segment(summary):
        return None
    alias_sets = load_prefix_alias_sets(config)
    team = team_from_first_prefix(summary, alias_sets)
    if team == "qa":
        return None
    if team in PLATFORM_KEYS:
        return team
    plat = delivery_platform(team, config)
    if plat in PLATFORM_KEYS:
        return plat
    return None


def task_from_pipe_prefix_team(
    summary: str,
    team: str,
    timeline_cfg: dict[str, Any],
    issuetype: str,
    config: dict[str, Any] | None = None,
) -> str | None:
    """
    When summary uses a recognized first pipe prefix, map Task/Sub-task to default
    canonical row for that team (e.g. BE | Enhancement -> Development).
    """
    if "|" not in summary:
        return None
    alias_sets = load_prefix_alias_sets(config)
    if team_from_first_prefix(summary, alias_sets) is None:
        return None
    if team in (TEAM_OTHER, "qa"):
        return None
    itype = (issuetype or "").lower()
    if itype not in ("task", "sub-task", "subtask"):
        return None
    if _summary_has_assessment_segment(summary):
        return None
    defaults = timeline_cfg.get("defaultTaskByTeam") or _DEFAULT_TASK_BY_TEAM
    plat = delivery_platform(team, config)
    return defaults.get(team) or (defaults.get(plat) if plat else None)


def _is_qa_test_planning(summary: str) -> bool:
    """True when segments after platform contain assessment or test planning."""
    parts = _pipe_segments(summary)
    if len(parts) < 3:
        return False
    remainder = " ".join(parts[2:]).casefold()
    return "assessment" in remainder or "test planning" in remainder


def _is_qa_automation(summary: str) -> bool:
    """True when third segment is Automation (QA | Platform | Automation | …)."""
    parts = _pipe_segments(summary)
    return len(parts) >= 3 and parts[2].casefold() == "automation"


def resolve_leave_team(
    issue: dict[str, Any],
    epic_issues: list[dict[str, Any]],
    teams_cfg: dict[str, list[str]],
    config: dict[str, Any] | None,
) -> str:
    """Leave team = own prefix team, else inherit from member's other epic tasks."""
    team = team_from_issue(issue, teams_cfg, config)
    if team != TEAM_OTHER:
        return team
    member = assignee_name(issue)
    if member == "Unassigned":
        return team
    for other in epic_issues:
        if other.get("key") == issue.get("key"):
            continue
        if is_bug_issue(other) or not is_task_or_subtask(other):
            continue
        if assignee_name(other) != member:
            continue
        other_team = team_from_issue(other, teams_cfg, config)
        if other_team != TEAM_OTHER:
            return other_team
    return team


def classify_issue(
    issue: dict[str, Any],
    timeline_cfg: dict[str, Any],
    teams_cfg: dict[str, list[str]],
    config: dict[str, Any] | None = None,
    epic_issues: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    summary = (get_field(issue, "summary") or "").strip()
    lower = summary.lower()
    prefixes = timeline_cfg.get("leaveTaskPrefixes") or {}
    planned_p = (prefixes.get("planned") or "Leave | Planned").lower()
    unplanned_p = (prefixes.get("unplanned") or "Leave | Unplanned").lower()
    generic_p = (prefixes.get("generic") or "Leave |").lower()

    def _work(platform: str, stage: str, team: str) -> dict[str, Any]:
        return {
            "kind": "work",
            "platform": platform,
            "stage": stage,
            "team": team,
            "issueKey": issue.get("key"),
        }

    def _leave_result(leave_type: str, prefix_len: int) -> dict[str, Any]:
        team = resolve_leave_team(issue, epic_issues or [], teams_cfg, config)
        comment = summary[prefix_len:].strip(" -:")
        return {
            "kind": "leave",
            "leaveType": leave_type,
            "team": team,
            "comment": comment,
        }

    if lower.startswith(planned_p):
        return _leave_result("planned", len(prefixes.get("planned") or "Leave | Planned"))
    if lower.startswith(unplanned_p):
        return _leave_result(
            "unplanned", len(prefixes.get("unplanned") or "Leave | Unplanned")
        )
    if lower.startswith(generic_p):
        return _leave_result("planned", len(prefixes.get("generic") or "Leave |"))

    assess_platform = assessment_target(summary, config)
    if assess_platform in PLATFORM_KEYS:
        title_team = team_from_title(summary, config) or assess_platform
        return _work(assess_platform, STAGE_TECH_SOLUTIONING, title_team)

    uat_platform = platform_uat_from_segments(summary, config)
    if uat_platform:
        return _work(uat_platform, STAGE_UAT, TEAM_PRODUCT_DESIGN)

    title_team = team_from_title(summary, config)
    field_value = jira_teams_field_value(issue, config)
    if not title_team and field_value:
        if is_jira_teams_uat_value(field_value, config):
            return _work("frontend", STAGE_UAT, TEAM_PRODUCT_DESIGN)
        field_team = team_from_jira_field_value(field_value, config)
        if field_team in ("data_engineering", "devops"):
            return _work("backend", STAGE_DEVELOPMENT, field_team)

    team = team_from_issue(issue, teams_cfg, config)
    itype = issue_type_name(issue)

    if team == "qa" or itype == "test execution":
        qa_platform = qa_platform_from_segment(summary, config)
        if not qa_platform:
            return {"kind": "unmapped", "platform": None, "stage": None, "team": "qa"}

        if _is_qa_test_planning(summary):
            return _work(qa_platform, STAGE_QA_TEST_PLANNING, "qa")

        if _is_qa_automation(summary):
            return _work(qa_platform, STAGE_STAGE_TESTING, "qa")

        qa_stage = qa_stage_from_segments(summary, config)
        if qa_stage:
            plat, stage = qa_stage
            return _work(plat, stage, "qa")

        return _work(qa_platform, STAGE_STAGE_TESTING, "qa")

    release = platform_release_from_segments(summary, config)
    if release and team in PLATFORM_KEYS:
        plat, stage = release
        if plat == team:
            return _work(plat, stage, team)

    if itype == "bug":
        return {"kind": "unmapped", "platform": None, "stage": None, "team": team}

    dev_stage = task_from_pipe_prefix_team(summary, team, timeline_cfg, itype, config)
    if dev_stage:
        plat = delivery_platform(team, config) or (team if team in PLATFORM_KEYS else None)
        if plat in PLATFORM_KEYS:
            return _work(plat, dev_stage, team)

    plat = delivery_platform(team, config)
    if plat in PLATFORM_KEYS and itype in ("task", "sub-task", "subtask"):
        title_resolved = team_from_title(summary, config)
        if title_resolved == team or team_from_jira_field(issue, config) == team:
            defaults = timeline_cfg.get("defaultTaskByTeam") or _DEFAULT_TASK_BY_TEAM
            stage = defaults.get(plat) or defaults.get(team)
            if stage:
                return _work(plat, stage, team)

    return {"kind": "unmapped", "platform": None, "stage": None, "team": team}
