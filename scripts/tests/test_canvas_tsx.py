"""Tests for epic canvas .tsx generation."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from sprintkit.config import load_config  # noqa: E402
from sprintkit.epic_pipeline import run_epic_estimation  # noqa: E402
from sprintkit.render.canvas_tsx import render_epic_canvas_tsx, write_epic_canvas  # noqa: E402

FIXTURE = ROOT / "scripts/tests/fixtures/epic_cli_issues.json"
CONFIG_PATH = ROOT / ".cursor/config/em-config.yaml"


class TestCanvasTsx(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        issues = json.loads(FIXTURE.read_text(encoding="utf-8"))
        config = load_config(CONFIG_PATH)
        cls.result = run_epic_estimation(
            issues,
            config,
            "VP-800",
            jira_site_url="https://example.atlassian.net",
        )

    def test_render_contains_epic_key_and_export(self):
        text = render_epic_canvas_tsx(self.result.canvas_data)
        self.assertIn("VP-800", text)
        self.assertIn("export default function EpicEstimationCanvas", text)
        self.assertNotIn("fetch(", text)
        self.assertNotIn("__EPIC_DATA_PLACEHOLDER__", text)

    def test_write_epic_canvas(self):
        path = Path("/tmp/test-epic-canvas-VP-800.canvas.tsx")
        write_epic_canvas(self.result.canvas_data, path)
        self.assertTrue(path.is_file())
        content = path.read_text(encoding="utf-8")
        self.assertIn("VP-800", content)
        path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
