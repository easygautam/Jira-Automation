"""Tests for stage_dates.py."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from sprintkit.stage_dates import compute_stage_dates  # noqa: E402
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
    start_date: str | None = None,
) -> dict:
    fields: dict = {
        "summary": summary,
        "timeoriginalestimate": estimate_seconds,
        "issuetype": {"name": "Task"},
        "assignee": {"displayName": "Alice", "accountId": "alice"},
        "parent": {"key": parent_key, "fields": {"issuetype": {"name": "Epic"}}},
    }
    if start_date:
        fields["customfield_10015"] = start_date
    return {"key": key, "fields": fields}


CONFIG = {
    "fields": {"startDate": "customfield_10015"},
    "scheduling": {"workingDayInts": [0, 1, 2, 3, 4]},
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

    def test_web_dev_respects_be_end(self):
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
        be_end = epic_row["executionStages"]["backend"]["stages"][0]["end"]
        web_start = epic_row["executionStages"]["frontend"]["stages"][0]["start"]
        self.assertEqual(be_end, "2026-06-03")
        self.assertEqual(web_start, "2026-06-04")

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


if __name__ == "__main__":
    unittest.main()
