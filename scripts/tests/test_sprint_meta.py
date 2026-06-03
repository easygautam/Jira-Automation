"""Tests for sprint_meta.py"""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from sprint_meta import extract_active_sprint  # noqa: E402


class TestSprintMeta(unittest.TestCase):
    def test_picks_active_sprint(self):
        issues = json.loads(
            (ROOT / "scripts/fixtures/sample_issues_with_sprint.json").read_text()
        )
        meta = extract_active_sprint(issues, "customfield_10020")
        self.assertEqual(meta["sprintName"], "VP Sprint 11")
        self.assertEqual(meta["sprintStart"], "2026-05-26")
        self.assertEqual(meta["sprintEnd"], "2026-06-09")
        self.assertEqual(meta["state"], "active")

    def test_missing_sprint_raises(self):
        issues = [{"key": "X", "fields": {"summary": "no sprint"}}]
        with self.assertRaises(ValueError):
            extract_active_sprint(issues, "customfield_10020")


if __name__ == "__main__":
    unittest.main()
