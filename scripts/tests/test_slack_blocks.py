"""Tests for Slack Block Kit renderer and client."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from sprintkit.epic_pipeline import run_epic_estimation  # noqa: E402
from sprintkit.render.slack_blocks import (  # noqa: E402
    MAX_BLOCKS_PER_MESSAGE,
    build_slack_blocks,
    build_slack_blocks_fallback,
    delivery_window_caption,
    fmt_display_date,
    platform_delivery_title,
)
from sprintkit.slack_client import (  # noqa: E402
    SlackError,
    post_epic_estimation,
    resolve_bot_token,
    resolve_channel_id,
)


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
    "slack": {
        "channel": "gautam-personal-agent",
        "botTokenEnv": "SLACK_BOT_TOKEN",
    },
}


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


def _sample_canvas() -> dict:
    epic = _epic("VP-900", "Payments PRD")
    assess = _task("VP-901", "BE | Assessment | Design", "VP-900", 6, "2026-06-02")
    dev = _task("VP-902", "BE || Implement API", "VP-900", 12, "2026-06-04")
    result = run_epic_estimation(
        [epic, assess, dev],
        MINIMAL_CONFIG,
        "VP-900",
        jira_site_url="https://example.atlassian.net",
    )
    canvas = dict(result.canvas_data)
    canvas["unmapped"] = [
        {
            "key": "VP-999",
            "summary": "Orphan task",
            "effortsHours": 2,
            "assignee": "Alice",
            "team": "Other",
        }
    ]
    canvas["additionalEfforts"] = [
        {
            "team": "Other",
            "effortHours": 2,
            "details": "Alice (2h) - VP-999",
        }
    ]
    canvas["dataQuality"] = [
        {"member": "Alice", "key": "VP-901", "reason": "Missing estimate on sub-task"}
    ]
    return canvas


class TestSlackBlockFormatting(unittest.TestCase):
    def test_fmt_display_date(self):
        self.assertEqual(fmt_display_date("2026-06-10"), "10 Jun 2026")
        self.assertEqual(fmt_display_date(None), "—")

    def test_delivery_window_caption(self):
        self.assertEqual(
            delivery_window_caption("2026-06-10", "2026-06-25"),
            "16 calendar days in delivery window",
        )
        self.assertIsNone(delivery_window_caption(None, "2026-06-25"))

    def test_platform_delivery_title(self):
        self.assertEqual(platform_delivery_title("Backend"), "Backend Delivery")
        self.assertEqual(platform_delivery_title("Web"), "Web Delivery")
        self.assertEqual(platform_delivery_title("Mobile"), "App Delivery")


class TestSlackBlocks(unittest.TestCase):
    def setUp(self):
        self.canvas = _sample_canvas()

    def test_build_slack_blocks_structure(self):
        message = build_slack_blocks(self.canvas)
        self.assertIn("Epic estimation — VP-900", message["text"])
        blocks = message["blocks"]
        self.assertLessEqual(len(blocks), MAX_BLOCKS_PER_MESSAGE)
        types = [b["type"] for b in blocks]
        self.assertEqual(types[0], "header")
        self.assertIn("table", types)
        self.assertIn("data_visualization", types)

    def test_team_task_pie_block(self):
        from sprintkit.render.slack_blocks import build_team_task_pie_block

        block = build_team_task_pie_block(self.canvas)
        self.assertIsNotNone(block)
        assert block is not None
        self.assertEqual(block["chart"]["type"], "pie")
        segments = block["chart"]["segments"]
        self.assertTrue(all(s["value"] > 0 for s in segments))

    def test_team_effort_bar_block(self):
        from sprintkit.render.slack_blocks import build_team_effort_bar_block

        block = build_team_effort_bar_block(self.canvas)
        self.assertIsNotNone(block)
        assert block is not None
        self.assertEqual(block["chart"]["type"], "bar")
        self.assertIn("axis_config", block["chart"])

    def test_teams_plan_table_headers(self):
        message = build_slack_blocks(self.canvas)
        table = next(b for b in message["blocks"] if b["type"] == "table")
        header_cells = table["rows"][0]
        self.assertEqual(len(header_cells), 5)
        header_text = header_cells[0]["elements"][0]["elements"][0]["text"]
        self.assertEqual(header_text, "Team")

    def test_additional_efforts_and_data_quality_sections(self):
        message = build_slack_blocks(self.canvas)
        headers = [b.get("text", {}).get("text") for b in message["blocks"] if b["type"] == "header"]
        self.assertIn("Additional efforts", headers)
        self.assertIn("Data quality", headers)

    def test_fallback_uses_field_grid(self):
        message = build_slack_blocks_fallback(self.canvas)
        types = [b["type"] for b in message["blocks"]]
        self.assertNotIn("table", types)
        field_text = "\n".join(
            f["text"]
            for b in message["blocks"]
            if b["type"] == "section"
            for f in b.get("fields", [])
        )
        self.assertIn("*Team*", field_text)
        self.assertIn("*Stage*", field_text)
        self.assertNotIn("```", field_text)

    def test_stage_table_row(self):
        from sprintkit.render.slack_blocks import _stage_table_row

        row = _stage_table_row(
            {
                "stage": "Development",
                "synthetic": False,
                "resources": 1.0,
                "effortsHours": 2.0,
                "leaveHours": 0,
                "calculatedDays": 0.33,
                "start": "2026-06-22",
                "end": "2026-06-22",
            }
        )
        self.assertEqual(row[0], "Development")
        self.assertIn("Jun 2026", row[5])


class TestSlackClient(unittest.TestCase):
    @patch("sprintkit.slack_client.bootstrap_slack_env")
    def test_resolve_bot_token_missing(self, mock_bootstrap):
        config = {"slack": {"botTokenEnv": "SLACK_BOT_TOKEN"}}
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SlackError):
                resolve_bot_token(config)

    @patch("sprintkit.slack_client.bootstrap_slack_env")
    def test_resolve_bot_token_present(self, mock_bootstrap):
        config = {"slack": {"botTokenEnv": "SLACK_BOT_TOKEN"}}
        with patch.dict(os.environ, {"SLACK_BOT_TOKEN": "xoxb-test"}):
            self.assertEqual(resolve_bot_token(config), "xoxb-test")

    def test_resolve_channel_id_from_config(self):
        config = {"slack": {"channelId": "C123"}}
        self.assertEqual(resolve_channel_id("xoxb-test", config), "C123")

    @patch("sprintkit.slack_client._request_slack")
    def test_resolve_channel_id_by_name(self, mock_request):
        mock_request.return_value = {
            "ok": True,
            "channels": [{"id": "C999", "name": "gautam-personal-agent"}],
            "response_metadata": {},
        }
        config = {"slack": {"channel": "gautam-personal-agent"}}
        self.assertEqual(resolve_channel_id("xoxb-test", config), "C999")

    @patch("sprintkit.slack_client._lookup_channel_id_by_list")
    def test_resolve_channel_id_name_fallback_when_list_fails(self, mock_lookup):
        mock_lookup.side_effect = SlackError("Slack HTTP 429: rate limited")
        config = {"slack": {"channel": "gautam-personal-agent"}}
        self.assertEqual(
            resolve_channel_id("xoxb-test", config),
            "#gautam-personal-agent",
        )

    @patch("sprintkit.slack_client._lookup_channel_id_by_list")
    def test_resolve_channel_id_raises_when_fallback_disabled(self, mock_lookup):
        mock_lookup.side_effect = SlackError("Slack HTTP 429: rate limited")
        config = {"slack": {"channel": "gautam-personal-agent"}}
        with self.assertRaises(SlackError):
            resolve_channel_id("xoxb-test", config, allow_name_fallback=False)

    @patch("sprintkit.slack_client.post_message")
    @patch("sprintkit.slack_client.resolve_channel_id")
    @patch("sprintkit.slack_client.resolve_bot_token")
    @patch("sprintkit.slack_client._chat_permalink")
    def test_post_epic_estimation(self, mock_permalink, mock_token, mock_channel, mock_post):
        mock_token.return_value = "xoxb-test"
        mock_channel.return_value = "C999"
        mock_post.return_value = {"ok": True, "ts": "1234.5678"}
        mock_permalink.return_value = "https://slack.example/archives/C999/p12345678"

        canvas = _sample_canvas()
        result = post_epic_estimation(canvas, MINIMAL_CONFIG)

        self.assertTrue(result["posted"])
        self.assertEqual(result["channelId"], "C999")
        self.assertEqual(result["permalink"], "https://slack.example/archives/C999/p12345678")
        mock_post.assert_called()
        call_kwargs = mock_post.call_args.kwargs
        self.assertIn("blocks", call_kwargs)
        self.assertGreater(len(call_kwargs["blocks"]), 0)

    @patch("sprintkit.slack_client.post_message")
    @patch("sprintkit.slack_client.resolve_channel_id")
    @patch("sprintkit.slack_client.resolve_bot_token")
    @patch("sprintkit.slack_client._chat_permalink")
    def test_post_epic_estimation_invalid_blocks_fallback(
        self, mock_permalink, mock_token, mock_channel, mock_post
    ):
        mock_token.return_value = "xoxb-test"
        mock_channel.return_value = "C999"
        mock_permalink.return_value = None
        mock_post.side_effect = [
            SlackError("Slack API error: invalid_blocks"),
            {"ok": True, "ts": "1234.5678"},
        ]

        canvas = _sample_canvas()
        result = post_epic_estimation(canvas, MINIMAL_CONFIG)
        self.assertTrue(result["posted"])
        self.assertTrue(result["fallbackUsed"])
        self.assertEqual(mock_post.call_count, 2)


if __name__ == "__main__":
    unittest.main()
