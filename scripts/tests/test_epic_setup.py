"""Tests for epic delivery-stage setup planning."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from sprintkit.config import default_config, load_epic_setup_config  # noqa: E402
from sprintkit.epic_setup import (  # noqa: E402
    build_setup_plan,
    scan_existing_stages,
    stage_summary,
)
from epic_setup import run_epic_setup_cli  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CONFIG = default_config()


def _load(name: str) -> list[dict]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class TestStageSummary(unittest.TestCase):
    def test_backend_assessment(self):
        self.assertEqual(
            stage_summary("backend", "Tech Solutioning", "Push Notifications"),
            "BE | Assessment | Push Notifications",
        )

    def test_mobile_uat(self):
        self.assertEqual(
            stage_summary("mobile", "UAT", "Push Notifications"),
            "APP | UAT | Push Notifications — product sign-off",
        )


class TestEpicSetupPlan(unittest.TestCase):
    def test_empty_epic_creates_twelve_tasks(self):
        issues = _load("epic_setup_empty.json")
        plan = build_setup_plan(
            "PPL-1546",
            issues,
            ["backend", "mobile"],
            dev_placeholders=True,
            config=CONFIG,
        )
        self.assertEqual(len(plan["toCreate"]), 12)
        self.assertEqual(len(plan["skipped"]), 0)
        summaries = {row["summary"] for row in plan["toCreate"]}
        self.assertIn("BE | Assessment | Push Notifications", summaries)
        self.assertIn("APP | UAT | Push Notifications — product sign-off", summaries)

    def test_full_epic_skips_all_stages(self):
        issues = _load("epic_setup_full.json")
        plan = build_setup_plan(
            "PPL-1546",
            issues,
            ["backend", "mobile"],
            dev_placeholders=True,
            config=CONFIG,
        )
        self.assertEqual(len(plan["toCreate"]), 0)
        self.assertEqual(len(plan["skipped"]), 12)
        covered = scan_existing_stages(issues, CONFIG)
        self.assertIn(("backend", "Tech Solutioning"), covered)
        self.assertIn(("mobile", "UAT"), covered)

    def test_partial_epic_only_missing_stages(self):
        issues = _load("epic_setup_empty.json")
        issues.append(
            {
                "key": "PPL-1547",
                "fields": {
                    "summary": "BE | Assessment | Push Notifications",
                    "issuetype": {"name": "Task"},
                    "parent": {"key": "PPL-1546"},
                },
            }
        )
        plan = build_setup_plan(
            "PPL-1546",
            issues,
            ["backend", "mobile"],
            dev_placeholders=True,
            config=CONFIG,
        )
        self.assertEqual(len(plan["toCreate"]), 11)
        self.assertEqual(len(plan["skipped"]), 1)
        self.assertEqual(plan["skipped"][0]["issueKey"], "PPL-1547")

    def test_no_dev_placeholders_omits_development(self):
        issues = _load("epic_setup_empty.json")
        plan = build_setup_plan(
            "PPL-1546",
            issues,
            ["backend", "mobile"],
            dev_placeholders=False,
            config=CONFIG,
        )
        stages = {(r["platform"], r["stage"]) for r in plan["toCreate"]}
        self.assertNotIn(("backend", "Development"), stages)
        self.assertNotIn(("mobile", "Development"), stages)
        self.assertEqual(len(plan["toCreate"]), 10)

    def test_backend_only_platform(self):
        issues = _load("epic_setup_empty.json")
        plan = build_setup_plan(
            "PPL-1546",
            issues,
            ["backend"],
            dev_placeholders=True,
            config=CONFIG,
        )
        self.assertEqual(len(plan["toCreate"]), 6)
        self.assertTrue(
            all(row["platform"] == "backend" for row in plan["toCreate"])
        )

    def test_create_payload_includes_ppl_defaults(self):
        issues = _load("epic_setup_empty.json")
        setup_cfg = load_epic_setup_config(CONFIG)
        setup_cfg["projectDefaults"] = {
            "PPL": {
                "teamsByRole": {
                    "backend": {"id": "10193"},
                    "qa": {"id": "10265"},
                },
                "projectElement": {"id": "10423"},
                "fixVersion": {"id": "22390"},
            }
        }
        merged = {**CONFIG, "epicSetup": setup_cfg}
        plan = build_setup_plan(
            "PPL-1546",
            issues,
            ["backend"],
            dev_placeholders=True,
            config=merged,
        )
        payload = plan["toCreate"][0]["createPayload"]
        self.assertEqual(payload["projectKey"], "PPL")
        self.assertEqual(payload["parent"], "PPL-1546")
        af = payload["additional_fields"]
        self.assertEqual(af["customfield_10014"], "PPL-1546")
        self.assertEqual(af["customfield_10218"], {"id": "10193"})


class TestEpicSetupCli(unittest.TestCase):
    def test_cli_json_empty_epic(self):
        path = FIXTURES / "epic_setup_empty.json"
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            code = run_epic_setup_cli(
                [
                    "--epic",
                    "PPL-1546",
                    "--issues",
                    str(path),
                    "--json",
                ]
            )
        self.assertEqual(code, 0)
        data = json.loads(buf.getvalue())
        self.assertEqual(len(data["toCreate"]), 12)


if __name__ == "__main__":
    unittest.main()
