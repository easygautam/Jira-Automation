"""Tests for schedule_delta.py."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from schedule_delta import compute_schedule_delta, delta_has_changes  # noqa: E402


class TestScheduleDelta(unittest.TestCase):
    def test_newly_scheduled(self):
        prior = {"scheduled": [], "unscheduled": [{"key": "VP-1", "reason": "missing_estimate"}]}
        current = {
            "scheduled": [
                {
                    "key": "VP-1",
                    "startDate": "2026-06-03",
                    "dueDate": "2026-06-04",
                    "status": "on_track",
                }
            ],
            "unscheduled": [],
        }
        delta = compute_schedule_delta(prior, current)
        self.assertEqual(len(delta["newly_scheduled"]), 1)
        self.assertEqual(delta["newly_scheduled"][0]["key"], "VP-1")
        self.assertTrue(delta_has_changes(delta))

    def test_date_change(self):
        prior = {
            "scheduled": [
                {
                    "key": "VP-2",
                    "startDate": "2026-06-01",
                    "dueDate": "2026-06-02",
                    "status": "on_track",
                }
            ],
            "unscheduled": [],
        }
        current = {
            "scheduled": [
                {
                    "key": "VP-2",
                    "startDate": "2026-06-03",
                    "dueDate": "2026-06-05",
                    "status": "delayed",
                }
            ],
            "unscheduled": [],
        }
        delta = compute_schedule_delta(prior, current)
        self.assertEqual(len(delta["date_changes"]), 1)
        self.assertEqual(len(delta["status_changes"]), 1)

    def test_newly_unscheduled(self):
        prior = {
            "scheduled": [
                {
                    "key": "VP-3",
                    "startDate": "2026-06-01",
                    "dueDate": "2026-06-01",
                    "status": "on_track",
                }
            ],
            "unscheduled": [],
        }
        current = {
            "scheduled": [],
            "unscheduled": [{"key": "VP-3", "reason": "missing_estimate"}],
        }
        delta = compute_schedule_delta(prior, current)
        self.assertEqual(len(delta["newly_unscheduled"]), 1)

    def test_no_changes(self):
        schedule = {
            "scheduled": [
                {
                    "key": "VP-4",
                    "startDate": "2026-06-01",
                    "dueDate": "2026-06-02",
                    "status": "on_track",
                }
            ],
            "unscheduled": [],
        }
        delta = compute_schedule_delta(schedule, schedule)
        self.assertFalse(delta_has_changes(delta))


if __name__ == "__main__":
    unittest.main()
