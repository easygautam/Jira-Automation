"""Tests for config loading, side-display defaults, and PyYAML-independent team bucketing."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from sprintkit import config as config_module  # noqa: E402
from sprintkit.config import (  # noqa: E402
    DEFAULT_SIDE_DISPLAY,
    default_config,
    load_config,
    project_key_from_issue_key,
    pyyaml_available,
    resolve_project_key,
    resolve_side_display_map,
)
from sprintkit.stages import STAGE_DEVELOPMENT  # noqa: E402
from sprintkit.timeline import (  # noqa: E402
    build_timeline_breakdown,
    member_side_for_classification,
    side_display,
)


def _issue(
    key: str,
    summary: str,
    estimate: int,
    *,
    parent_key: str = "VP-100",
    assignee: str = "Dev",
) -> dict:
    return {
        "key": key,
        "fields": {
            "summary": summary,
            "issuetype": {"name": "Task"},
            "status": {"name": "In Progress"},
            "timeoriginalestimate": estimate,
            "assignee": {"displayName": assignee, "accountId": f"acc-{key}"},
            "parent": {
                "key": parent_key,
                "fields": {"issuetype": {"name": "Epic"}, "summary": "Epic"},
            },
        },
    }


def _epic(key: str) -> dict:
    return {
        "key": key,
        "fields": {
            "summary": "Epic",
            "issuetype": {"name": "Epic", "hierarchyLevel": 1},
            "priority": {"name": "High"},
            "status": {"name": "In Progress"},
        },
    }


class TestProjectKeyResolution(unittest.TestCase):
    def test_project_key_from_issue_key(self):
        self.assertEqual(project_key_from_issue_key("VP-12345"), "VP")
        self.assertEqual(project_key_from_issue_key("foot-99"), "FOOT")
        self.assertIsNone(project_key_from_issue_key("INVALID"))
        self.assertIsNone(project_key_from_issue_key(""))

    def test_resolve_cli_overrides_config(self):
        cfg = {"jira": {"projectKey": "VP"}}
        self.assertEqual(resolve_project_key(cli="FOOT", config=cfg), "FOOT")

    def test_resolve_from_epic_key(self):
        self.assertEqual(
            resolve_project_key(epic_key="ABC-12345", config={}),
            "ABC",
        )

    def test_resolve_from_config(self):
        cfg = {"jira": {"projectKey": "VP"}}
        self.assertEqual(resolve_project_key(config=cfg), "VP")

    def test_resolve_raises_when_missing(self):
        with self.assertRaises(ValueError):
            resolve_project_key(config={})


class TestSideDisplay(unittest.TestCase):
    def test_known_teams_never_other_with_empty_map(self):
        self.assertEqual(side_display("backend", {}), "Backend")
        self.assertEqual(side_display("qa", {}), "QA")
        self.assertEqual(side_display("frontend", {}), "Web")
        self.assertEqual(side_display("mobile", {}), "Mobile")
        self.assertEqual(side_display("product_design", {}), "Product + Design")

    def test_other_team_maps_to_other(self):
        self.assertEqual(side_display("other", {}), "Other")

    def test_resolve_side_display_merges_config(self):
        cfg = {"timeline": {"sideDisplay": {"backend": "BE Team"}}}
        merged = resolve_side_display_map(cfg)
        self.assertEqual(merged["backend"], "BE Team")
        self.assertEqual(merged["qa"], DEFAULT_SIDE_DISPLAY["qa"])


class TestDefaultConfig(unittest.TestCase):
    def test_default_config_has_timeline_side_display(self):
        cfg = default_config()
        self.assertEqual(cfg["timeline"]["sideDisplay"]["backend"], "Backend")
        self.assertIn("executionStages", cfg["timeline"])
        self.assertIn("teamPrefixMapping", cfg)

    def test_load_config_without_pyyaml_uses_defaults(self):
        config_module._pyyaml_warning_emitted = False
        with mock.patch.object(config_module, "yaml", None):
            cfg = load_config(ROOT / ".cursor/config/em-config.yaml")
        self.assertEqual(cfg["timeline"]["sideDisplay"]["backend"], "Backend")
        self.assertEqual(cfg["timeline"]["hoursPerDay"], 6)

    @unittest.skipUnless(pyyaml_available(), "PyYAML not installed")
    def test_load_real_em_config_has_timeline(self):
        cfg = load_config(ROOT / ".cursor/config/em-config.yaml")
        self.assertEqual(cfg["timeline"]["sideDisplay"]["backend"], "Backend")
        self.assertTrue(cfg.get("jira", {}).get("projectKey"))


class TestMemberSideClassification(unittest.TestCase):
    def test_additional_effort_qa_side(self):
        side = member_side_for_classification(
            {"kind": "additional_effort", "team": "qa"},
            {"qa": "QA", "other": "Other"},
        )
        self.assertEqual(side, "QA")

    def test_unmapped_always_other(self):
        side_map = resolve_side_display_map({})
        result = member_side_for_classification(
            {"kind": "unmapped", "team": "qa"},
            side_map,
        )
        self.assertEqual(result, "Other")

    def test_work_backend_not_other(self):
        side_map = resolve_side_display_map({})
        result = member_side_for_classification(
            {
                "kind": "work",
                "platform": "backend",
                "stage": STAGE_DEVELOPMENT,
                "team": "backend",
            },
            side_map,
        )
        self.assertEqual(result, "Backend")


class TestTimelineWithoutPyYaml(unittest.TestCase):
    def test_be_tasks_bucket_backend_not_other(self):
        config_module._pyyaml_warning_emitted = False
        with mock.patch.object(config_module, "yaml", None):
            cfg = load_config(ROOT / ".cursor/config/em-config.yaml")
        epic = _epic("VP-100")
        task = _issue("VP-101", "BE || API work", 7200, parent_key="VP-100", assignee="Alice")
        result = build_timeline_breakdown(
            [epic, task],
            {"scheduled": [{"key": "VP-101"}]},
            cfg,
        )[0]
        self.assertIn("Backend", result["membersBySide"])
        self.assertNotIn(
            "Alice",
            [m["member"] for m in result["membersBySide"].get("Other", [])],
        )

    def test_qa_platform_tasks_bucket_qa_not_other(self):
        config_module._pyyaml_warning_emitted = False
        with mock.patch.object(config_module, "yaml", None):
            cfg = load_config(ROOT / ".cursor/config/em-config.yaml")
        epic = _epic("VP-200")
        task = _issue(
            "VP-201",
            "QA | BE | API validation",
            3600,
            parent_key="VP-200",
            assignee="Carol",
        )
        result = build_timeline_breakdown([epic, task], {"scheduled": []}, cfg)[0]
        self.assertIn("QA", result["membersBySide"])
        self.assertIn(
            "Carol",
            [m["member"] for m in result["membersBySide"]["QA"]],
        )

    def test_qa_without_platform_additional_effort_not_in_member_breakdown(self):
        config_module._pyyaml_warning_emitted = False
        with mock.patch.object(config_module, "yaml", None):
            cfg = load_config(ROOT / ".cursor/config/em-config.yaml")
        epic = _epic("VP-300")
        task = _issue("VP-301", "QA | Assessment", 3600, parent_key="VP-300", assignee="Pat")
        result = build_timeline_breakdown([epic, task], {"scheduled": []}, cfg)[0]
        self.assertEqual(len(result["unmapped"]), 1)
        self.assertTrue(result["unmapped"][0].get("additionalEffort"))
        self.assertEqual(result["unmapped"][0]["team"], "QA")
        self.assertNotIn("Other", result["membersBySide"])
        self.assertNotIn("QA", result["membersBySide"])


if __name__ == "__main__":
    unittest.main()
