"""Tests for Jira issue-type allowlist (fetch + pipeline filter)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from sprintkit.config import (  # noqa: E402
    SCHEDULABLE_TYPES,
    allowed_issue_types,
    jql_allowed_issue_types_clause,
    load_config,
)
from sprintkit.jira_model import (  # noqa: E402
    filter_allowed_issues,
    is_allowed_issue_type,
)
from sprintkit.normalize import normalize  # noqa: E402
from sprintkit.pipeline import run_pipeline  # noqa: E402
from sprintkit.quality import build_data_quality_by_member  # noqa: E402

CONFIG_PATH = ROOT / ".cursor/config/em-config.yaml"
MINI_FIXTURE = ROOT / "scripts/tests/fixtures/mini_issues.json"


def _issue(key: str, issuetype: str) -> dict:
    return {
        "key": key,
        "fields": {
            "summary": f"{key} summary",
            "issuetype": {"name": issuetype},
            "parent": {"key": "VP-900", "fields": {"issuetype": {"name": "Epic"}}},
        },
    }


class TestAllowedIssueTypes(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_config(CONFIG_PATH)

    def test_schedulable_types_exclude_test_execution(self):
        self.assertNotIn("test execution", SCHEDULABLE_TYPES)

    def test_allowed_issue_types_from_config(self):
        allowed = allowed_issue_types(self.config)
        for name in ("epic", "story", "task", "sub-task", "bug"):
            self.assertIn(name, allowed)
        self.assertNotIn("test execution", allowed)

    def test_jql_clause(self):
        clause = jql_allowed_issue_types_clause(self.config)
        self.assertIn("issuetype in (", clause)
        self.assertIn("Epic", clause)
        self.assertIn("Sub-task", clause)
        self.assertIn("Bug", clause)

    def test_is_allowed_issue_type(self):
        self.assertTrue(is_allowed_issue_type(_issue("VP-1", "Task"), self.config))
        self.assertTrue(is_allowed_issue_type(_issue("VP-2", "Bug"), self.config))
        self.assertFalse(
            is_allowed_issue_type(_issue("VP-3", "Test Execution"), self.config)
        )
        self.assertFalse(is_allowed_issue_type(_issue("VP-4", "Test Plan"), self.config))

    def test_filter_allowed_issues(self):
        issues = [
            _issue("VP-1", "Task"),
            _issue("VP-2", "Test Execution"),
            _issue("VP-3", "Epic"),
        ]
        filtered = filter_allowed_issues(issues, self.config)
        keys = {i["key"] for i in filtered}
        self.assertEqual(keys, {"VP-1", "VP-3"})

    def test_pipeline_drops_test_execution_from_normalize_and_dq(self):
        issues = json.loads(MINI_FIXTURE.read_text(encoding="utf-8"))
        self.assertTrue(any(
            i.get("key") == "VP-903"
            and (i.get("fields") or {}).get("issuetype", {}).get("name") == "Test Execution"
            for i in issues
        ))

        result = run_pipeline(
            issues,
            self.config,
            project="VP",
            today="2026-06-05",
            jira_site_url="https://example.atlassian.net",
        )
        engine_keys = {item["key"] for item in result.engine["items"]}
        self.assertNotIn("VP-903", engine_keys)

        quality = build_data_quality_by_member(
            filter_allowed_issues(issues, self.config),
            result.schedule,
            result.timeline,
            None,
            self.config,
        )
        dq_keys = {row["key"] for rows in quality.values() for row in rows}
        self.assertNotIn("VP-903", dq_keys)

    def test_normalize_skips_test_execution_when_not_pre_filtered(self):
        issues = json.loads(MINI_FIXTURE.read_text(encoding="utf-8"))
        engine = normalize(issues, self.config, "2026-06-01", "2026-06-12", "2026-06-05")
        keys = {item["key"] for item in engine["items"]}
        self.assertIn("VP-901", keys)
        self.assertNotIn("VP-903", keys)


if __name__ == "__main__":
    unittest.main()
