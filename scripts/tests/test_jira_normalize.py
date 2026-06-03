"""Tests for jira_normalize estimate helpers."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from jira_normalize import (  # noqa: E402
    effective_estimate_seconds,
    has_actionable_bug_effort,
    time_spent_seconds,
)


def _bug(key: str, oe: int = 0, spent: int = 0) -> dict:
    return {
        "key": key,
        "fields": {
            "issuetype": {"name": "Bug"},
            "timeoriginalestimate": oe,
            "timespent": spent,
        },
    }


def _task(key: str, oe: int = 0, spent: int = 0) -> dict:
    return {
        "key": key,
        "fields": {
            "issuetype": {"name": "Task"},
            "timeoriginalestimate": oe,
            "timespent": spent,
        },
    }


CONFIG = {
    "fields": {
        "originalEstimate": "timeoriginalestimate",
        "timeSpent": "timespent",
    }
}


class TestEffectiveEstimate(unittest.TestCase):
    def test_bug_uses_timespent_when_oe_empty(self):
        issue = _bug("VP-1", oe=0, spent=3600)
        self.assertEqual(effective_estimate_seconds(issue, CONFIG), 3600)

    def test_bug_prefers_timespent_over_oe(self):
        issue = _bug("VP-2", oe=7200, spent=3600)
        self.assertEqual(effective_estimate_seconds(issue, CONFIG), 3600)

    def test_bug_falls_back_to_oe(self):
        issue = _bug("VP-3", oe=7200, spent=0)
        self.assertEqual(effective_estimate_seconds(issue, CONFIG), 7200)

    def test_task_ignores_timespent(self):
        issue = _task("VP-4", oe=0, spent=3600)
        self.assertEqual(effective_estimate_seconds(issue, CONFIG), 0)
        self.assertEqual(time_spent_seconds(issue, CONFIG), 3600)

    def test_has_actionable_bug_effort(self):
        self.assertTrue(has_actionable_bug_effort(_bug("VP-5", spent=1), CONFIG))
        self.assertFalse(has_actionable_bug_effort(_bug("VP-6"), CONFIG))
        self.assertFalse(has_actionable_bug_effort(_task("VP-7", spent=3600), CONFIG))


if __name__ == "__main__":
    unittest.main()
