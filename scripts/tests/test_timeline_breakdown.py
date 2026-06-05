"""Tests for timeline_breakdown.py."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from timeline_breakdown import (  # noqa: E402
    STAGE_DEVELOPMENT,
    STAGE_STAGE_TESTING,
    STAGE_TEST_PLANNING,
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
        "effortBuffers": {
            "bugFixesPercentOfDevelopment": 0.10,
            "stageFinalTestingPercentOfStageTesting": 0.10,
        },
        "leaveTaskPrefixes": {
            "planned": "Leave | Planned",
            "unplanned": "Leave | Unplanned",
        },
        "sideDisplay": {
            "backend": "Backend",
            "frontend": "Web",
            "mobile": "Mobile",
            "qa": "QA",
            "unknown": "Other",
        },
        "defaultTaskByTeam": {
            "backend": "Development",
            "frontend": "Development",
            "mobile": "Development",
        },
        "executionStages": {
            "backend": [
                "Assessment",
                "Development",
                "Stage testing",
                "Bug fixes",
                "Stage final testing",
                "Prod release",
                "Prod final testing",
                "Go live date",
            ],
            "frontend": [
                "Assessment",
                "Development",
                "Stage testing",
                "Bug fixes",
                "Stage final testing",
                "Pre-Prod testing",
                "UAT",
                "Ready for release",
                "Go live date",
            ],
            "mobile": [
                "Assessment",
                "Development",
                "Stage testing",
                "Bug fixes",
                "Stage final testing",
                "Pre-Prod testing",
                "UAT",
                "Ready for release",
                "Go live date",
            ],
        },
        "qaCrossPlatformStages": ["Test planning"],
        "stageMapping": [],
    },
}


def _stage_row(epic_row: dict, platform: str, stage: str) -> dict:
    block = epic_row["executionStages"][platform]
    return next(r for r in block["stages"] if r["stage"] == stage)


class TestCalcDays(unittest.TestCase):
    def test_six_hour_day(self):
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

    def test_be_assessment_prefix(self):
        issue = _issue("VP-2", "BE | Assessment", 3600)
        result = classify_issue(issue, MINIMAL_CONFIG["timeline"], MINIMAL_CONFIG["teams"])
        self.assertEqual(result["platform"], "backend")
        self.assertEqual(result["stage"], "Assessment")

    def test_be_development_pipe(self):
        issue = _issue("VP-2", "BE || Add endpoint", 14400)
        result = classify_issue(issue, MINIMAL_CONFIG["timeline"], MINIMAL_CONFIG["teams"])
        self.assertEqual(result["kind"], "work")
        self.assertEqual(result["stage"], STAGE_DEVELOPMENT)
        self.assertEqual(result["platform"], "backend")

    def test_qa_assessment_cross_platform(self):
        issue = _issue("VP-3", "QA | Assessment", 7200)
        result = classify_issue(issue, MINIMAL_CONFIG["timeline"], MINIMAL_CONFIG["teams"])
        self.assertEqual(result["platform"], "qa_cross")
        self.assertEqual(result["stage"], STAGE_TEST_PLANNING)

    def test_qa_web_stage_testing(self):
        issue = _issue("VP-4", "QA | WEB | 1st iteration (stage testing)", 3600)
        result = classify_issue(issue, MINIMAL_CONFIG["timeline"], MINIMAL_CONFIG["teams"])
        self.assertEqual(result["platform"], "frontend")
        self.assertEqual(result["stage"], STAGE_STAGE_TESTING)


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
        result = build_timeline_breakdown([epic, t1, t2], schedule, MINIMAL_CONFIG)
        epic_row = result[0]
        # Calendar dates are deferred — all start/end resolve to None.
        self.assertIsNone(epic_row["deliveryStart"])
        self.assertIsNone(epic_row["deliveryEnd"])

        be_row = _stage_row(epic_row, "backend", STAGE_DEVELOPMENT)
        self.assertIsNone(be_row["start"])
        self.assertIsNone(be_row["end"])
        self.assertEqual(be_row["effortsHours"], 8.0)
        bug_row = _stage_row(epic_row, "backend", "Bug fixes")
        self.assertEqual(bug_row["effortsHours"], 0.8)
        self.assertEqual(bug_row["source"], "synthetic")

        # hasWork: platforms with Jira tasks are flagged; empty ones are not.
        self.assertTrue(epic_row["executionStages"]["backend"]["hasWork"])
        self.assertTrue(epic_row["executionStages"]["frontend"]["hasWork"])
        self.assertFalse(epic_row["executionStages"]["mobile"]["hasWork"])

    def test_planned_leave_hours_on_side(self):
        epic = _epic("VP-200")
        dev = _issue("VP-201", "BE || work", 3600, parent_key="VP-200")
        leave = _issue("VP-202", "Leave | Planned - holiday", 7200, parent_key="VP-200")
        result = build_timeline_breakdown([epic, dev, leave], {"scheduled": []}, MINIMAL_CONFIG)
        be_row = _stage_row(result[0], "backend", STAGE_DEVELOPMENT)
        self.assertEqual(be_row["plannedLeaveHours"], 2.0)

    def test_web_preprod_separate_from_uat(self):
        epic = _epic("VP-600")
        pre = _issue(
            "VP-601",
            "QA | WEB | pre-prod validation",
            7200,
            parent_key="VP-600",
        )
        uat = _issue("VP-602", "QA | WEB | UAT stage", 3600, parent_key="VP-600")
        result = build_timeline_breakdown([epic, pre, uat], {"scheduled": []}, MINIMAL_CONFIG)[0]
        pre_row = _stage_row(result, "frontend", "Pre-Prod testing")
        uat_row = _stage_row(result, "frontend", "UAT")
        self.assertEqual(pre_row["effortsHours"], 2.0)
        self.assertEqual(uat_row["effortsHours"], 1.0)

    def test_mobile_preprod_not_web(self):
        epic = _epic("VP-601")
        mob = _issue(
            "VP-602",
            "QA | APP | mobile pre-prod",
            3600,
            parent_key="VP-601",
        )
        result = build_timeline_breakdown([epic, mob], {"scheduled": []}, MINIMAL_CONFIG)[0]
        mob_row = _stage_row(result, "mobile", "Pre-Prod testing")
        web_row = _stage_row(result, "frontend", "Pre-Prod testing")
        self.assertEqual(mob_row["effortsHours"], 1.0)
        self.assertIsNone(web_row["effortsHours"])

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
        # Member Start/End dates are deferred (rendered as placeholders).
        for member in backend_members:
            self.assertIsNone(member["start"])
            self.assertIsNone(member["end"])

    def test_qa_test_planning_not_tripled(self):
        epic = _epic("VP-700")
        qa = _issue("VP-701", "QA | Assessment", 9000, parent_key="VP-700")
        result = build_timeline_breakdown([epic, qa], {"scheduled": []}, MINIMAL_CONFIG)[0]
        qa_rows = result["qaCrossPlatform"]["stages"]
        planning = next(r for r in qa_rows if r["stage"] == STAGE_TEST_PLANNING)
        self.assertEqual(planning["effortsHours"], 2.5)
        for plat in ("backend", "frontend", "mobile"):
            assess = _stage_row(result, plat, "Assessment")
            self.assertIsNone(assess["effortsHours"])


if __name__ == "__main__":
    unittest.main()
