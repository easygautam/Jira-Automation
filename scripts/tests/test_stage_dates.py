"""Tests for stage_dates.py."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from sprintkit.stage_dates import (  # noqa: E402
    backend_verification_required_days,
    compute_stage_dates,
    signed_business_day_gap,
)
from sprintkit.stages import (  # noqa: E402
    STAGE_DEVELOPMENT,
    STAGE_GO_LIVE,
    STAGE_QA_TEST_PLANNING,
    STAGE_TECH_SOLUTIONING,
)


def _issue(
    key: str,
    summary: str,
    *,
    estimate_seconds: int = 0,
    parent_key: str = "E1",
    parent_type: str = "Epic",
    start_date: str | None = None,
    issuetype: str = "Task",
) -> dict:
    fields: dict = {
        "summary": summary,
        "timeoriginalestimate": estimate_seconds,
        "issuetype": {"name": issuetype},
        "assignee": {"displayName": "Alice", "accountId": "alice"},
        "parent": {"key": parent_key, "fields": {"issuetype": {"name": parent_type}}},
    }
    if start_date:
        fields["customfield_10015"] = start_date
    return {"key": key, "fields": fields}


def _epic(key: str = "E1") -> dict:
    return {"key": key, "fields": {"issuetype": {"name": "Epic", "hierarchyLevel": 1}}}


CONFIG = {
    "fields": {"startDate": "customfield_10015"},
    "scheduling": {"workingDayInts": [0, 1, 2, 3, 4]},
    "timeline": {
        "hoursPerDay": 6,
        "effortBuffers": {
            "backendVerificationPercentOfFeDevelopment": 0.15,
            "backendVerificationMaxDays": 2,
        },
    },
}


def _stage_row(
    stage: str,
    calc_days: float | None,
    issue_keys: list[str],
    *,
    efforts_hours: float | None = None,
) -> dict:
    row = {
        "stage": stage,
        "calculatedDays": calc_days,
        "issueKeys": issue_keys,
        "plannedLeaveHours": 0.0,
        "unplannedDelayHours": 0.0,
    }
    if efforts_hours is not None:
        row["effortsHours"] = efforts_hours
    elif issue_keys and calc_days:
        row["effortsHours"] = float(calc_days) * 6
    return row


def _platform_block(stages: list[dict], has_work: bool = True) -> dict:
    return {"hasWork": has_work, "stages": stages}


class TestComputeStageDates(unittest.TestCase):
    def test_assessment_and_dev_anchors(self):
        issues = [
            _issue("E1-AS", "BE | Assessment | API", start_date="2026-06-02"),
            _issue("E1-DEV", "BE || API work", start_date="2026-06-05"),
        ]
        epic_row = {
            "epicKey": "E1",
            "executionStages": {
                "backend": _platform_block(
                    [
                        _stage_row(STAGE_TECH_SOLUTIONING, 2, ["E1-AS"]),
                        _stage_row(STAGE_DEVELOPMENT, 3, ["E1-DEV"]),
                        _stage_row(STAGE_GO_LIVE, 1, []),
                    ]
                ),
                "frontend": _platform_block([], has_work=False),
                "mobile": _platform_block([], has_work=False),
            },
        }
        compute_stage_dates(epic_row, issues, CONFIG)
        be = epic_row["executionStages"]["backend"]["stages"]
        self.assertEqual(be[0]["start"], "2026-06-02")
        self.assertEqual(be[0]["end"], "2026-06-03")
        self.assertEqual(be[1]["start"], "2026-06-05")
        self.assertEqual(be[1]["end"], "2026-06-09")
        # Go live has no tasks/effort — no dates; epic go-live falls back to last stage end
        self.assertIsNone(be[2]["start"])
        self.assertIsNone(be[2]["end"])
        self.assertEqual(epic_row["deliveryStart"], "2026-06-02")
        self.assertEqual(epic_row["goLive"], "2026-06-09")

    def test_missing_start_renders_none(self):
        issues = [_issue("E1-DEV", "BE || work")]
        epic_row = {
            "executionStages": {
                "backend": _platform_block(
                    [
                        _stage_row(STAGE_TECH_SOLUTIONING, 2, []),
                        _stage_row(STAGE_DEVELOPMENT, 2, ["E1-DEV"]),
                    ]
                ),
                "frontend": _platform_block([], has_work=False),
                "mobile": _platform_block([], has_work=False),
            },
        }
        compute_stage_dates(epic_row, issues, CONFIG)
        stages = epic_row["executionStages"]["backend"]["stages"]
        self.assertIsNone(stages[0]["start"])
        self.assertIsNone(stages[0]["end"])
        self.assertIsNone(stages[1]["start"])
        self.assertIsNone(epic_row["deliveryStart"])

    def test_web_dev_uses_jira_start_not_be_end(self):
        issues = [
            _issue("BE-D", "BE || API", start_date="2026-06-02"),
            _issue("WEB-D", "WEB || UI", start_date="2026-06-03"),
        ]
        epic_row = {
            "executionStages": {
                "backend": _platform_block(
                    [_stage_row(STAGE_DEVELOPMENT, 2, ["BE-D"])]
                ),
                "frontend": _platform_block(
                    [_stage_row(STAGE_DEVELOPMENT, 2, ["WEB-D"])]
                ),
                "mobile": _platform_block([], has_work=False),
            },
        }
        compute_stage_dates(epic_row, issues, CONFIG)
        web_start = epic_row["executionStages"]["frontend"]["stages"][0]["start"]
        self.assertEqual(web_start, "2026-06-03")

    def test_mobile_dev_not_delayed_by_be_end(self):
        issues = [
            _issue("BE-D", "BE || API", start_date="2026-06-02"),
            _issue("APP-PARENT", "App | Development", start_date="2026-06-17"),
            _issue(
                "ST1",
                "sub work",
                parent_key="APP-PARENT",
                parent_type="Task",
                issuetype="Sub-task",
            ),
        ]
        epic_row = {
            "executionStages": {
                "backend": _platform_block(
                    [_stage_row(STAGE_DEVELOPMENT, 10, ["BE-D"])]
                ),
                "frontend": _platform_block([], has_work=False),
                "mobile": _platform_block(
                    [_stage_row(STAGE_DEVELOPMENT, 2, ["ST1"], efforts_hours=12)]
                ),
            },
        }
        compute_stage_dates(epic_row, issues, CONFIG)
        mobile_start = epic_row["executionStages"]["mobile"]["stages"][0]["start"]
        self.assertEqual(mobile_start, "2026-06-17")

    def test_empty_stage_has_no_dates_chain_skips_it(self):
        issues = [_issue("E1-AS", "BE | Assessment", start_date="2026-06-02")]
        epic_row = {
            "executionStages": {
                "backend": _platform_block(
                    [
                        _stage_row(STAGE_TECH_SOLUTIONING, 0.5, ["E1-AS"], efforts_hours=3),
                        {
                            "stage": STAGE_QA_TEST_PLANNING,
                            "calculatedDays": None,
                            "issueKeys": [],
                            "effortsHours": None,
                            "plannedLeaveHours": 0.0,
                            "unplannedDelayHours": 0.0,
                        },
                        _stage_row(STAGE_DEVELOPMENT, 4.33, [], efforts_hours=14),
                    ]
                ),
                "frontend": _platform_block([], has_work=False),
                "mobile": _platform_block([], has_work=False),
            },
        }
        compute_stage_dates(epic_row, issues, CONFIG)
        stages = epic_row["executionStages"]["backend"]["stages"]
        self.assertEqual(stages[0]["start"], "2026-06-02")
        self.assertIsNone(stages[1]["start"])
        self.assertIsNone(stages[1]["end"])
        self.assertIsNone(stages[2]["start"])

    def test_sub_day_synthetic_stages_share_calendar_day(self):
        from sprintkit.stages import STAGE_BUG_FIXES, STAGE_STAGE_FINAL_TESTING, STAGE_STAGE_TESTING

        epic_row = {
            "executionStages": {
                "backend": _platform_block([], has_work=False),
                "frontend": _platform_block(
                    [
                        _stage_row(STAGE_STAGE_TESTING, 2, ["WEB-QA"], efforts_hours=12),
                        {
                            "stage": STAGE_BUG_FIXES,
                            "calculatedDays": None,
                            "issueKeys": [],
                            "effortsHours": 0.2,
                            "resources": None,
                            "source": "synthetic",
                            "plannedLeaveHours": 0.0,
                            "unplannedDelayHours": 0.0,
                        },
                        {
                            "stage": STAGE_STAGE_FINAL_TESTING,
                            "calculatedDays": None,
                            "issueKeys": [],
                            "effortsHours": 1.2,
                            "resources": None,
                            "source": "synthetic",
                            "plannedLeaveHours": 0.0,
                            "unplannedDelayHours": 0.0,
                        },
                    ]
                ),
                "mobile": _platform_block([], has_work=False),
            },
        }
        issues = [
            _issue("WEB-QA", "QA | Web | Testing", start_date="2026-06-23"),
        ]
        compute_stage_dates(epic_row, issues, CONFIG)
        stages = epic_row["executionStages"]["frontend"]["stages"]
        testing = stages[0]
        bug = stages[1]
        final = stages[2]
        self.assertEqual(testing["start"], "2026-06-23")
        self.assertEqual(testing["end"], "2026-06-24")
        self.assertAlmostEqual(bug["calculatedDays"], 0.03, places=2)
        self.assertEqual(bug["start"], "2026-06-25")
        self.assertEqual(bug["end"], "2026-06-25")
        self.assertAlmostEqual(final["calculatedDays"], 0.2, places=2)
        self.assertEqual(final["start"], "2026-06-25")
        self.assertEqual(final["end"], "2026-06-25")

    def test_parent_task_start_anchors_subtask_only_stage(self):
        issues = [
            _epic(),
            _issue("T-PARENT", "App | Development", start_date="2026-06-17"),
            _issue(
                "ST1",
                "sub work",
                parent_key="T-PARENT",
                parent_type="Task",
                issuetype="Sub-task",
            ),
        ]
        epic_row = {
            "executionStages": {
                "backend": _platform_block([], has_work=False),
                "frontend": _platform_block([], has_work=False),
                "mobile": _platform_block(
                    [_stage_row(STAGE_DEVELOPMENT, 2, ["ST1"], efforts_hours=12)]
                ),
            },
        }
        compute_stage_dates(epic_row, issues, CONFIG)
        dev = epic_row["executionStages"]["mobile"]["stages"][0]
        self.assertEqual(dev["start"], "2026-06-17")

    def test_earliest_start_wins_parent_vs_subtask(self):
        issues = [
            _epic(),
            _issue("T-PARENT", "App | Development", start_date="2026-06-17"),
            _issue(
                "ST1",
                "sub work",
                parent_key="T-PARENT",
                parent_type="Task",
                issuetype="Sub-task",
                start_date="2026-06-10",
            ),
        ]
        epic_row = {
            "executionStages": {
                "backend": _platform_block([], has_work=False),
                "frontend": _platform_block([], has_work=False),
                "mobile": _platform_block(
                    [_stage_row(STAGE_DEVELOPMENT, 2, ["ST1"], efforts_hours=12)]
                ),
            },
        }
        compute_stage_dates(epic_row, issues, CONFIG)
        dev = epic_row["executionStages"]["mobile"]["stages"][0]
        self.assertEqual(dev["start"], "2026-06-10")

    def test_story_ancestor_included_epic_start_excluded(self):
        issues = [
            _epic(),
            _issue(
                "STORY-1",
                "Story",
                parent_key="E1",
                parent_type="Epic",
                issuetype="Story",
                start_date="2026-06-05",
            ),
            _issue(
                "T1",
                "App | Development",
                parent_key="STORY-1",
                parent_type="Story",
            ),
            _issue(
                "ST1",
                "sub",
                parent_key="T1",
                parent_type="Task",
                issuetype="Sub-task",
            ),
        ]
        epic_row = {
            "executionStages": {
                "backend": _platform_block([], has_work=False),
                "frontend": _platform_block([], has_work=False),
                "mobile": _platform_block(
                    [_stage_row(STAGE_DEVELOPMENT, 2, ["ST1"], efforts_hours=12)]
                ),
            },
        }
        compute_stage_dates(epic_row, issues, CONFIG)
        dev = epic_row["executionStages"]["mobile"]["stages"][0]
        self.assertEqual(dev["start"], "2026-06-05")


class TestBackendVerificationBuffer(unittest.TestCase):
    WORKING = {0, 1, 2, 3, 4}
    BUFFERS = {
        "backendVerificationPercentOfFeDevelopment": 0.15,
        "backendVerificationMaxDays": 2,
    }

    def test_required_days_capped_at_two_calendar_days(self):
        row = {"effortsHours": 114.0, "resources": 3.0}
        self.assertEqual(
            backend_verification_required_days(row, self.BUFFERS, 6.0),
            2.0,
        )

    def test_required_days_from_fe_development_hours(self):
        row = {"effortsHours": 60.0, "resources": 1.0}
        self.assertEqual(
            backend_verification_required_days(row, self.BUFFERS, 6.0),
            1.5,
        )

    def test_signed_gap_positive_when_fe_ends_after_be(self):
        from datetime import date

        gap = signed_business_day_gap(
            date(2026, 7, 2), date(2026, 7, 3), self.WORKING
        )
        self.assertEqual(gap, 1.0)

    def test_partial_buffer_when_fe_ends_one_day_after_be(self):
        issues = [
            _issue("BE-D", "BE || API", start_date="2026-06-02"),
            _issue("WEB-D", "WEB || UI", start_date="2026-06-03"),
        ]
        epic_row = {
            "executionStages": {
                "backend": _platform_block(
                    [_stage_row(STAGE_DEVELOPMENT, 2, ["BE-D"], efforts_hours=12)]
                ),
                "frontend": _platform_block(
                    [_stage_row(STAGE_DEVELOPMENT, 2, ["WEB-D"], efforts_hours=60)]
                ),
                "mobile": _platform_block([], has_work=False),
            },
        }
        compute_stage_dates(epic_row, issues, CONFIG)
        web = epic_row["executionStages"]["frontend"]["stages"][0]
        self.assertEqual(web["start"], "2026-06-03")
        self.assertEqual(web["end"], "2026-06-05")
        self.assertAlmostEqual(web["backendVerificationBufferDays"], 0.5, places=2)
        self.assertEqual(web["backendVerificationRequiredDays"], 1.5)

    def test_full_buffer_when_fe_and_be_end_same_day(self):
        issues = [
            _issue("BE-D", "BE || API", start_date="2026-06-02"),
            _issue("WEB-D", "WEB || UI", start_date="2026-06-02"),
        ]
        epic_row = {
            "executionStages": {
                "backend": _platform_block(
                    [_stage_row(STAGE_DEVELOPMENT, 2, ["BE-D"], efforts_hours=12)]
                ),
                "frontend": _platform_block(
                    [_stage_row(STAGE_DEVELOPMENT, 2, ["WEB-D"], efforts_hours=60)]
                ),
                "mobile": _platform_block([], has_work=False),
            },
        }
        compute_stage_dates(epic_row, issues, CONFIG)
        web = epic_row["executionStages"]["frontend"]["stages"][0]
        self.assertEqual(web["end"], "2026-06-05")
        self.assertEqual(web["backendVerificationBufferDays"], 1.5)

    def test_buffer_when_fe_ends_before_be(self):
        issues = [
            _issue("BE-D", "BE || API", start_date="2026-06-02"),
            _issue("WEB-D", "WEB || UI", start_date="2026-06-02"),
        ]
        epic_row = {
            "executionStages": {
                "backend": _platform_block(
                    [_stage_row(STAGE_DEVELOPMENT, 4, ["BE-D"], efforts_hours=24)]
                ),
                "frontend": _platform_block(
                    [_stage_row(STAGE_DEVELOPMENT, 2, ["WEB-D"], efforts_hours=60)]
                ),
                "mobile": _platform_block([], has_work=False),
            },
        }
        compute_stage_dates(epic_row, issues, CONFIG)
        be = epic_row["executionStages"]["backend"]["stages"][0]
        web = epic_row["executionStages"]["frontend"]["stages"][0]
        self.assertEqual(be["end"], "2026-06-05")
        self.assertEqual(web["end"], "2026-06-09")
        self.assertEqual(web["backendVerificationBufferDays"], 3.5)

    def test_no_buffer_without_backend_development(self):
        issues = [_issue("WEB-D", "WEB || UI", start_date="2026-06-02")]
        epic_row = {
            "executionStages": {
                "backend": _platform_block([], has_work=False),
                "frontend": _platform_block(
                    [_stage_row(STAGE_DEVELOPMENT, 2, ["WEB-D"], efforts_hours=60)]
                ),
                "mobile": _platform_block([], has_work=False),
            },
        }
        compute_stage_dates(epic_row, issues, CONFIG)
        web = epic_row["executionStages"]["frontend"]["stages"][0]
        self.assertEqual(web["end"], "2026-06-03")
        self.assertNotIn("backendVerificationBufferDays", web)

    def test_downstream_stage_chains_from_buffered_development_end(self):
        from sprintkit.stages import STAGE_STAGE_TESTING

        issues = [
            _issue("BE-D", "BE || API", start_date="2026-06-02"),
            _issue("WEB-D", "WEB || UI", start_date="2026-06-02"),
            _issue("WEB-QA", "QA | Web | Testing", start_date="2026-06-10"),
        ]
        epic_row = {
            "executionStages": {
                "backend": _platform_block(
                    [_stage_row(STAGE_DEVELOPMENT, 2, ["BE-D"], efforts_hours=12)]
                ),
                "frontend": _platform_block(
                    [
                        _stage_row(STAGE_DEVELOPMENT, 2, ["WEB-D"], efforts_hours=60),
                        _stage_row(STAGE_STAGE_TESTING, 1, ["WEB-QA"], efforts_hours=6),
                    ]
                ),
                "mobile": _platform_block([], has_work=False),
            },
        }
        compute_stage_dates(epic_row, issues, CONFIG)
        web_stages = epic_row["executionStages"]["frontend"]["stages"]
        self.assertEqual(web_stages[0]["end"], "2026-06-05")
        self.assertEqual(web_stages[1]["start"], "2026-06-10")


if __name__ == "__main__":
    unittest.main()
