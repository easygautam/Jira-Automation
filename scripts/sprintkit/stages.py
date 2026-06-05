"""Steps 3 & 4 — classify each issue into a leave bucket or a platform stage.

`classify_issue` is the single entry point: it returns one of

* ``{"kind": "leave", "leaveType": ..., "team": ..., "comment": ...}``
* ``{"kind": "work", "platform": ..., "stage": ..., "team": ..., "issueKey": ...}``
* ``{"kind": "unmapped", "platform": None, "stage": None, "team": ...}``
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
    load_prefix_alias_sets,
    team_from_first_prefix,
    team_from_issue,
)

PLATFORM_KEYS = ("backend", "frontend", "mobile")
PLATFORM_SIDE = {"backend": "Backend", "frontend": "Web", "mobile": "Mobile"}
QA_CROSS = "qa_cross"

STAGE_TEST_PLANNING = "Test planning"
STAGE_ASSESSMENT = "Assessment"
STAGE_DEVELOPMENT = "Development"
STAGE_STAGE_TESTING = "Stage testing"
STAGE_BUG_FIXES = "Bug fixes"
STAGE_STAGE_FINAL_TESTING = "Stage final testing"
STAGE_PROD_RELEASE = "Prod release"
STAGE_PROD_FINAL_TESTING = "Prod final testing"
STAGE_PREPROD = "Pre-Prod testing"
STAGE_UAT = "UAT"
STAGE_READY = "Ready for release"
STAGE_GO_LIVE = "Go live date"

DEFAULT_EXECUTION_STAGES: dict[str, list[str]] = {
    "backend": [
        STAGE_ASSESSMENT,
        STAGE_DEVELOPMENT,
        STAGE_STAGE_TESTING,
        STAGE_BUG_FIXES,
        STAGE_STAGE_FINAL_TESTING,
        STAGE_PROD_RELEASE,
        STAGE_PROD_FINAL_TESTING,
        STAGE_GO_LIVE,
    ],
    "frontend": [
        STAGE_ASSESSMENT,
        STAGE_DEVELOPMENT,
        STAGE_STAGE_TESTING,
        STAGE_BUG_FIXES,
        STAGE_STAGE_FINAL_TESTING,
        STAGE_PREPROD,
        STAGE_UAT,
        STAGE_READY,
        STAGE_GO_LIVE,
    ],
    "mobile": [
        STAGE_ASSESSMENT,
        STAGE_DEVELOPMENT,
        STAGE_STAGE_TESTING,
        STAGE_BUG_FIXES,
        STAGE_STAGE_FINAL_TESTING,
        STAGE_PREPROD,
        STAGE_UAT,
        STAGE_READY,
        STAGE_GO_LIVE,
    ],
}

# Defaults when timeline.defaultTaskByTeam is absent (e.g. config not loaded)
_DEFAULT_TASK_BY_TEAM: dict[str, str] = {
    "backend": "Development",
    "frontend": "Development",
    "mobile": "Development",
}


# --- prefix/stage helpers -------------------------------------------------


def _summary_has_assessment_segment(summary: str) -> bool:
    """True when a pipe segment is Assessment (e.g. BE | Assessment)."""
    if "|" not in summary:
        return False
    parts = [p.strip().casefold() for p in summary.split("|")]
    return any(p == "assessment" or p.endswith(" assessment") for p in parts[1:]) or (
        parts[-1] == "assessment"
    )


def assessment_target(
    summary: str,
    config: dict[str, Any] | None = None,
) -> str | None:
    """
    Platform key for Assessment stage, or qa_cross for QA | Assessment.
    None if title is not an assessment task.
    """
    if not _summary_has_assessment_segment(summary):
        return None
    alias_sets = load_prefix_alias_sets(config)
    team = team_from_first_prefix(summary, alias_sets)
    if team == "qa":
        return QA_CROSS
    if team in PLATFORM_KEYS:
        return team
    return None


def qa_platform_stream(summary: str) -> str | None:
    """
    When first prefix is QA, return backend | frontend | mobile for scoped QA work.
    None when QA title has no Web/Mobile/BE stream (cross-platform test planning).
    """
    parts = [p.strip().lower() for p in summary.split("|")]
    if not parts or parts[0] != "qa":
        return None
    if len(parts) < 2:
        return None
    context = " ".join(parts[1:])
    if any(x in context for x in ("be", "backend", "api contract")):
        return "backend"
    if any(x in context for x in ("app", "mobile", "android", "ios")):
        return "mobile"
    if any(x in context for x in ("web", "website", "mweb", "frontend", "fe", "admin")):
        return "frontend"
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
    if "assessment" in summary.lower():
        return None
    defaults = timeline_cfg.get("defaultTaskByTeam") or _DEFAULT_TASK_BY_TEAM
    return defaults.get(team)


def stage_mapping_rule_applies(rule: dict[str, Any], summary: str) -> bool:
    """Keyword match with optional excludeKeywords."""
    keywords = [k.lower() for k in rule.get("keywords") or []]
    if not keywords:
        return False
    lower = summary.lower()
    if not any(kw in lower for kw in keywords):
        return False
    for ex in rule.get("excludeKeywords") or []:
        if ex.lower() in lower:
            return False
    return True


def _match_config_stage(
    stage_mapping: list[dict[str, Any]],
    platform: str,
    summary: str,
) -> str | None:
    for rule in stage_mapping:
        if rule.get("platform") != platform:
            continue
        if stage_mapping_rule_applies(rule, summary):
            return rule.get("stage")
    return None


def _is_stage_testing_qa(summary: str) -> bool:
    lower = summary.lower()
    if "pre-prod" in lower or "pre prod" in lower:
        return False
    if "ready for release" in lower:
        return False
    markers = (
        "1st iteration",
        "2nd iteration",
        "iteration",
        "stage testing",
        "mweb stage",
        "admin + bug",
        "api contract",
        "automation testing",
    )
    return any(m in lower for m in markers)


def _qa_scoped_release_stage(summary: str, platform: str) -> str | None:
    lower = summary.lower()
    if "ready for release" in lower:
        return STAGE_READY
    if ("uat" in lower or "uat stage" in lower) and "pre-prod" not in lower and "pre prod" not in lower:
        if "prod final" in lower or "uat prod" in lower:
            return None
        return STAGE_UAT
    if "pre-prod" in lower or "pre prod" in lower:
        return STAGE_PREPROD
    return None


def _backend_prod_stage(summary: str) -> str | None:
    lower = summary.lower()
    if any(k in lower for k in ("prod final", "production final", "uat prod")):
        return STAGE_PROD_FINAL_TESTING
    if any(k in lower for k in ("prod release", "production release")):
        if "prod final" in lower or "final testing" in lower:
            return None
        return STAGE_PROD_RELEASE
    return None


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
    stage_mapping = timeline_cfg.get("stageMapping") or []

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
    if assess_platform == QA_CROSS:
        return _work(QA_CROSS, STAGE_TEST_PLANNING, "qa")
    if assess_platform in PLATFORM_KEYS:
        return _work(assess_platform, STAGE_ASSESSMENT, assess_platform)

    team = team_from_issue(issue, teams_cfg, config)
    itype = issue_type_name(issue)
    qa_stream = qa_platform_stream(summary)

    if team == "qa" or itype == "test execution":
        if qa_stream:
            release_stage = _qa_scoped_release_stage(summary, qa_stream)
            if release_stage and qa_stream in ("frontend", "mobile"):
                return _work(qa_stream, release_stage, "qa")
            if qa_stream == "backend":
                prod = _backend_prod_stage(summary)
                if prod:
                    return _work("backend", prod, "qa")
            if _is_stage_testing_qa(summary):
                return _work(qa_stream, STAGE_STAGE_TESTING, "qa")
            mapped = _match_config_stage(stage_mapping, qa_stream, summary)
            if mapped:
                return _work(qa_stream, mapped, "qa")
        markers_planning = (
            "test case",
            "test cases",
            "test planning",
            "test execution",
            "qa planning",
        )
        if any(m in lower for m in markers_planning) or qa_stream is None:
            return _work(QA_CROSS, STAGE_TEST_PLANNING, "qa")
        return _work(qa_stream, STAGE_STAGE_TESTING, "qa")

    if team == "backend" or qa_stream == "backend":
        prod = _backend_prod_stage(summary)
        if prod:
            return _work("backend", prod, team if team != TEAM_OTHER else "backend")
        if "go live" in lower:
            return _work("backend", STAGE_GO_LIVE, "backend")

    if team in PLATFORM_KEYS:
        mapped = _match_config_stage(stage_mapping, team, summary)
        if mapped:
            return _work(team, mapped, team)
        if team in ("frontend", "mobile"):
            release_stage = _qa_scoped_release_stage(summary, team)
            if release_stage:
                return _work(team, release_stage, team)
        if "go live" in lower:
            return _work(team, STAGE_GO_LIVE, team)

    if itype == "bug":
        return {"kind": "unmapped", "platform": None, "stage": None, "team": team}

    dev_stage = task_from_pipe_prefix_team(summary, team, timeline_cfg, itype, config)
    if dev_stage and team in PLATFORM_KEYS:
        return _work(team, dev_stage, team)

    return {"kind": "unmapped", "platform": None, "stage": None, "team": team}
