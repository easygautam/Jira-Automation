"""Tests for report date formatting (DD-MM-YYYY)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from sprintkit.render.markdown import fmt_date, fmt_date_range  # noqa: E402


class TestFmtDate(unittest.TestCase):
    def test_iso_date(self):
        self.assertEqual(fmt_date("2026-06-10"), "10-06-2026")

    def test_iso_datetime(self):
        self.assertEqual(fmt_date("2026-06-10T12:00:00Z"), "10-06-2026")

    def test_none_and_empty(self):
        self.assertEqual(fmt_date(None), "—")
        self.assertEqual(fmt_date(""), "—")

    def test_invalid_passthrough(self):
        self.assertEqual(fmt_date("not-a-date"), "not-a-date")

    def test_date_range(self):
        self.assertEqual(
            fmt_date_range("2026-06-01", "2026-06-12"),
            "01-06-2026 → 12-06-2026",
        )

    def test_date_range_missing(self):
        self.assertEqual(fmt_date_range(None, "2026-06-12"), "—")
        self.assertEqual(fmt_date_range("2026-06-01", None), "—")


if __name__ == "__main__":
    unittest.main()
