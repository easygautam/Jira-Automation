"""Tests for data_quality.py."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from data_quality import (  # noqa: E402
    REASON_MISSING_ESTIMATE,
    REASON_PARENT_NOT_MAPPED,
    REASON_PARENT_OUT_OF_SCOPE,
    REASON_TIMELINE_UNMAPPED,
    build_data_quality_by_member,
)


def _issue(
    key: str,
    summary: str,
    estimate_seconds: int = 28800,
    parent_key: str | None = "VP-EPIC",
    issuetype: str = "Task",
    assignee: str = "Alice",
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
        engine = {"items": [{"key": "VP-10", "epicKey": "VP-1"}]}
        result = build_data_quality_by_member(
            [epic, task], schedule, engine, None, {"Alice": "Alice"}
        )
        self.assertIn("Alice", result)
        reasons = [r["reason"] for r in result["Alice"]]
        self.assertIn(REASON_MISSING_ESTIMATE, reasons)
        self.assertEqual(result["Alice"][0]["key"], "VP-10")

    def test_parent_not_mapped(self):
        task = _issue("VP-20", "Orphan task", parent_key=None)
        result = build_data_quality_by_member(
            [task],
            {"unscheduled": []},
            {"items": []},
            None,
            {"Alice": "Alice"},
        )
        self.assertTrue(
            any(r["reason"] == REASON_PARENT_NOT_MAPPED for r in result["Alice"])
        )

    def test_parent_out_of_sprint(self):
        task = _issue("VP-30", "Bad parent", parent_key="VP-MISSING")
        result = build_data_quality_by_member(
            [task],
            {"unscheduled": []},
            {"items": []},
            None,
            {"Alice": "Alice"},
        )
        self.assertTrue(
            any(r["reason"] == REASON_PARENT_OUT_OF_SCOPE for r in result["Alice"])
        )

    def test_bug_with_timespent_skips_missing_estimate(self):
        epic = _epic("VP-3")
        bug = _issue(
            "VP-50",
            "Logged bug",
            0,
            parent_key="VP-3",
            issuetype="Bug",
            assignee="Carol",
        )
        bug["fields"]["timespent"] = 7200
        schedule = {"unscheduled": [{"key": "VP-50", "reason": "missing_estimate"}]}
        engine = {"items": [{"key": "VP-50", "epicKey": "VP-3", "estimateSeconds": 7200}]}
        result = build_data_quality_by_member(
            [epic, bug],
            schedule,
            engine,
            None,
            {"Carol": "Carol"},
            {"fields": {"timeSpent": "timespent"}},
        )
        reasons = [r["reason"] for r in result.get("Carol", [])]
        self.assertNotIn(REASON_MISSING_ESTIMATE, reasons)

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
            {"items": []},
            timeline,
            {"Bob": "Bob"},
        )
        self.assertTrue(
            any(r["reason"] == REASON_TIMELINE_UNMAPPED for r in result["Bob"])
        )


if __name__ == "__main__":
    unittest.main()
