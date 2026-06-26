"""Tests for data_quality.py."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from sprintkit.jira_model import build_index  # noqa: E402
from sprintkit.quality import (  # noqa: E402
    REASON_EPIC_NOT_MAPPED,
    REASON_MISSING_ESTIMATE,
    REASON_MISSING_LOGGED_TIME,
    REASON_PARENT_NOT_MAPPED,
    REASON_PARENT_OUT_OF_SCOPE,
    REASON_QA_MISSING_PLATFORM,
    REASON_TIMELINE_UNMAPPED,
    REASON_UNASSIGNED,
    build_data_quality_by_member,
    collect_issue_flags,
    consolidate_dq_rows,
    count_dq_reasons,
)

CONFIG = {
    "fields": {"timeSpent": "timespent"},
    "dataQuality": {
        "bugActiveStatuses": ["To Do", "In Progress", "Hold", "Deferred"],
    },
}


def _issue(
    key: str,
    summary: str,
    estimate_seconds: int = 28800,
    parent_key: str | None = "VP-EPIC",
    issuetype: str = "Task",
    assignee: str = "Alice",
    status: str = "In Progress",
    timespent: int = 0,
) -> dict:
    fields: dict = {
        "summary": summary,
        "timeoriginalestimate": estimate_seconds,
        "timespent": timespent,
        "issuetype": {"name": issuetype},
        "status": {"name": status},
        "labels": [],
        "components": [],
    }
    if assignee:
        fields["assignee"] = {"displayName": assignee, "accountId": assignee}
    if parent_key:
        fields["parent"] = {
            "key": parent_key,
            "fields": {"issuetype": {"name": "Epic"}, "summary": "Epic title"},
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


class TestDataQuality(unittest.TestCase):
    def test_missing_estimate_by_member(self):
        epic = _epic("VP-1")
        task = _issue("VP-10", "No estimate task", 0, parent_key="VP-1")
        schedule = {"unscheduled": [{"key": "VP-10", "reason": "missing_estimate"}]}
        result = build_data_quality_by_member(
            [epic, task], schedule, None, {"Alice": "Alice"}
        )
        self.assertIn("Alice", result)
        reasons = [r["reason"] for r in result["Alice"]]
        self.assertIn(REASON_MISSING_ESTIMATE, reasons[0])
        self.assertEqual(result["Alice"][0]["key"], "VP-10")

    def test_parent_not_mapped(self):
        task = _issue("VP-20", "Orphan task", parent_key=None)
        result = build_data_quality_by_member(
            [task],
            {"unscheduled": []},
            None,
            {"Alice": "Alice"},
        )
        self.assertTrue(
            any(REASON_PARENT_NOT_MAPPED in r["reason"] for r in result["Alice"])
        )

    def test_parent_out_of_sprint(self):
        task = _issue("VP-30", "Bad parent", parent_key="VP-MISSING")
        result = build_data_quality_by_member(
            [task],
            {"unscheduled": []},
            None,
            {"Alice": "Alice"},
        )
        self.assertTrue(
            any(REASON_PARENT_OUT_OF_SCOPE in r["reason"] for r in result["Alice"])
        )

    def test_epic_not_mapped(self):
        story = {
            "key": "VP-STORY",
            "fields": {
                "summary": "Story slice",
                "issuetype": {"name": "Story"},
            },
        }
        task = _issue("VP-40", "Task under story", parent_key="VP-STORY")
        result = build_data_quality_by_member(
            [story, task],
            {"unscheduled": []},
            None,
            {"Alice": "Alice"},
        )
        self.assertTrue(
            any(REASON_EPIC_NOT_MAPPED in r["reason"] for r in result["Alice"])
        )

    def test_consolidate_single_reason(self):
        raw = {
            "Alice": [{"key": "VP-1", "title": "T", "reason": REASON_MISSING_ESTIMATE}]
        }
        merged = consolidate_dq_rows(raw)
        self.assertEqual(merged["Alice"][0]["reason"], REASON_MISSING_ESTIMATE)

    def test_bug_active_todo_no_time_flag(self):
        epic = _epic("VP-3")
        bug = _issue(
            "VP-50",
            "New bug",
            0,
            parent_key="VP-3",
            issuetype="Bug",
            assignee="Carol",
            status="TO  DO",
            timespent=0,
        )
        schedule = {"unscheduled": [{"key": "VP-50", "reason": "missing_estimate"}]}
        result = build_data_quality_by_member(
            [epic, bug],
            schedule,
            None,
            {"Carol": "Carol"},
            CONFIG,
        )
        reasons = [r["reason"] for r in result.get("Carol", [])]
        self.assertEqual(reasons, [])

    def test_bug_deferred_no_time_flag(self):
        epic = _epic("VP-3")
        bug = _issue(
            "VP-51",
            "Deferred bug",
            0,
            parent_key="VP-3",
            issuetype="Bug",
            assignee="Carol",
            status="Deferred",
            timespent=0,
        )
        result = build_data_quality_by_member(
            [epic, bug],
            {"unscheduled": []},
            None,
            {"Carol": "Carol"},
            CONFIG,
        )
        self.assertEqual(result.get("Carol", []), [])

    def test_bug_not_a_bug_skips_missing_logged_time(self):
        epic = _epic("VP-3")
        bug = _issue(
            "VP-55",
            "Rejected defect",
            0,
            parent_key="VP-3",
            issuetype="Bug",
            assignee="Carol",
            status="Not a Bug",
            timespent=0,
        )
        result = build_data_quality_by_member(
            [epic, bug],
            {"unscheduled": []},
            None,
            {"Carol": "Carol"},
            CONFIG,
        )
        self.assertEqual(result.get("Carol", []), [])

    def test_bug_ready_for_qa_without_logged_time(self):
        epic = _epic("VP-3")
        bug = _issue(
            "VP-52",
            "QA bug",
            0,
            parent_key="VP-3",
            issuetype="Bug",
            assignee="Carol",
            status="Ready For QA",
            timespent=0,
        )
        result = build_data_quality_by_member(
            [epic, bug],
            {"unscheduled": []},
            None,
            {"Carol": "Carol"},
            CONFIG,
        )
        self.assertIn(REASON_MISSING_LOGGED_TIME, result["Carol"][0]["reason"])

    def test_bug_ready_for_qa_with_logged_time(self):
        epic = _epic("VP-3")
        bug = _issue(
            "VP-53",
            "Logged QA bug",
            0,
            parent_key="VP-3",
            issuetype="Bug",
            assignee="Carol",
            status="Ready For QA",
            timespent=7200,
        )
        result = build_data_quality_by_member(
            [epic, bug],
            {"unscheduled": []},
            None,
            {"Carol": "Carol"},
            CONFIG,
        )
        self.assertEqual(result.get("Carol", []), [])

    def test_bug_with_timespent_skips_missing_logged_time(self):
        epic = _epic("VP-3")
        bug = _issue(
            "VP-54",
            "Closed bug",
            0,
            parent_key="VP-3",
            issuetype="Bug",
            assignee="Carol",
            status="Closed",
            timespent=7200,
        )
        result = build_data_quality_by_member(
            [epic, bug],
            {"unscheduled": []},
            None,
            {"Carol": "Carol"},
            CONFIG,
        )
        self.assertEqual(result.get("Carol", []), [])

    def test_consolidate_multiple_reasons(self):
        raw = {
            "Unassigned": [
                {"key": "VP-1", "title": "Bug", "reason": REASON_MISSING_LOGGED_TIME},
                {"key": "VP-1", "title": "Bug", "reason": REASON_PARENT_OUT_OF_SCOPE},
                {"key": "VP-1", "title": "Bug", "reason": REASON_UNASSIGNED},
            ]
        }
        merged = consolidate_dq_rows(raw)
        self.assertEqual(len(merged["Unassigned"]), 1)
        reason = merged["Unassigned"][0]["reason"]
        self.assertIn(REASON_MISSING_LOGGED_TIME, reason)
        self.assertIn(REASON_PARENT_OUT_OF_SCOPE, reason)
        self.assertIn(REASON_UNASSIGNED, reason)

    def test_count_dq_reasons(self):
        by_member = {
            "Alice": [
                {
                    "key": "VP-1",
                    "title": "T",
                    "reason": f"{REASON_MISSING_ESTIMATE}; {REASON_UNASSIGNED}",
                }
            ]
        }
        counts = count_dq_reasons(by_member)
        self.assertEqual(counts[REASON_MISSING_ESTIMATE], 1)
        self.assertEqual(counts[REASON_UNASSIGNED], 1)

    def test_assignee_display_falls_back_to_display_name(self):
        issue = _issue("VP-99", "APP | work", parent_key="VP-EPIC", assignee="Carol")
        issue["fields"]["assignee"] = {
            "accountId": "acct-123",
            "displayName": "Carol Smith",
        }
        from sprintkit.quality import assignee_display

        self.assertEqual(assignee_display(issue, {}), "Carol Smith")

    def test_qa_without_platform_not_dq_flagged(self):
        issue = _issue("VP-99", "QA | Assessment", parent_key="VP-EPIC", assignee="Carol")
        config = {
            **CONFIG,
            "teams": {"qa": ["qa"]},
            "teamPrefixMapping": {
                "qa": {"aliases": ["qa"]},
                "backend": {"aliases": ["be"]},
                "frontend": {"aliases": ["web"]},
                "mobile": {"aliases": ["app"]},
            },
        }
        index = build_index([issue])
        reasons = collect_issue_flags(issue, index, set(), config)
        self.assertNotIn(REASON_QA_MISSING_PLATFORM, reasons)
        self.assertNotIn(REASON_TIMELINE_UNMAPPED, reasons)

    def test_qa_additional_effort_skips_timeline_dq(self):
        epic = _epic("VP-2")
        task = _issue(
            "VP-99",
            "QA | KT session",
            parent_key="VP-2",
            assignee="Carol",
            estimate_seconds=3600,
        )
        timeline = [
            {
                "epicKey": "VP-2",
                "unmapped": [
                    {
                        "key": "VP-99",
                        "summary": "QA | KT session",
                        "assignee": "Carol",
                        "effortsHours": 1,
                        "additionalEffort": True,
                    }
                ],
            }
        ]
        result = build_data_quality_by_member(
            [epic, task],
            {"unscheduled": [], "violations": []},
            timeline,
            {"Carol": "Carol"},
        )
        all_reasons = [r["reason"] for rows in result.values() for r in rows]
        self.assertFalse(any(REASON_TIMELINE_UNMAPPED in r for r in all_reasons))

    def test_timeline_unmapped(self):
        epic = _epic("VP-2")
        task = _issue("VP-40", "Stage work", parent_key="VP-2", assignee="Bob")
        timeline = [
            {
                "epicKey": "VP-2",
                "unmapped": [
                    {
                        "key": "VP-40",
                        "summary": "Stage | foo",
                        "assignee": "Bob",
                        "effortsHours": 2,
                    }
                ],
            }
        ]
        result = build_data_quality_by_member(
            [epic, task],
            {"unscheduled": [], "violations": []},
            timeline,
            {"Bob": "Bob"},
        )
        self.assertTrue(
            any(REASON_TIMELINE_UNMAPPED in r["reason"] for r in result["Bob"])
        )

    def test_parent_task_not_flagged_when_subtasks_have_estimates(self):
        epic = _epic("VP-2")
        parent = _issue("VP-50", "APP | Development", parent_key="VP-2", assignee="Rajat")
        sub = _issue(
            "VP-51",
            "APP | slice",
            estimate_seconds=14400,
            parent_key="VP-50",
            issuetype="Sub-task",
            assignee="Rajat",
        )
        index = build_index([epic, parent, sub])
        reasons = collect_issue_flags(parent, index, set(), CONFIG)
        self.assertNotIn(REASON_MISSING_ESTIMATE, reasons)


if __name__ == "__main__":
    unittest.main()
