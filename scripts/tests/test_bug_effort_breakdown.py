"""Tests for bug_effort_breakdown and timeline task-type filter."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from sprintkit.bugs import build_bug_effort_breakdown  # noqa: E402
from sprintkit.jira_model import is_bug_issue, is_task_or_subtask  # noqa: E402
from sprintkit.timeline import build_timeline_breakdown  # noqa: E402


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
        "defaultTaskByTeam": {"backend": "Development"},
        "executionStages": {
            "backend": ["Development"],
            "frontend": ["Development"],
            "mobile": ["Development"],
        },
        "stageMapping": [],
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
        be = next(
            r
            for r in result[0]["executionStages"]["backend"]["stages"]
            if r["stage"] == "Development"
        )
        self.assertEqual(be["effortsHours"], 2.0)


class TestBugEffortBreakdown(unittest.TestCase):
    def test_per_member_per_epic(self):
        epic = _epic("VP-2")
        b1 = _issue("VP-20", "Bug one", 0, parent_key="VP-2", issuetype="Bug", assignee="Alice")
        b1["fields"]["timespent"] = 7200
        b2 = _issue("VP-21", "Bug two", 0, parent_key="VP-2", issuetype="Bug", assignee="Bob")
        b2["fields"]["timespent"] = 3600
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
        alice = next(m for m in result[0]["members"] if m["member"] == "Alice")
        self.assertEqual(alice["effortsHours"], 2.0)
        self.assertEqual(alice["bugCount"], 1)
        self.assertNotIn("issues", alice)

    def test_ignores_original_estimate_without_timespent(self):
        epic = _epic("VP-5")
        bug = _issue(
            "VP-50",
            "OE only",
            7200,
            parent_key="VP-5",
            issuetype="Bug",
            assignee="Alice",
        )
        result = build_bug_effort_breakdown(
            [epic, bug],
            {"scheduled": []},
            CONFIG,
        )
        self.assertIsNone(result[0]["totalBugHours"])
        alice = result[0]["members"][0]
        self.assertIsNone(alice["effortsHours"])
        self.assertEqual(alice["bugCount"], 1)

    def test_bug_uses_timespent_when_oe_empty(self):
        epic = _epic("VP-4")
        bug = _issue(
            "VP-40",
            "Logged only",
            0,
            parent_key="VP-4",
            issuetype="Bug",
            assignee="Alice",
        )
        bug["fields"]["timespent"] = 7200
        result = build_bug_effort_breakdown(
            [epic, bug],
            {"scheduled": []},
            {**CONFIG, "fields": {"timeSpent": "timespent"}},
        )
        self.assertEqual(result[0]["totalBugHours"], 2.0)

    def test_all_sprint_epics_including_zero_bugs(self):
        epic1 = _epic("VP-1")
        epic2 = _epic("VP-2")
        bug = _issue("VP-10", "Bug", 0, parent_key="VP-1", issuetype="Bug")
        bug["fields"]["timespent"] = 3600
        result = build_bug_effort_breakdown(
            [epic1, epic2, bug],
            {"scheduled": [{"key": "VP-10", "epicKey": "VP-1"}]},
            CONFIG,
        )
        keys = [r["epicKey"] for r in result]
        self.assertEqual(keys, ["VP-1", "VP-2"])
        empty = next(r for r in result if r["epicKey"] == "VP-2")
        self.assertEqual(empty["bugCount"], 0)
        self.assertIsNone(empty["totalBugHours"])
        self.assertEqual(empty["members"], [])

    def test_side_hours_totals(self):
        epic = _epic("VP-3")
        b1 = _issue(
            "VP-30",
            "QA | WEB | bug",
            0,
            parent_key="VP-3",
            issuetype="Bug",
            assignee="Alice",
        )
        b1["fields"]["timespent"] = 3600
        result = build_bug_effort_breakdown([epic, b1], {"scheduled": []}, CONFIG)
        side_hours = result[0]["sideHours"]
        self.assertTrue(side_hours)
        # One bug worth 1.0h attributed to exactly one side; reconciles to total.
        self.assertEqual(sum(side_hours.values()), 1.0)
        self.assertEqual(result[0]["totalBugHours"], 1.0)


if __name__ == "__main__":
    unittest.main()
