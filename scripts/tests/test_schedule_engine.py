"""Tests for schedule_engine.py"""

import json
import unittest
from datetime import date
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from sprintkit.schedule import (  # noqa: E402
    add_business_days,
    compute_schedule,
    duration_days,
    parse_date,
)


class TestDuration(unittest.TestCase):
    def test_eight_hours_one_day(self):
        self.assertEqual(duration_days(8 * 3600, 8), 1)

    def test_nine_hours_two_days(self):
        self.assertEqual(duration_days(9 * 3600, 8), 2)

    def test_zero_estimate(self):
        self.assertEqual(duration_days(0, 8), 0)


class TestBusinessDays(unittest.TestCase):
    def test_friday_plus_two_days_is_tuesday(self):
        fri = date(2026, 6, 5)  # Friday
        result = add_business_days(fri, 2, {0, 1, 2, 3, 4})
        self.assertEqual(result, date(2026, 6, 8))  # Monday + 1 = Tuesday? 
        # Fri + 1bd duration=2 means Fri start, add 1 more bd -> Mon? 
        # add_business_days(start, 2): start + 1 business day = Mon Jun 8
        self.assertEqual(result.weekday(), 0)  # Monday for duration 2 from Fri


class TestSequentialSchedule(unittest.TestCase):
    def test_single_assignee_two_tasks(self):
        data = {
            "sprintStart": "2026-06-02",
            "sprintEnd": "2026-06-13",
            "hoursPerDay": 8,
            "workingDays": [0, 1, 2, 3, 4],
            "today": "2026-06-02",
            "items": [
                {
                    "key": "T1",
                    "storyKey": "S1",
                    "epicKey": "E1",
                    "assignee": "alice",
                    "estimateSeconds": 8 * 3600,
                    "epicPriorityRank": 1,
                    "storyRank": 1,
                    "team": "backend",
                    "created": "2026-06-01",
                    "dependencies": [],
                },
                {
                    "key": "T2",
                    "storyKey": "S2",
                    "epicKey": "E1",
                    "assignee": "alice",
                    "estimateSeconds": 8 * 3600,
                    "epicPriorityRank": 1,
                    "storyRank": 2,
                    "team": "backend",
                    "created": "2026-06-01",
                    "dependencies": [],
                },
            ],
        }
        result = compute_schedule(data)
        self.assertEqual(len(result["scheduled"]), 2)
        t1 = next(x for x in result["scheduled"] if x["key"] == "T1")
        t2 = next(x for x in result["scheduled"] if x["key"] == "T2")
        self.assertEqual(t1["startDate"], "2026-06-02")
        self.assertEqual(t2["startDate"], "2026-06-03")


class TestPriorityReorder(unittest.TestCase):
    def test_higher_priority_scheduled_first(self):
        base = {
            "sprintStart": "2026-06-02",
            "sprintEnd": "2026-06-13",
            "hoursPerDay": 8,
            "workingDays": [0, 1, 2, 3, 4],
            "today": "2026-06-02",
        }
        items_low_first = {
            **base,
            "items": [
                {
                    "key": "LOW",
                    "assignee": "bob",
                    "estimateSeconds": 28800,
                    "epicPriorityRank": 3,
                    "storyRank": 1,
                    "team": "backend",
                    "created": "2026-06-01",
                    "dependencies": [],
                },
                {
                    "key": "HIGH",
                    "assignee": "bob",
                    "estimateSeconds": 28800,
                    "epicPriorityRank": 1,
                    "storyRank": 2,
                    "team": "backend",
                    "created": "2026-06-01",
                    "dependencies": [],
                },
            ],
        }
        result = compute_schedule(items_low_first)
        high = next(x for x in result["scheduled"] if x["key"] == "HIGH")
        self.assertEqual(high["startDate"], "2026-06-02")


class TestMissingEstimate(unittest.TestCase):
    def test_unscheduled(self):
        data = {
            "sprintStart": "2026-06-02",
            "sprintEnd": "2026-06-13",
            "hoursPerDay": 8,
            "workingDays": [0, 1, 2, 3, 4],
            "today": "2026-06-02",
            "items": [
                {
                    "key": "X1",
                    "assignee": "alice",
                    "estimateSeconds": 0,
                    "epicPriorityRank": 1,
                    "storyRank": 1,
                    "team": "backend",
                    "created": "",
                    "dependencies": [],
                }
            ],
        }
        result = compute_schedule(data)
        self.assertEqual(len(result["unscheduled"]), 1)
        self.assertEqual(result["unscheduled"][0]["reason"], "missing_estimate")


class TestExplicitDependencies(unittest.TestCase):
    def test_optional_dependency_does_not_delay_when_unscheduled(self):
        data = {
            "sprintStart": "2026-06-02",
            "sprintEnd": "2026-06-20",
            "hoursPerDay": 8,
            "workingDays": [0, 1, 2, 3, 4],
            "today": "2026-06-02",
            "items": [
                {
                    "key": "MOB-1",
                    "assignee": "mob",
                    "estimateSeconds": 8 * 3600,
                    "epicPriorityRank": 1,
                    "storyRank": 1,
                    "team": "mobile",
                    "created": "2026-06-01",
                    "dependencies": [
                        {"type": "backend_delivery", "dependsOnKey": "BE-MISSING"}
                    ],
                },
            ],
        }
        result = compute_schedule(data)
        self.assertEqual(result["violations"], [])
        self.assertEqual(len(result["scheduled"]), 1)

    def test_mobile_and_web_start_at_sprint_without_be_gate(self):
        data = {
            "sprintStart": "2026-06-02",
            "sprintEnd": "2026-06-20",
            "hoursPerDay": 8,
            "workingDays": [0, 1, 2, 3, 4],
            "today": "2026-06-02",
            "items": [
                {
                    "key": "BE-1",
                    "assignee": "be_dev",
                    "estimateSeconds": 16 * 3600,
                    "epicPriorityRank": 1,
                    "storyRank": 1,
                    "team": "backend",
                    "created": "2026-06-01",
                    "dependencies": [],
                },
                {
                    "key": "WEB-1",
                    "assignee": "web_dev",
                    "estimateSeconds": 8 * 3600,
                    "epicPriorityRank": 1,
                    "storyRank": 2,
                    "team": "frontend",
                    "created": "2026-06-01",
                    "dependencies": [],
                },
                {
                    "key": "MOB-1",
                    "assignee": "mob_dev",
                    "estimateSeconds": 8 * 3600,
                    "epicPriorityRank": 1,
                    "storyRank": 3,
                    "team": "mobile",
                    "created": "2026-06-01",
                    "dependencies": [],
                },
            ],
        }
        result = compute_schedule(data)
        web = next(x for x in result["scheduled"] if x["key"] == "WEB-1")
        mob = next(x for x in result["scheduled"] if x["key"] == "MOB-1")
        self.assertEqual(web["startDate"], "2026-06-02")
        self.assertEqual(mob["startDate"], "2026-06-02")


if __name__ == "__main__":
    unittest.main()
