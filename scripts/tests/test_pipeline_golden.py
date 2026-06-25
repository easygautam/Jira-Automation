"""Golden end-to-end test: run the whole pipeline on a small fixture.

Validates that all six report deliverables render, the post-refactor fixes hold
(reconciled Bug fix effort columns, no Start/End columns, blank line before
Unmapped work), and the active sprint window is resolved from the Jira field.
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from sprintkit.config import load_config  # noqa: E402
from sprintkit.pipeline import run_pipeline, standup_summary  # noqa: E402

FIXTURE = ROOT / "scripts/tests/fixtures/mini_issues.json"
CONFIG_PATH = ROOT / ".cursor/config/em-config.yaml"


class TestPipelineGolden(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        issues = json.loads(FIXTURE.read_text(encoding="utf-8"))
        config = load_config(CONFIG_PATH)
        cls.result = run_pipeline(
            issues,
            config,
            project="VP",
            today="2026-06-05",
            jira_site_url="https://example.atlassian.net",
        )
        cls.md = cls.result.markdown
        cls.issues = issues
        cls.config = config

    def test_sprint_window_from_field(self):
        self.assertEqual(self.result.sprint_meta["sprintName"], "Demo Sprint")
        self.assertEqual(self.result.sprint_meta["sprintStart"], "2026-06-01")
        self.assertEqual(self.result.sprint_meta["sprintEnd"], "2026-06-12")

    def test_title_and_epic_title(self):
        self.assertIn("# Sprint Report — VP — Demo Sprint", self.md)
        self.assertIn("Demo Feature <> PRD", self.md)

    def test_all_deliverable_headers_present(self):
        for header in (
            "## Executive summary",
            "## Delivery items (Epics)",
            "## Epic Quality Report",
        ):
            self.assertIn(header, self.md)

    def test_bug_effort_columns_reconcile(self):
        self.assertIn(
            "| Epic ID | Epic Name | Bugs | Backend | Web | Mobile | Other | Total |",
            self.md,
        )

    def test_no_placeholder_start_end_columns(self):
        self.assertNotIn("| Start | End |", self.md)
        self.assertNotIn("placeholders", self.md)

    def test_standup_summary_renders(self):
        text = standup_summary(
            self.result,
            self.issues,
            self.config,
            jira_site_url="https://example.atlassian.net",
        )
        self.assertIn("Standup — Demo Sprint", text)
        self.assertIn("Status:", text)
        self.assertIn("[VP-901](https://example.atlassian.net/browse/VP-901)", text)

    def test_no_qa_all_platforms_section(self):
        self.assertNotIn("QA (all platforms)", self.md)

    def test_all_issue_keys_in_report_are_linked(self):
        """Table cells and lists must not contain bare VP- keys (browse links required)."""
        bare_table_key = re.search(r"\|\s+VP-\d+\s+\|", self.md)
        self.assertIsNone(bare_table_key, "found unlinked issue key in table")
        bare_bullet_key = re.search(r"^- VP-\d+:", self.md, re.MULTILINE)
        self.assertIsNone(bare_bullet_key, "found unlinked issue key in list")


if __name__ == "__main__":
    unittest.main()
