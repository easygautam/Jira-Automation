"""Tests for jira_normalize estimate helpers."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from sprintkit.jira_model import (  # noqa: E402
    bug_missing_logged_time,
    build_index,
    count_unscheduled_breakdown,
    effective_estimate_seconds,
    is_bug_active_status,
    lookup_status_phase,
    normalize_status_name,
    resolve_epic_key,
    time_spent_seconds,
)


def _bug(key: str, oe: int = 0, spent: int = 0, status: str = "To Do") -> dict:
    return {
        "key": key,
        "fields": {
            "issuetype": {"name": "Bug"},
            "timeoriginalestimate": oe,
            "timespent": spent,
            "status": {"name": status},
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


def _epic(key: str) -> dict:
    return {
        "key": key,
        "fields": {
            "summary": "Epic",
            "issuetype": {"name": "Epic", "hierarchyLevel": 1},
        },
    }


CONFIG = {
    "fields": {
        "originalEstimate": "timeoriginalestimate",
        "timeSpent": "timespent",
    },
    "dataQuality": {
        "bugActiveStatuses": ["To Do", "In Progress", "Hold", "Deferred"],
    },
    "statusPhaseMap": {
        "To Do": "PRD Tech Discussion",
        "TO  DO": "PRD Tech Discussion",
        "In Progress": "Development",
        "Ready For QA": "QA Testing",
    },
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


class TestBugStatusHelpers(unittest.TestCase):
    def test_normalize_status_name(self):
        self.assertEqual(normalize_status_name("TO  DO"), "to do")
        self.assertEqual(normalize_status_name("In  Progress"), "in progress")

    def test_is_bug_active_status_variants(self):
        self.assertTrue(is_bug_active_status(_bug("VP-8", status="TO  DO"), CONFIG))
        self.assertTrue(is_bug_active_status(_bug("VP-9", status="In  Progress"), CONFIG))
        self.assertTrue(is_bug_active_status(_bug("VP-10", status="Deferred"), CONFIG))
        self.assertFalse(is_bug_active_status(_bug("VP-11", status="Ready For QA"), CONFIG))

    def test_bug_missing_logged_time(self):
        self.assertFalse(bug_missing_logged_time(_bug("VP-12", status="TO  DO"), CONFIG))
        self.assertTrue(
            bug_missing_logged_time(_bug("VP-13", status="Closed", spent=0), CONFIG)
        )
        self.assertFalse(
            bug_missing_logged_time(_bug("VP-14", status="Closed", spent=3600), CONFIG)
        )
        self.assertFalse(
            bug_missing_logged_time(_bug("VP-15", status="Not a Bug", spent=0), CONFIG)
        )


class TestStatusPhaseLookup(unittest.TestCase):
    def test_lookup_status_phase_exact(self):
        self.assertEqual(
            lookup_status_phase("In Progress", CONFIG),
            "Development",
        )

    def test_lookup_status_phase_normalized(self):
        self.assertEqual(
            lookup_status_phase("TO  DO", CONFIG),
            "PRD Tech Discussion",
        )
        self.assertEqual(
            lookup_status_phase("Ready For QA", CONFIG),
            "QA Testing",
        )

    def test_count_unscheduled_breakdown(self):
        issues = {
            "VP-A": _bug("VP-A", status="TO  DO"),
            "VP-B": _task("VP-B"),
            "VP-C": _bug("VP-C", status="Closed", spent=0),
        }
        unscheduled = [{"key": "VP-A"}, {"key": "VP-B"}, {"key": "VP-C"}]
        active, tasks, other = count_unscheduled_breakdown(unscheduled, issues, CONFIG)
        self.assertEqual(active, 1)
        self.assertEqual(tasks, 1)
        self.assertEqual(other, 1)


class TestResolveEpicKey(unittest.TestCase):
    def test_walks_story_to_epic(self):
        epic = _epic("E1")
        story = {
            "key": "S1",
            "fields": {
                "issuetype": {"name": "Story"},
                "parent": {"key": "E1"},
            },
        }
        task = {
            "key": "T1",
            "fields": {
                "issuetype": {"name": "Task"},
                "parent": {"key": "S1"},
            },
        }
        index = build_index([epic, story, task])
        self.assertEqual(resolve_epic_key(task, index), "E1")
        self.assertEqual(resolve_epic_key(epic, index), "E1")


if __name__ == "__main__":
    unittest.main()
