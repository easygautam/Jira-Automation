"""Tests for epic rollup helpers used by the Delivery items section."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from sprintkit.jira_model import epic_jira_sort_key, epic_summary  # noqa: E402
from sprintkit.render.markdown import (  # noqa: E402
    derive_jira_site_url_from_issues,
    jira_issue_keys_linked,
    jira_issue_link,
    linkify_bare_issue_keys,
    resolve_jira_site_url,
)
from sprintkit.render.sections import compute_epic_rollup, worst_status  # noqa: E402


class TestEpicRollup(unittest.TestCase):
    def test_three_tasks_min_max(self):
        scheduled = [
            {"epicKey": "E1", "startDate": "2026-06-02", "dueDate": "2026-06-03", "status": "on_track"},
            {"epicKey": "E1", "startDate": "2026-06-04", "dueDate": "2026-06-06", "status": "delayed"},
            {"epicKey": "E1", "startDate": "2026-06-01", "dueDate": "2026-06-05", "status": "on_track"},
        ]
        engine_items = [{"key": "T1", "epicKey": "E1"}]
        rollup = compute_epic_rollup("E1", scheduled, [], engine_items)
        self.assertEqual(rollup["start"], "2026-06-01")
        self.assertEqual(rollup["due"], "2026-06-06")
        self.assertEqual(rollup["status"], "delayed")
        self.assertEqual(rollup["scheduled_count"], 3)

    def test_no_scheduled_tbd(self):
        rollup = compute_epic_rollup("E9", [], [{"key": "X"}], [])
        self.assertIsNone(rollup["start"])
        self.assertEqual(rollup["status"], "tbd")

    def test_worst_status_order(self):
        self.assertEqual(worst_status(["on_track", "delayed", "at_risk"]), "delayed")
        self.assertEqual(worst_status([]), "tbd")

    def test_jira_issue_link(self):
        link = jira_issue_link("https://physicswallah001.atlassian.net", "VP-19350")
        self.assertEqual(
            link,
            "[VP-19350](https://physicswallah001.atlassian.net/browse/VP-19350)",
        )
        self.assertEqual(jira_issue_link(None, "VP-1"), "VP-1")

    def test_jira_issue_keys_linked_all_keys(self):
        site = "https://physicswallah001.atlassian.net"
        keys = ["VP-1", "VP-2", "VP-3", "VP-4", "VP-5"]
        linked = jira_issue_keys_linked(site, keys)
        self.assertNotIn("…", linked)
        for k in keys:
            self.assertIn(f"[{k}]({site}/browse/{k})", linked)

    def test_derive_site_url_from_issue_icon(self):
        issues = [
            {
                "key": "VP-1",
                "fields": {
                    "status": {
                        "iconUrl": "https://physicswallah001.atlassian.net/images/icons/inprogress.png"
                    }
                },
            }
        ]
        self.assertEqual(
            derive_jira_site_url_from_issues(issues),
            "https://physicswallah001.atlassian.net",
        )

    def test_resolve_site_url_from_issues_when_config_missing(self):
        issues = [
            {
                "key": "VP-2",
                "fields": {
                    "priority": {
                        "iconUrl": "https://demo.atlassian.net/images/icons/priorities/high.svg"
                    }
                },
            }
        ]
        self.assertEqual(
            resolve_jira_site_url(None, {}, issues),
            "https://demo.atlassian.net",
        )

    def test_linkify_bare_issue_keys(self):
        site = "https://physicswallah001.atlassian.net"
        text = "| VP-99 | Title | and VP-100 done"
        linked = linkify_bare_issue_keys(text, site, project_key="VP")
        self.assertIn(f"[VP-99]({site}/browse/VP-99)", linked)
        self.assertIn(f"[VP-100]({site}/browse/VP-100)", linked)

    def test_linkify_skips_already_linked_keys(self):
        site = "https://physicswallah001.atlassian.net"
        text = f"[VP-1]({site}/browse/VP-1)"
        self.assertEqual(linkify_bare_issue_keys(text, site), text)

    def test_epic_summary_from_parent(self):
        issues = [
            {
                "key": "VP-100",
                "fields": {
                    "parent": {
                        "key": "VP-19350",
                        "fields": {
                            "summary": "Events phase 1 <> PRD",
                            "issuetype": {"name": "Epic"},
                        },
                    }
                },
            }
        ]
        summary = epic_summary("VP-19350", issues, {})
        self.assertEqual(summary, "Events phase 1 <> PRD")

    def test_delivery_epic_sort_jira_rank(self):
        issues = [
            {
                "key": "E1",
                "fields": {
                    "summary": "Prod Issues AMJ26",
                    "issuetype": {"name": "Epic", "hierarchyLevel": 1},
                    "customfield_10019": "0|i00003:",
                },
            },
            {
                "key": "E2",
                "fields": {
                    "summary": "Events phase 1 <> PRD",
                    "issuetype": {"name": "Epic", "hierarchyLevel": 1},
                    "customfield_10019": "0|i00001:",
                },
            },
            {
                "key": "E3",
                "fields": {
                    "summary": "Events Phase 2<>PRD",
                    "issuetype": {"name": "Epic", "hierarchyLevel": 1},
                    "customfield_10019": "0|i00002:",
                },
            },
        ]
        issue_by_key = {i["key"]: i for i in issues}
        scheduled = [
            {"epicKey": "E1", "startDate": "2026-06-04", "dueDate": "2026-06-04", "status": "on_track"},
            {"epicKey": "E2", "startDate": "2026-06-01", "dueDate": "2026-06-12", "status": "delayed"},
            {"epicKey": "E3", "startDate": "2026-06-02", "dueDate": "2026-06-08", "status": "delayed"},
        ]
        config = {"fields": {"rank": "customfield_10019"}}
        order = sorted(
            ["E1", "E2", "E3"],
            key=lambda k: epic_jira_sort_key(k, issue_by_key, config),
        )
        self.assertEqual(order, ["E2", "E3", "E1"])


if __name__ == "__main__":
    unittest.main()
