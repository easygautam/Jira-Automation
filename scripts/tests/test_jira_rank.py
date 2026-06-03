"""Tests for Jira Rank (LexoRank) epic ordering."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from jira_normalize import (  # noqa: E402
    epic_jira_sort_key,
    jira_rank,
    sort_epic_keys,
)


CONFIG = {"fields": {"rank": "customfield_10019"}}


class TestJiraRank(unittest.TestCase):
    def test_jira_rank_reads_config_field(self):
        issue = {"fields": {"customfield_10019": "0|i19dsj:"}}
        self.assertEqual(jira_rank(issue, CONFIG), "0|i19dsj:")

    def test_jira_rank_missing_issue(self):
        self.assertEqual(jira_rank(None, CONFIG), "")

    def test_epic_jira_sort_key_ranked_before_unranked(self):
        index = {
            "E1": {"key": "E1", "fields": {"customfield_10019": "0|i00002:"}},
            "E2": {"key": "E2", "fields": {}},
        }
        self.assertLess(
            epic_jira_sort_key("E1", index, CONFIG),
            epic_jira_sort_key("E2", index, CONFIG),
        )

    def test_sort_epic_keys_lexorank_order(self):
        issues = [
            {"key": "E1", "fields": {"customfield_10019": "0|i00003:"}},
            {"key": "E2", "fields": {"customfield_10019": "0|i00001:"}},
            {"key": "E3", "fields": {"customfield_10019": "0|i00002:"}},
        ]
        index = {i["key"]: i for i in issues}
        order = sort_epic_keys({"E1", "E2", "E3"}, index, CONFIG)
        self.assertEqual(order, ["E2", "E3", "E1"])

    def test_sort_epic_keys_unranked_last(self):
        issues = [
            {"key": "E1", "fields": {"customfield_10019": "0|i00001:"}},
            {"key": "E2", "fields": {}},
        ]
        index = {i["key"]: i for i in issues}
        order = sort_epic_keys({"E2", "E1"}, index, CONFIG)
        self.assertEqual(order, ["E1", "E2"])


if __name__ == "__main__":
    unittest.main()
