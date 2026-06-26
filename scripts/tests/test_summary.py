"""Tests for deterministic chat summaries."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from sprintkit.config import load_config  # noqa: E402
from sprintkit.epic_pipeline import run_epic_estimation  # noqa: E402
from sprintkit.pipeline import run_pipeline  # noqa: E402
from sprintkit.render.summary import epic_estimation_summary, sprint_report_summary  # noqa: E402

MINI_FIXTURE = ROOT / "scripts/tests/fixtures/mini_issues.json"
EPIC_FIXTURE = ROOT / "scripts/tests/fixtures/epic_cli_issues.json"
CONFIG_PATH = ROOT / ".cursor/config/em-config.yaml"


class TestSummary(unittest.TestCase):
    def test_sprint_report_summary(self):
        issues = json.loads(MINI_FIXTURE.read_text(encoding="utf-8"))
        config = load_config(CONFIG_PATH)
        result = run_pipeline(
            issues,
            config,
            project="VP",
            today="2026-06-05",
            jira_site_url="https://example.atlassian.net",
        )
        text = sprint_report_summary(result, "/tmp/sprint.md", jira_site_url="https://example.atlassian.net")
        self.assertIn("on_track:", text)
        self.assertIn("/tmp/sprint.md", text)

    def test_epic_estimation_summary(self):
        issues = json.loads(EPIC_FIXTURE.read_text(encoding="utf-8"))
        config = load_config(CONFIG_PATH)
        result = run_epic_estimation(
            issues,
            config,
            "VP-800",
            jira_site_url="https://example.atlassian.net",
        )
        text = epic_estimation_summary(result, canvas_path="/tmp/epic.canvas.tsx")
        self.assertIn("VP-800", text)
        self.assertIn("/tmp/epic.canvas.tsx", text)


if __name__ == "__main__":
    unittest.main()
