"""Tests for pipe-prefix team detection."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from jira_teams import TEAM_OTHER, team_from_first_prefix, team_from_issue  # noqa: E402
from timeline_breakdown import classify_issue  # noqa: E402


def _issue(summary: str, issuetype: str = "Task") -> dict:
    return {
        "key": "VP-1",
        "fields": {
            "summary": summary,
            "issuetype": {"name": issuetype},
            "labels": [],
            "components": [],
        },
    }


CONFIG = {
    "teams": {"qa": ["qa"], "mobile": ["mobile", "app"]},
    "teamPrefixMapping": {
        "qa": {"aliases": ["qa"]},
        "backend": {"aliases": ["be", "backend", "api", "dag", "ppadmin", "admin"]},
        "frontend": {"aliases": ["web", "website", "frontend", "frontent", "fe"]},
        "mobile": {"aliases": ["mobile", "app", "android", "ios"]},
    },
    "timeline": {
        "leaveTaskPrefixes": {"planned": "Leave | Planned", "unplanned": "Leave | Unplanned"},
        "defaultTaskByTeam": {
            "backend": "BE development",
            "frontend": "Web development",
            "mobile": "Mobile development",
        },
        "mappingRules": [
            {"keywords": ["android", "app |"], "task": "Mobile development"},
            {"keywords": ["qa |"], "task": "QA Test cases & planning"},
        ],
    },
}


class TestPipePrefix(unittest.TestCase):
    def test_qa_before_app(self):
        self.assertEqual(
            team_from_first_prefix("QA | APP | EVENTS PRD — 2nd iteration"),
            "qa",
        )
        issue = _issue("QA | APP | EVENTS PRD — 2nd iteration (registration funnel)")
        self.assertEqual(team_from_issue(issue, CONFIG["teams"], CONFIG), "qa")

    def test_be_first(self):
        self.assertEqual(team_from_first_prefix("BE || Add endpoint"), "backend")

    def test_app_first(self):
        self.assertEqual(team_from_first_prefix("APP | Stage | icon"), "mobile")

    def test_android_is_mobile(self):
        self.assertEqual(team_from_first_prefix("Android | Stage | icon"), "mobile")

    def test_ppadmin_is_backend(self):
        self.assertEqual(team_from_first_prefix("PPAdmin || Create operation"), "backend")

    def test_dag_and_api_are_backend(self):
        self.assertEqual(team_from_first_prefix("DAG | flow test"), "backend")
        self.assertEqual(team_from_first_prefix("API | contract review"), "backend")

    def test_website_and_fe_are_web(self):
        self.assertEqual(team_from_first_prefix("Website | landing"), "frontend")
        self.assertEqual(team_from_first_prefix("FE | component"), "frontend")

    def test_unmatched_prefix_is_other(self):
        self.assertIsNone(team_from_first_prefix("Stage | FOMO message"))
        issue = _issue("Stage | Past Time Slots Displayed")
        self.assertEqual(team_from_issue(issue, CONFIG["teams"], CONFIG), TEAM_OTHER)
        self.assertEqual(
            team_from_issue(_issue("Enhancement: Need to check"), CONFIG["teams"], CONFIG),
            TEAM_OTHER,
        )

    def test_mixed_case_prefixes(self):
        cases = [
            ("be | Enhancement: foo", "backend"),
            ("BE | Enhancement: foo", "backend"),
            ("Qa | APP | work", "qa"),
            ("web | UI change", "frontend"),
            ("WEB | UI change", "frontend"),
            ("aNdRoId | Stage", "mobile"),
            ("iOS | build", "mobile"),
            ("PpAdmin | op", "backend"),
            ("Api | endpoint", "backend"),
        ]
        for summary, expected in cases:
            with self.subTest(summary=summary):
                self.assertEqual(
                    team_from_first_prefix(summary),
                    expected,
                    msg=summary,
                )

    def test_be_pipe_enhancement_maps_to_be_development(self):
        issue = _issue(
            "BE | Enhancement: Need to check the center ids and fomo cuttoff value while uploading"
        )
        result = classify_issue(issue, CONFIG["timeline"], CONFIG["teams"], CONFIG)
        self.assertEqual(result["kind"], "work")
        self.assertEqual(result["team"], "backend")
        self.assertEqual(result["task"], "BE development")

    def test_qa_classified_as_qa_work_not_mobile(self):
        issue = _issue(
            "QA | APP | EVENTS PRD — 2nd iteration (registration funnel)",
            "Test Execution",
        )
        result = classify_issue(issue, CONFIG["timeline"], CONFIG["teams"], CONFIG)
        self.assertEqual(result["team"], "qa")
        self.assertIn("QA mobile stage", result["task"])


if __name__ == "__main__":
    unittest.main()
