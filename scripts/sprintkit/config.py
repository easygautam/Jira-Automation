"""Configuration loading and shared constants for the sprint pipeline."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - optional dependency
    yaml = None  # type: ignore

DEFAULT_PRIORITY = ["Highest", "High", "Medium", "Low", "Lowest"]
DEFAULT_BUG_ACTIVE_STATUSES = ["To Do", "In Progress", "Hold", "Deferred"]
DEFAULT_BUG_NO_WORKLOG_STATUSES = ["Not a Bug"]
SCHEDULABLE_TYPES = frozenset({"task", "sub-task", "subtask", "bug", "test execution"})

DEFAULT_SIDE_DISPLAY: dict[str, str] = {
    "backend": "Backend",
    "frontend": "Web",
    "mobile": "Mobile",
    "product_design": "Product + Design",
    "qa": "QA",
    "other": "Other",
    "unknown": "Other",
}

DEFAULT_TEAM_PREFIX_MAPPING: dict[str, dict[str, list[str]]] = {
    "qa": {"aliases": ["qa"]},
    "backend": {"aliases": ["be", "backend", "api", "dag", "ppadmin", "admin"]},
    "frontend": {"aliases": ["web", "website", "frontend", "frontent", "fe"]},
    "mobile": {"aliases": ["mobile", "app", "android", "ios"]},
}

_pyyaml_warning_emitted = False


def pyyaml_available() -> bool:
    return yaml is not None


def resolve_side_display_map(config: dict[str, Any] | None) -> dict[str, str]:
    """Merge built-in team labels with optional timeline.sideDisplay from config."""
    custom = ((config or {}).get("timeline") or {}).get("sideDisplay") or {}
    return {**DEFAULT_SIDE_DISPLAY, **custom}


def default_config() -> dict[str, Any]:
    """Runnable pipeline defaults when em-config.yaml cannot be parsed."""
    from sprintkit.stages import DEFAULT_EXECUTION_STAGES

    return {
        "priorityOrder": list(DEFAULT_PRIORITY),
        "teams": {
            "backend": ["backend", "be", "api"],
            "frontend": ["frontend", "web"],
            "mobile": ["mobile", "app"],
            "qa": ["qa"],
        },
        "teamPrefixMapping": {
            team: dict(entry) for team, entry in DEFAULT_TEAM_PREFIX_MAPPING.items()
        },
        "dataQuality": {
            "bugActiveStatuses": list(DEFAULT_BUG_ACTIVE_STATUSES),
            "bugNoWorklogStatuses": list(DEFAULT_BUG_NO_WORKLOG_STATUSES),
        },
        "scheduling": {
            "hoursPerDay": 8,
            "workingDayInts": [0, 1, 2, 3, 4],
        },
        "timeline": {
            "hoursPerDay": 6,
            "leaveTaskPrefixes": {
                "generic": "Leave |",
                "planned": "Leave | Planned",
                "unplanned": "Leave | Unplanned",
            },
            "sideDisplay": dict(DEFAULT_SIDE_DISPLAY),
            "defaultTaskByTeam": {
                "backend": "Development",
                "frontend": "Development",
                "mobile": "Development",
            },
            "effortBuffers": {
                "bugFixesPercentOfDevelopment": 0.10,
                "stageFinalTestingPercentOfStageTesting": 0.10,
            },
            "executionStages": {
                platform: list(stages)
                for platform, stages in DEFAULT_EXECUTION_STAGES.items()
            },
        },
    }


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def config_warnings(config: dict[str, Any] | None) -> list[str]:
    """Non-fatal setup notices for the executive summary."""
    warnings: list[str] = []
    if not pyyaml_available():
        warnings.append(
            "Config loaded from built-in defaults — PyYAML not installed; "
            "run `pip install -r requirements.txt` for full em-config.yaml."
        )
    cfg = config or {}
    jira = cfg.get("jira") or {}
    if not jira.get("projectKey"):
        warnings.append(
            "jira.projectKey is empty — set it in em-config.yaml for live Jira runs."
        )
    return warnings


def load_config(path: Path) -> dict[str, Any]:
    """Load em-config.yaml merged over built-in defaults."""
    global _pyyaml_warning_emitted
    defaults = default_config()
    text = Path(path).read_text(encoding="utf-8")
    if yaml is None:
        if not _pyyaml_warning_emitted:
            print(
                "Warning: PyYAML not installed — using built-in defaults. "
                "Install with: pip install -r requirements.txt",
                file=sys.stderr,
            )
            _pyyaml_warning_emitted = True
        return defaults
    loaded = yaml.safe_load(text) or {}
    if not isinstance(loaded, dict):
        return defaults
    return _deep_merge(defaults, loaded)
