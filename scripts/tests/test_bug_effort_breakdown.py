"""Tests for bug_effort_breakdown and timeline task-type filter."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from bug_effort_breakdown import build_bug_effort_breakdown  # noqa: E402
from timeline_breakdown import (  # noqa: E402
    build_timeline_breakdown,
    is_bug_issue,
    is_task_or_subtask,
)


def _issue(
    key: str,
    summary: str,
    estimate_seconds: int = 0,
    parent_key: str | None = None,
    issuetype: str = "Task",
    assignee: str | None = "Alice",
) -> dict:
    fields: dict = {
        "summary": summary,
        "timeoriginalestimate": estimate_seconds,
        "issuetype": {"name": issuetype},
        "labels": [],
        "components": [],
        "status": {"name": "In Progress"},
    }
    if assignee:
        fields["assignee"] = {"displayName": assignee, "accountId": assignee}
    if parent_key:
        fields["parent"] = {
            "key": parent_key,
            "fields": {"issuetype": {"name": "Epic"}, "summary": "Test Epic"},
        }
    return {"key": key, "fields": fields}


def _epic(key: str) -> dict:
    return {
        "key": key,
        "fields": {
            "summary": "Epic",
            "issuetype": {"name": "Epic", "hierarchyLevel": 1},
        },
    }


CONFIG = {
    "teams": {"backend": ["be"], "frontend": ["web"]},
    "timeline": {
        "hoursPerDay": 6,
        "leaveTaskPrefixes": {"planned": "Leave | Planned", "unplanned": "Leave | Unplanned"},
        "sideDisplay": {"backend": "Backend", "frontend": "Web", "unknown": "Other"},
        "canonicalTasks": [{"name": "BE development", "side": "Backend"}],
        "mappingRules": [
            {"keywords": ["be ||"], "task": "BE development"},
            {"keywords": ["bug"], "task": None, "useTeamBugRow": True},
        ],
    },
}


class TestIssueTypeHelpers(unittest.TestCase):
    def test_task_and_subtask(self):
        self.assertTrue(is_task_or_subtask(_issue("A", "x", issuetype="Task")))
        self.assertTrue(is_task_or_subtask(_issue("B", "x", issuetype="Sub-task")))
        self.assertFalse(is_task_or_subtask(_issue("C", "x", issuetype="Bug")))
        self.assertFalse(is_task_or_subtask(_issue("D", "x", issuetype="Test Execution")))

    def test_bug(self):
        self.assertTrue(is_bug_issue(_issue("E", "x", issuetype="Bug")))


class TestTimelineTaskOnly(unittest.TestCase):
    def test_excludes_bug_and_test_execution(self):
        epic = _epic("VP-1")
        task = _issue("VP-10", "BE || work", 7200, parent_key="VP-1", issuetype="Task")
        bug = _issue("VP-11", "Login broken", 3600, parent_key="VP-1", issuetype="Bug")
        te = _issue(
            "VP-12",
            "QA | test",
            1800,
            parent_key="VP-1",
            issuetype="Test Execution",
        )
        result = build_timeline_breakdown(
            [epic, task, bug, te], {"scheduled": []}, CONFIG
        )
        be = next(r for r in result[0]["tasks"] if r["task"] == "BE development")
        self.assertEqual(be["effortsHours"], 2.0)


class TestBugEffortBreakdown(unittest.TestCase):
    def test_per_member_per_epic(self):
        epic = _epic("VP-2")
        b1 = _issue("VP-20", "Bug one", 7200, parent_key="VP-2", issuetype="Bug", assignee="Alice")
        b2 = _issue("VP-21", "Bug two", 3600, parent_key="VP-2", issuetype="Bug", assignee="Bob")
        result = build_bug_effort_breakdown(
            [epic, b1, b2],
            {
                "scheduled": [
                    {"key": "VP-20", "startDate": "2026-06-01", "dueDate": "2026-06-02"},
                ]
            },
            CONFIG,
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["totalBugHours"], 3.0)
        self.assertEqual(len(result[0]["members"]), 2)


if __name__ == "__main__":
    unittest.main()
