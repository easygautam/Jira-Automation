"""Tests for timeline_breakdown.py."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from timeline_breakdown import (  # noqa: E402
    build_timeline_breakdown,
    calc_days,
    classify_issue,
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
    }
    if assignee:
        fields["assignee"] = {"displayName": assignee, "accountId": assignee}
    if parent_key:
        fields["parent"] = {
            "key": parent_key,
            "fields": {"issuetype": {"name": "Epic"}, "summary": "Test Epic"},
        }
    return {"key": key, "fields": fields}


def _epic(key: str, summary: str = "Events phase 1") -> dict:
    return {
        "key": key,
        "fields": {
            "summary": summary,
            "issuetype": {"name": "Epic", "hierarchyLevel": 1},
            "timeoriginalestimate": 0,
        },
    }


MINIMAL_CONFIG = {
    "teams": {
        "backend": ["backend", "be"],
        "frontend": ["frontend", "web"],
        "mobile": ["mobile", "android"],
        "qa": ["qa", "test"],
    },
    "timeline": {
        "hoursPerDay": 6,
        "leaveTaskPrefixes": {
            "planned": "Leave | Planned",
            "unplanned": "Leave | Unplanned",
        },
        "sideDisplay": {
            "backend": "Backend",
            "frontend": "Web",
            "mobile": "Mobile",
            "qa": "QA",
            "release": "Release",
            "unknown": "Other",
        },
        "canonicalTasks": [
            {"name": "BE development", "side": "Backend"},
            {"name": "Web development", "side": "Web"},
            {"name": "Go live date", "side": "Release"},
        ],
        "mappingRules": [
            {"keywords": ["leave | planned"], "leaveType": "planned"},
            {"keywords": ["leave | unplanned"], "leaveType": "unplanned"},
            {"keywords": ["be ||", "be development"], "task": "BE development"},
            {"keywords": ["web ||"], "task": "Web development"},
            {"keywords": ["go live"], "task": "Go live date"},
            {"keywords": ["bug"], "task": None, "useTeamBugRow": True},
        ],
    },
}


class TestCalcDays(unittest.TestCase):
    def test_six_hour_day(self):
        # (12 + 6 + 0) / (2 * 6) = 1.5 -> ceil 2
        self.assertEqual(calc_days(12, 6, 0, 2, 6), 2)

    def test_no_resources(self):
        self.assertIsNone(calc_days(10, 0, 0, 0, 6))


class TestClassifyIssue(unittest.TestCase):
    def test_planned_leave(self):
        issue = _issue("VP-1", "Leave | Planned - doctor", 7200)
        cfg = MINIMAL_CONFIG["timeline"]
        result = classify_issue(issue, cfg, MINIMAL_CONFIG["teams"])
        self.assertEqual(result["kind"], "leave")
        self.assertEqual(result["leaveType"], "planned")

    def test_be_development_keyword(self):
        issue = _issue("VP-2", "BE || Add endpoint", 14400)
        cfg = MINIMAL_CONFIG["timeline"]
        result = classify_issue(issue, cfg, MINIMAL_CONFIG["teams"])
        self.assertEqual(result["kind"], "work")
        self.assertEqual(result["task"], "BE development")


class TestBuildTimelineBreakdown(unittest.TestCase):
    def test_epic_aggregation_dates(self):
        epic = _epic("VP-100")
        t1 = _issue("VP-101", "BE || API", 28800, parent_key="VP-100")
        t2 = _issue("VP-102", "WEB || UI", 14400, parent_key="VP-100", assignee="Bob")
        schedule = {
            "scheduled": [
                {"key": "VP-101", "startDate": "2026-06-02", "dueDate": "2026-06-05"},
                {"key": "VP-102", "startDate": "2026-06-03", "dueDate": "2026-06-08"},
            ]
        }
        result = build_timeline_breakdown(
            [epic, t1, t2], schedule, MINIMAL_CONFIG
        )
        self.assertEqual(len(result), 1)
        epic_row = result[0]
        self.assertEqual(epic_row["epicKey"], "VP-100")
        self.assertEqual(epic_row["deliveryStart"], "2026-06-02")
        self.assertEqual(epic_row["deliveryEnd"], "2026-06-08")

        be_row = next(r for r in epic_row["tasks"] if r["task"] == "BE development")
        self.assertEqual(be_row["start"], "2026-06-02")
        self.assertEqual(be_row["end"], "2026-06-05")
        self.assertEqual(be_row["effortsHours"], 8.0)

    def test_planned_leave_hours_on_side(self):
        epic = _epic("VP-200")
        dev = _issue("VP-201", "BE || work", 3600, parent_key="VP-200")
        leave = _issue("VP-202", "Leave | Planned - holiday", 7200, parent_key="VP-200")
        schedule = {"scheduled": []}
        result = build_timeline_breakdown([epic, dev, leave], schedule, MINIMAL_CONFIG)
        be_row = next(r for r in result[0]["tasks"] if r["task"] == "BE development")
        self.assertEqual(be_row["plannedLeaveHours"], 2.0)

    def test_members_by_side_two_backend(self):
        epic = _epic("VP-300")
        t1 = _issue("VP-301", "BE || API one", 7200, parent_key="VP-300", assignee="Alice")
        t2 = _issue("VP-302", "BE || API two", 10800, parent_key="VP-300", assignee="Bob")
        schedule = {
            "scheduled": [
                {"key": "VP-301", "startDate": "2026-06-01", "dueDate": "2026-06-02"},
                {"key": "VP-302", "startDate": "2026-06-03", "dueDate": "2026-06-05"},
            ]
        }
        result = build_timeline_breakdown([epic, t1, t2], schedule, MINIMAL_CONFIG)
        backend_members = result[0]["membersBySide"]["Backend"]
        self.assertEqual(len(backend_members), 2)
        by_name = {m["member"]: m for m in backend_members}
        self.assertEqual(by_name["Alice"]["effortsHours"], 2.0)
        self.assertEqual(by_name["Bob"]["effortsHours"], 3.0)
        self.assertEqual(by_name["Alice"]["start"], "2026-06-01")
        self.assertEqual(by_name["Bob"]["end"], "2026-06-05")
        self.assertEqual(len(result[0]["teamSummary"]["Backend"]["members"]), 2)


if __name__ == "__main__":
    unittest.main()
