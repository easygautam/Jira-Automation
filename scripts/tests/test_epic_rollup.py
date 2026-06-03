"""Tests for epic rollup in render_report.py"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from render_report import (  # noqa: E402
    compute_epic_rollup,
    jira_issue_link,
    resolve_epic_summary,
    worst_status,
)


class TestEpicRollup(unittest.TestCase):
    def test_three_tasks_min_max(self):
        scheduled = [
            {"epicKey": "E1", "startDate": "2026-06-02", "dueDate": "2026-06-03", "status": "on_track"},
            {"epicKey": "E1", "startDate": "2026-06-04", "dueDate": "2026-06-06", "status": "delayed"},
            {"epicKey": "E1", "startDate": "2026-06-01", "dueDate": "2026-06-05", "status": "on_track"},
        ]
        engine_items = [{"key": "T1", "epicKey": "E1"}]
        rollup = compute_epic_rollup("E1", scheduled, [], engine_items)
        self.assertEqual(rollup["start"], "2026-06-01")
        self.assertEqual(rollup["due"], "2026-06-06")
        self.assertEqual(rollup["status"], "delayed")
        self.assertEqual(rollup["scheduled_count"], 3)

    def test_no_scheduled_tbd(self):
        rollup = compute_epic_rollup("E9", [], [{"key": "X"}], [])
        self.assertIsNone(rollup["start"])
        self.assertEqual(rollup["status"], "tbd")

    def test_worst_status_order(self):
        self.assertEqual(worst_status(["on_track", "delayed", "at_risk"]), "delayed")
        self.assertEqual(worst_status([]), "tbd")

    def test_jira_issue_link(self):
        link = jira_issue_link("https://physicswallah001.atlassian.net", "VP-19350")
        self.assertEqual(
            link,
            "[VP-19350](https://physicswallah001.atlassian.net/browse/VP-19350)",
        )
        self.assertEqual(jira_issue_link(None, "VP-1"), "VP-1")

    def test_resolve_epic_summary_from_parent(self):
        issues = [
            {
                "key": "VP-100",
                "fields": {
                    "parent": {
                        "key": "VP-19350",
                        "fields": {
                            "summary": "Events phase 1 <> PRD",
                            "issuetype": {"name": "Epic"},
                        },
                    }
                },
            }
        ]
        summary = resolve_epic_summary("VP-19350", issues, {})
        self.assertEqual(summary, "Events phase 1 <> PRD")


if __name__ == "__main__":
    unittest.main()
