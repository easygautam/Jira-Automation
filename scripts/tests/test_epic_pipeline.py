"""Tests for epic estimation pipeline."""

from __future__ import annotations

import json
import sys
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from sprintkit.epic_pipeline import result_to_json, run_epic_estimation  # noqa: E402
from sprintkit.jira_model import jira_start_date  # noqa: E402


def _epic(key: str, summary: str = "Test PRD") -> dict:
    return {
        "key": key,
        "fields": {
            "summary": summary,
            "issuetype": {"name": "Epic", "hierarchyLevel": 1},
        },
    }


def _task(
    key: str,
    summary: str,
    parent: str,
    hours: float = 6,
    start: str | None = None,
) -> dict:
    fields: dict = {
        "summary": summary,
        "timeoriginalestimate": int(hours * 3600),
        "issuetype": {"name": "Task"},
        "assignee": {"displayName": "Alice", "accountId": "alice"},
        "parent": {"key": parent, "fields": {"issuetype": {"name": "Epic"}}},
    }
    if start:
        fields["customfield_10015"] = start
    return {"key": key, "fields": fields}


MINIMAL_CONFIG = {
    "fields": {"startDate": "customfield_10015"},
    "scheduling": {"workingDayInts": [0, 1, 2, 3, 4]},
    "teams": {
        "backend": ["backend", "be"],
        "frontend": ["frontend", "web"],
        "mobile": ["mobile", "app"],
        "qa": ["qa"],
    },
    "teamPrefixMapping": {
        "backend": {"aliases": ["be", "backend"]},
        "frontend": {"aliases": ["web", "frontend"]},
        "mobile": {"aliases": ["app", "mobile"]},
        "qa": {"aliases": ["qa"]},
    },
    "timeline": {
        "hoursPerDay": 6,
        "effortBuffers": {
            "bugFixesPercentOfDevelopment": 0.10,
            "stageFinalTestingPercentOfStageTesting": 0.10,
        },
        "leaveTaskPrefixes": {
            "generic": "Leave |",
            "planned": "Leave | Planned",
            "unplanned": "Leave | Unplanned",
        },
    },
}


class TestEpicPipeline(unittest.TestCase):
    def test_run_epic_estimation(self):
        epic = _epic("VP-900", "Payments PRD")
        assess = _task("VP-901", "BE | Assessment | Design", "VP-900", 6, "2026-06-02")
        dev = _task("VP-902", "BE || Implement API", "VP-900", 12, "2026-06-04")
        issues = [epic, assess, dev]
        result = run_epic_estimation(
            issues, MINIMAL_CONFIG, "VP-900", jira_site_url="https://example.atlassian.net"
        )
        self.assertEqual(result.epic_key, "VP-900")
        self.assertEqual(result.delivery_start, "2026-06-02")
        self.assertIn("Teams plan", result.markdown)
        self.assertIn("Start", result.markdown)
        self.assertIn("VP-900", result.canvas_data["epicKey"])
        payload = result_to_json(result)
        self.assertEqual(payload["epicKey"], "VP-900")
        self.assertIn("timeline", payload)
        self.assertIn("canvas", payload)

    def test_jira_start_date(self):
        issue = _task("VP-1", "BE || x", "E1", start="2026-06-15")
        parsed = jira_start_date(issue, MINIMAL_CONFIG)
        self.assertEqual(parsed.isoformat(), "2026-06-15")

    def test_cli_stdout_json(self):
        epic = _epic("VP-800")
        task = _task("VP-801", "BE || work", "VP-800", 6, "2026-06-01")
        fixture = ROOT / "scripts" / "tests" / "fixtures" / "epic_cli_issues.json"
        fixture.parent.mkdir(parents=True, exist_ok=True)
        fixture.write_text(json.dumps([epic, task]), encoding="utf-8")

        from epic_estimation import main  # noqa: E402

        argv = [
            "epic_estimation.py",
            "--epic",
            "VP-800",
            "--issues",
            str(fixture),
            "--config",
            str(ROOT / ".cursor/config/em-config.yaml"),
            "--jira-site-url",
            "https://example.atlassian.net",
        ]
        buf = StringIO()
        with patch.object(sys, "argv", argv), patch.object(sys.stdout, "write", buf.write):
            try:
                main()
            except SystemExit:
                pass
        # main writes via json.dump to stdout - patch may not capture; run subprocess style
        import subprocess

        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/epic_estimation.py"),
                "--epic",
                "VP-800",
                "--issues",
                str(fixture),
                "--project",
                "VP",
                "--jira-site-url",
                "https://example.atlassian.net",
            ],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertEqual(data["epicKey"], "VP-800")
        self.assertNotIn("output", proc.stdout.lower() or "")


if __name__ == "__main__":
    unittest.main()
