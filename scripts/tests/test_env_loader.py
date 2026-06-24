"""Tests for env file loading (local + cloud-compatible)."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from sprintkit.env_loader import load_env_files, parse_env_file  # noqa: E402


class TestEnvLoader(unittest.TestCase):
    def test_parse_env_file(self):
        text = """
# comment
SLACK_BOT_TOKEN=xoxb-test
export SLACK_CHANNEL_ID="C123"
"""
        parsed = parse_env_file(text)
        self.assertEqual(parsed["SLACK_BOT_TOKEN"], "xoxb-test")
        self.assertEqual(parsed["SLACK_CHANNEL_ID"], "C123")

    def test_load_env_files_does_not_override_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env.local").write_text("SLACK_BOT_TOKEN=from-file\n", encoding="utf-8")
            with patch_environ({"SLACK_BOT_TOKEN": "from-process"}):
                load_env_files({"slack": {"envFiles": [".env.local"]}}, repo_root=root)
                self.assertEqual(os.environ.get("SLACK_BOT_TOKEN"), "from-process")

    def test_load_env_files_sets_missing_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env").write_text("SLACK_BOT_TOKEN=from-file\n", encoding="utf-8")
            key = "SLACK_BOT_TOKEN"
            old = os.environ.pop(key, None)
            try:
                load_env_files({"slack": {"envFiles": [".env"]}}, repo_root=root)
                self.assertEqual(os.environ.get("SLACK_BOT_TOKEN"), "from-file")
            finally:
                if old is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = old


class patch_environ:
    """Temporarily replace os.environ for a block."""

    def __init__(self, values: dict[str, str]):
        self._values = values
        self._saved: dict[str, str | None] = {}

    def __enter__(self):
        for key in self._values:
            self._saved[key] = os.environ.get(key)
        os.environ.update(self._values)
        return self

    def __exit__(self, *args):
        for key, old in self._saved.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old


if __name__ == "__main__":
    unittest.main()
