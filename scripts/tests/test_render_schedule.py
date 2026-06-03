"""Tests for Team tasks plan and bug effort tables in render_report.py."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from render_report import (  # noqa: E402
    epic_prd_anchor,
    epic_title_link,
    phase_for_epic,
    render_bug_sections,
    render_data_quality_section,
    render_report,
    render_schedule_delta_section,
    render_team_tasks_plan,
    schedule_member_anchor,
)


def _issue(key: str, summary: str, assignee: str = "Alice") -> dict:
    return {
        "key": key,
        "fields": {
            "summary": summary,
            "assignee": {"displayName": assignee, "accountId": assignee},
            "issuetype": {"name": "Task"},
            "labels": [],
            "components": [],
        },
    }


CONFIG = {
    "teams": {"backend": ["be"], "qa": ["qa"]},
    "teamPrefixMapping": {
        "backend": {"aliases": ["be"]},
        "qa": {"aliases": ["qa"]},
    },
    "timeline": {
        "sideDisplay": {
            "backend": "Backend",
            "frontend": "Web",
            "qa": "QA",
            "other": "Other",
        }
    },
    "statusPhaseMap": {
        "To Do": "PRD Tech Discussion",
        "TO  DO": "PRD Tech Discussion",
        "In Progress": "Development",
    },
    "dataQuality": {
        "bugActiveStatuses": ["To Do", "In Progress", "Hold", "Deferred"],
    },
}


class TestScheduleAnchor(unittest.TestCase):
    def test_slug(self):
        self.assertEqual(schedule_member_anchor("Aman Gupta"), "aman-gupta")

    def test_epic_prd_anchor(self):
        self.assertEqual(epic_prd_anchor("VP-19350"), "prd-vp-19350")

    def test_epic_title_link(self):
        linked = epic_title_link("Events phase 1 <> PRD", "VP-19350", True)
        self.assertEqual(linked, "[Events phase 1 <> PRD](#prd-vp-19350)")
        plain = epic_title_link("No timeline", "VP-1", False)
        self.assertEqual(plain, "No timeline")


class TestTeamTasksPlan(unittest.TestCase):
    def test_member_tables_no_schedule_index(self):
        by_assignee = {
            "alice": [
                {
                    "key": "VP-1",
                    "epicKey": "E1",
                    "assignee": "alice",
                    "startDate": "2026-06-03",
                    "dueDate": "2026-06-05",
                    "status": "on_track",
                },
                {
                    "key": "VP-2",
                    "epicKey": "E1",
                    "assignee": "alice",
                    "startDate": "2026-06-01",
                    "dueDate": "2026-06-02",
                    "status": "delayed",
                },
            ]
        }
        issues = [
            _issue("VP-1", "BE || task one"),
            _issue("VP-2", "BE || task two"),
        ]
        issue_by_key = {i["key"]: i for i in issues}
        est = {"VP-1": 7200, "VP-2": 3600}
        lines = render_team_tasks_plan(
            by_assignee,
            {"alice": "Alice"},
            issue_by_key,
            est,
            None,
            CONFIG,
        )
        body = "\n".join(lines)
        self.assertIn("## Team tasks plan", body)
        self.assertNotIn("Schedule by assignee", body)
        self.assertNotIn("| Team | Member |", body)
        self.assertIn("### Alice", body)
        self.assertIn("| Key | Task title | Epic | Effort | Status |", body)
        self.assertIn("| 2h |", body)
        self.assertIn("| 1h |", body)


class TestBugEffortTable(unittest.TestCase):
    def test_epic_side_columns_and_member_without_team(self):
        bug_data = [
            {
                "epicKey": "VP-2",
                "prdName": "Test PRD",
                "totalBugHours": 3.0,
                "bugCount": 2,
                "members": [
                    {
                        "member": "Alice",
                        "effortsHours": 2.0,
                        "bugCount": 1,
                        "sides": ["Backend"],
                    },
                    {
                        "member": "Bob",
                        "effortsHours": 1.0,
                        "bugCount": 1,
                        "sides": ["Web"],
                    },
                ],
                "bySide": {},
            }
        ]
        body = "\n".join(render_bug_sections(bug_data, None))
        self.assertIn("| Epic ID | Epic Name | Backend | Web | Mobile | Bugs |", body)
        self.assertIn("| VP-2 | Test PRD | 2.0 | 1.0 | — | 2 |", body)
        self.assertNotIn("#### By team", body)
        self.assertIn("| Member | Bug effort (h) | Bug count |", body)
        self.assertNotIn("| Member | Team |", body)


class TestPhaseForEpic(unittest.TestCase):
    def test_phase_uses_config_status_map(self):
        epic = {
            "key": "E1",
            "fields": {
                "summary": "Epic",
                "issuetype": {"name": "Epic", "hierarchyLevel": 1},
                "status": {"name": "In Progress"},
            },
        }
        task = {
            "key": "T1",
            "fields": {
                "summary": "Task",
                "issuetype": {"name": "Task"},
                "status": {"name": "TO  DO"},
                "parent": {"key": "E1", "fields": {"issuetype": {"name": "Epic"}}},
            },
        }
        self.assertEqual(phase_for_epic("E1", [epic, task], CONFIG), "Development")


class TestDataQualitySection(unittest.TestCase):
    def test_reason_summary_table(self):
        by_member = {
            "Alice": [
                {
                    "key": "VP-1",
                    "title": "Task",
                    "reason": "Missing estimates; Unassigned",
                }
            ]
        }
        body = "\n".join(render_data_quality_section(by_member, None))
        self.assertIn("## Data quality flags", body)
        self.assertIn("| Reason | Count |", body)
        self.assertIn("| Missing estimates | 1 |", body)
        self.assertIn("| Unassigned | 1 |", body)


class TestScheduleDeltaSection(unittest.TestCase):
    def test_renders_date_changes(self):
        delta = {
            "newly_scheduled": [],
            "newly_unscheduled": [],
            "date_changes": [
                {
                    "key": "VP-9",
                    "priorStart": "2026-06-01",
                    "priorDue": "2026-06-02",
                    "startDate": "2026-06-03",
                    "dueDate": "2026-06-04",
                }
            ],
            "status_changes": [],
        }
        body = "\n".join(render_schedule_delta_section(delta, None))
        self.assertIn("## Schedule Delta", body)
        self.assertIn("VP-9", body)


class TestExecutiveSummary(unittest.TestCase):
    def test_unscheduled_breakdown_narrative(self):
        bug = {
            "key": "B1",
            "fields": {
                "summary": "Bug",
                "issuetype": {"name": "Bug"},
                "status": {"name": "TO  DO"},
                "timeoriginalestimate": 0,
                "timespent": 0,
            },
        }
        task = _issue("T1", "No est", assignee="Alice")
        task["fields"]["timeoriginalestimate"] = 0
        body = render_report(
            [bug, task],
            {"scheduled": [], "unscheduled": [{"key": "B1"}, {"key": "T1"}]},
            {"items": [], "sprintStart": "2026-06-01", "sprintEnd": "2026-06-12"},
            "VP",
            "Sprint",
            None,
            config=CONFIG,
        )
        self.assertIn("active bugs (estimate not required yet)", body)
        self.assertIn("tasks missing Original Estimate", body)


if __name__ == "__main__":
    unittest.main()
