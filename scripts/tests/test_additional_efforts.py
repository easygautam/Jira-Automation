"""Tests for Additional efforts table builder."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from sprintkit.render.additional_efforts import (  # noqa: E402
    build_additional_efforts_rows,
    render_additional_efforts_markdown,
)


class TestAdditionalEfforts(unittest.TestCase):
    def test_single_member_qa_row(self):
        unmapped = [
            {
                "key": "PPL-1232",
                "assignee": "Shubham Bhandari",
                "effortsHours": 1.0,
                "team": "QA",
            }
        ]
        rows = build_additional_efforts_rows(
            unmapped, jira_site_url="https://example.atlassian.net"
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["team"], "QA")
        self.assertEqual(rows[0]["effortHours"], 1.0)
        self.assertIn("Shubham Bhandari (1h)", rows[0]["details"])
        self.assertIn("[PPL-1232](https://example.atlassian.net/browse/PPL-1232)", rows[0]["details"])

    def test_multi_member_same_team(self):
        unmapped = [
            {
                "key": "VP-1",
                "assignee": "Alice",
                "effortsHours": 2.0,
                "team": "Backend",
            },
            {
                "key": "VP-2",
                "assignee": "Bob",
                "effortsHours": 3.0,
                "team": "Backend",
            },
        ]
        rows = build_additional_efforts_rows(unmapped, jira_site_url=None)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["effortHours"], 5.0)
        self.assertIn("Alice (2h)", rows[0]["details"])
        self.assertIn("Bob (3h)", rows[0]["details"])

    def test_team_order_follows_plan(self):
        unmapped = [
            {"key": "W-1", "assignee": "A", "effortsHours": 1.0, "team": "Web"},
            {"key": "B-1", "assignee": "B", "effortsHours": 1.0, "team": "Backend"},
        ]
        rows = build_additional_efforts_rows(unmapped, jira_site_url=None)
        self.assertEqual([r["team"] for r in rows], ["Backend", "Web"])

    def test_markdown_section(self):
        lines = render_additional_efforts_markdown(
            [
                {
                    "key": "PPL-1232",
                    "assignee": "Shubham Bhandari",
                    "effortsHours": 1.0,
                    "team": "QA",
                }
            ],
            jira_site_url="https://example.atlassian.net",
        )
        text = "\n".join(lines)
        self.assertIn("## Additional efforts", text)
        self.assertIn("| QA |", text)
        self.assertIn("Shubham Bhandari (1h)", text)
        self.assertNotIn("Unmapped work", text)

    def test_empty_returns_no_lines(self):
        self.assertEqual(render_additional_efforts_markdown([], jira_site_url=None), [])


if __name__ == "__main__":
    unittest.main()
