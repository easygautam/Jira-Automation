"""Tests for Team tasks plan and bug effort tables in render_report.py."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from sprintkit.render.markdown import (  # noqa: E402
    epic_prd_anchor,
    epic_title_link,
    jira_issue_keys_linked,
    jira_issue_link,
)
from sprintkit.render.report import render_report  # noqa: E402
from sprintkit.render.sections import (  # noqa: E402
    phase_for_epic,
    render_bug_sections,
    render_data_quality_section,
    render_schedule_delta_section,
    render_team_tasks_plan,
    render_timeline_sections,
)

JIRA_SITE = "https://physicswallah001.atlassian.net"


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
    "jira": {"siteUrl": JIRA_SITE},
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


class TestJiraIssueLinks(unittest.TestCase):
    def test_issue_link_markdown(self):
        self.assertEqual(
            jira_issue_link(JIRA_SITE, "VP-20013"),
            "[VP-20013](https://physicswallah001.atlassian.net/browse/VP-20013)",
        )

    def test_issue_keys_linked_all_by_default(self):
        keys = ["VP-1", "VP-2", "VP-3", "VP-4", "VP-5"]
        linked = jira_issue_keys_linked(JIRA_SITE, keys)
        self.assertIn("[VP-5]", linked)
        self.assertNotIn("…", linked)

    def test_issue_keys_linked_truncates_when_limit_set(self):
        keys = ["VP-1", "VP-2", "VP-3", "VP-4", "VP-5"]
        linked = jira_issue_keys_linked(JIRA_SITE, keys, limit=4)
        self.assertIn("[VP-4]", linked)
        self.assertNotIn("[VP-5]", linked)
        self.assertTrue(linked.endswith("…"))


class TestAnchors(unittest.TestCase):
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
            JIRA_SITE,
            CONFIG,
        )
        body = "\n".join(lines)
        self.assertIn("## Team tasks plan", body)
        self.assertIn("[VP-1](https://physicswallah001.atlassian.net/browse/VP-1)", body)
        self.assertNotIn("Schedule by assignee", body)
        self.assertNotIn("| Team | Member |", body)
        self.assertIn("### Alice", body)
        self.assertIn("| Key | Task title | Epic | Effort | Status |", body)
        self.assertIn("| 2h |", body)
        self.assertIn("| 1h |", body)


class TestBugEffortTable(unittest.TestCase):
    def test_epic_side_columns_reconcile_to_total(self):
        bug_data = [
            {
                "epicKey": "VP-2",
                "prdName": "Test PRD",
                "totalBugHours": 3.0,
                "bugCount": 2,
                "members": [
                    {"member": "Alice", "effortsHours": 2.0, "bugCount": 1},
                    {"member": "Bob", "effortsHours": 1.0, "bugCount": 1},
                ],
                "sideHours": {"Backend": 2.0, "Web": 1.0},
            }
        ]
        body = "\n".join(render_bug_sections(bug_data, JIRA_SITE))
        self.assertIn(
            "| Epic ID | Epic Name | Backend | Web | Mobile | QA | Other | Total | Bugs |",
            body,
        )
        self.assertIn(
            "| [VP-2](https://physicswallah001.atlassian.net/browse/VP-2) "
            "| Test PRD | 2.0 | 1.0 | — | — | — | 3.0 | 2 |",
            body,
        )
        self.assertIn("**Sprint bug effort total:** 3.0 h (Backend 2.0, Web 1.0", body)
        self.assertIn("| Member | Bug effort (h) | Bug count |", body)
        self.assertNotIn("| Member | Team |", body)


class TestTimelineSectionsRender(unittest.TestCase):
    def _timeline(self) -> list[dict]:
        backend_stages = [
            {
                "stage": "Development",
                "source": "jira",
                "resources": 1.0,
                "effortsHours": 8.0,
                "plannedLeaveHours": 2.0,
                "unplannedDelayHours": 1.0,
                "start": None,
                "end": None,
                "calculatedDays": 2,
                "issueKeys": ["VP-101"],
            }
        ]
        web_stages = [
            {
                "stage": "Development",
                "source": None,
                "resources": None,
                "effortsHours": None,
                "plannedLeaveHours": 0.0,
                "unplannedDelayHours": 0.0,
                "start": None,
                "end": None,
                "calculatedDays": None,
                "issueKeys": [],
            }
        ]
        return [
            {
                "epicKey": "VP-100",
                "prdName": "Test PRD",
                "deliveryStart": None,
                "deliveryEnd": None,
                "goLive": None,
                "calendarDeliveryDays": None,
                "executionStages": {
                    "backend": {"hasWork": True, "stages": backend_stages},
                    "frontend": {"hasWork": False, "stages": web_stages},
                    "mobile": {"hasWork": False, "stages": []},
                },
                "teamSummary": {
                    "Backend": {
                        "peakResources": 1.0,
                        "totalEffortHours": 8.0,
                        "totalLeaveHours": 2.0,
                        "totalDelayHours": 1.0,
                        "taskCount": 1,
                        "members": [],
                    }
                },
                "membersBySide": {
                    "Backend": [
                        {
                            "member": "Alice",
                            "effortsHours": 8.0,
                            "plannedLeaveHours": 2.0,
                            "unplannedDelayHours": 1.0,
                            "start": None,
                            "end": None,
                            "calculatedDays": 2,
                            "issueCount": 1,
                            "issueKeys": ["VP-101"],
                            "tasks": ["Development"],
                        }
                    ]
                },
                "tasks": [],
                "unmapped": [],
            }
        ]

    def test_leave_and_delay_columns(self):
        body = "\n".join(render_timeline_sections(self._timeline(), JIRA_SITE))
        # Team summary: single combined Leave column (no separate Planned/Unplanned).
        self.assertIn(
            "| Team | Peak resources | Total effort (h) | Leave (h) | Tasks |", body
        )
        # Combined leave = planned 2 + unplanned 1 = 3.0
        self.assertIn("| Backend | 1.0 | 8.0 | 3.0 | 1 |", body)
        # Member breakdown keeps both Planned leave + Unplanned delay columns.
        self.assertIn("| Member | Efforts (h) | Planned leave (h) | Unplanned delay (h) |", body)
        # Execution-stage table has no Delay (h) column and combines leave; no Start/End.
        self.assertIn("| Stage | Resources | Efforts (h) | Leave (h) | Calc days |", body)
        self.assertNotIn("Delay (h)", body)
        self.assertNotIn("| Start | End |", body)
        self.assertIn(
            "[VP-101](https://physicswallah001.atlassian.net/browse/VP-101)",
            body,
        )

    def test_empty_platform_table_omitted_and_dates_dashed(self):
        body = "\n".join(render_timeline_sections(self._timeline(), JIRA_SITE))
        # Backend has work; Web/Mobile do not → only Backend stage table rendered.
        self.assertIn("**Backend**", body)
        self.assertNotIn("**Web**", body)
        self.assertNotIn("**Mobile**", body)
        # Date-only lines removed.
        self.assertNotIn("Epic delivery window", body)
        self.assertNotIn("Go live", body)
        # Member row: Start/End columns removed; Calc days follows Unplanned delay.
        self.assertIn("| Alice | 8.0 | 2.0 | 1.0 | 2 |", body)


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
        body = "\n".join(render_data_quality_section(by_member, JIRA_SITE))
        self.assertIn("## Data quality flags", body)
        self.assertIn("[VP-1](https://physicswallah001.atlassian.net/browse/VP-1)", body)
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
        body = "\n".join(render_schedule_delta_section(delta, JIRA_SITE))
        self.assertIn("## Schedule Delta", body)
        self.assertIn(
            "[VP-9](https://physicswallah001.atlassian.net/browse/VP-9)",
            body,
        )


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
        self.assertIn("[B1](https://physicswallah001.atlassian.net/browse/B1)", body)
        self.assertIn("active bugs (estimate not required yet)", body)
        self.assertIn("tasks missing Original Estimate", body)


if __name__ == "__main__":
    unittest.main()
