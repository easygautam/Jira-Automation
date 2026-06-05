"""Configuration loading and shared constants for the sprint pipeline."""

from __future__ import annotations

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


def load_config(path: Path) -> dict[str, Any]:
    """Load em-config.yaml; fall back to minimal defaults without PyYAML."""
    text = Path(path).read_text(encoding="utf-8")
    if yaml is not None:
        return yaml.safe_load(text) or {}
    return {"priorityOrder": DEFAULT_PRIORITY, "teams": {}}
