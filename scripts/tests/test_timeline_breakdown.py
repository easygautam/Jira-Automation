"""Tests for timeline_breakdown.py."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from sprintkit.stages import (  # noqa: E402
    STAGE_DEVELOPMENT,
    STAGE_PROD_FINAL_TESTING,
    STAGE_QA_TEST_PLANNING,
    STAGE_STAGE_TESTING,
    STAGE_TECH_SOLUTIONING,
    STAGE_UAT,
    TEAM_PRODUCT_DESIGN,
    classify_issue,
)
from sprintkit.timeline import build_timeline_breakdown, calc_days, format_calc_days  # noqa: E402


def _issue(
    key: str,
    summary: str,
    estimate_seconds: int = 0,
    parent_key: str | None = None,
    issuetype: str = "Task",
    assignee: str | None = "Alice",
) -> dict:
    fields: dict = {
        "summary": summary,
        "timeoriginalestimate": estimate_seconds,
        "issuetype": {"name": issuetype},
        "labels": [],
        "components": [],
    }
    if assignee:
        fields["assignee"] = {"displayName": assignee, "accountId": assignee}
    if parent_key:
        fields["parent"] = {
            "key": parent_key,
            "fields": {"issuetype": {"name": "Epic"}, "summary": "Test Epic"},
        }
    return {"key": key, "fields": fields}


def _epic(key: str, summary: str = "Events phase 1") -> dict:
    return {
        "key": key,
        "fields": {
            "summary": summary,
            "issuetype": {"name": "Epic", "hierarchyLevel": 1},
            "timeoriginalestimate": 0,
        },
    }


MINIMAL_CONFIG = {
    "teams": {
        "backend": ["backend", "be"],
        "frontend": ["frontend", "web"],
        "mobile": ["mobile", "android", "app"],
        "qa": ["qa", "test"],
    },
    "teamPrefixMapping": {
        "qa": {"aliases": ["qa"]},
        "backend": {"aliases": ["be", "backend"]},
        "frontend": {"aliases": ["web", "frontend"]},
        "mobile": {"aliases": ["app", "mobile", "android"]},
    },
    "timeline": {
        "hoursPerDay": 6,
        "effortBuffers": {
            "bugFixesPercentOfDevelopment": 0.10,
            "stageFinalTestingPercentOfStageTesting": 0.10,
        },
        "leaveTaskPrefixes": {
            "planned": "Leave | Planned",
            "unplanned": "Leave | Unplanned",
        },
        "sideDisplay": {
            "backend": "Backend",
            "frontend": "Web",
            "mobile": "Mobile",
            "product_design": "Product + Design",
            "qa": "QA",
            "unknown": "Other",
        },
        "defaultTaskByTeam": {
            "backend": "Development",
            "frontend": "Development",
            "mobile": "Development",
        },
        "executionStages": {
            "backend": [
                "Tech Solutioning",
                "QA Test Planning",
                "Development",
                "Stage testing",
                "Bug fixes",
                "Stage final testing",
                "Prod release",
                "Prod final testing",
                "Go live date",
            ],
            "frontend": [
                "Tech Solutioning",
                "QA Test Planning",
                "Development",
                "Stage testing",
                "Bug fixes",
                "Stage final testing",
                "Pre-Prod testing",
                "UAT",
                "Go live date",
            ],
            "mobile": [
                "Tech Solutioning",
                "QA Test Planning",
                "Development",
                "Stage testing",
                "Bug fixes",
                "Stage final testing",
                "Pre-Prod testing",
                "UAT",
                "Go live date",
            ],
        },
    },
}


def _stage_row(epic_row: dict, platform: str, stage: str) -> dict:
    block = epic_row["executionStages"][platform]
    return next(r for r in block["stages"] if r["stage"] == stage)


class TestCalcDays(unittest.TestCase):
    def test_six_hour_day_decimal(self):
        self.assertEqual(calc_days(12, 6, 0, 2, 6), 1.5)

    def test_three_hours_half_day(self):
        self.assertEqual(calc_days(3, 0, 0, 1, 6), 0.5)

    def test_development_with_leave(self):
        self.assertEqual(calc_days(14, 12, 0, 1, 6), 4.33)

    def test_no_resources(self):
        self.assertIsNone(calc_days(10, 0, 0, 0, 6))


class TestFormatCalcDays(unittest.TestCase):
    def test_half_day(self):
        self.assertEqual(format_calc_days(0.5), "0.5")

    def test_decimal_trim(self):
        self.assertEqual(format_calc_days(4.33), "4.33")

    def test_whole_day(self):
        self.assertEqual(format_calc_days(2.0), "2")


class TestClassifyIssue(unittest.TestCase):
    def test_planned_leave(self):
        issue = _issue("VP-1", "Leave | Planned - doctor", 7200)
        cfg = MINIMAL_CONFIG["timeline"]
        result = classify_issue(issue, cfg, MINIMAL_CONFIG["teams"], MINIMAL_CONFIG)
        self.assertEqual(result["kind"], "leave")
        self.assertEqual(result["leaveType"], "planned")

    def test_be_assessment_maps_to_tech_solutioning(self):
        issue = _issue("VP-2", "BE | Assessment", 3600)
        result = classify_issue(
            issue, MINIMAL_CONFIG["timeline"], MINIMAL_CONFIG["teams"], MINIMAL_CONFIG
        )
        self.assertEqual(result["platform"], "backend")
        self.assertEqual(result["stage"], STAGE_TECH_SOLUTIONING)

    def test_be_development_pipe(self):
        issue = _issue("VP-2", "BE || Add endpoint", 14400)
        result = classify_issue(
            issue, MINIMAL_CONFIG["timeline"], MINIMAL_CONFIG["teams"], MINIMAL_CONFIG
        )
        self.assertEqual(result["kind"], "work")
        self.assertEqual(result["stage"], STAGE_DEVELOPMENT)
        self.assertEqual(result["platform"], "backend")

    def test_qa_assessment_without_platform_unmapped(self):
        issue = _issue("VP-3", "QA | Assessment", 7200)
        result = classify_issue(
            issue, MINIMAL_CONFIG["timeline"], MINIMAL_CONFIG["teams"], MINIMAL_CONFIG
        )
        self.assertEqual(result["kind"], "unmapped")
        self.assertEqual(result["team"], "qa")

    def test_qa_app_assessment_test_planning(self):
        issue = _issue("VP-3a", "QA | App | Assessment / Test Planning", 7200)
        result = classify_issue(
            issue, MINIMAL_CONFIG["timeline"], MINIMAL_CONFIG["teams"], MINIMAL_CONFIG
        )
        self.assertEqual(result["platform"], "mobile")
        self.assertEqual(result["stage"], STAGE_QA_TEST_PLANNING)

    def test_qa_be_automation_stage_testing(self):
        issue = _issue(
            "VP-3b",
            "QA | BE | Automation | integrate events PRD API automation",
            3600,
        )
        result = classify_issue(
            issue, MINIMAL_CONFIG["timeline"], MINIMAL_CONFIG["teams"], MINIMAL_CONFIG
        )
        self.assertEqual(result["platform"], "backend")
        self.assertEqual(result["stage"], STAGE_STAGE_TESTING)

    def test_qa_web_e2e_default_stage_testing(self):
        issue = _issue("VP-3c", "QA | Web | events PRD e2e", 3600)
        result = classify_issue(
            issue, MINIMAL_CONFIG["timeline"], MINIMAL_CONFIG["teams"], MINIMAL_CONFIG
        )
        self.assertEqual(result["platform"], "frontend")
        self.assertEqual(result["stage"], STAGE_STAGE_TESTING)

    def test_qa_web_stage_testing(self):
        issue = _issue("VP-4", "QA | WEB | 1st iteration (stage testing)", 3600)
        result = classify_issue(
            issue, MINIMAL_CONFIG["timeline"], MINIMAL_CONFIG["teams"], MINIMAL_CONFIG
        )
        self.assertEqual(result["platform"], "frontend")
        self.assertEqual(result["stage"], STAGE_STAGE_TESTING)

    def test_designer_uat_in_title_is_development(self):
        issue = _issue("VP-19936", "Web | UI Pointers Webview - Designer UAT", 21600)
        result = classify_issue(
            issue, MINIMAL_CONFIG["timeline"], MINIMAL_CONFIG["teams"], MINIMAL_CONFIG
        )
        self.assertEqual(result["kind"], "work")
        self.assertEqual(result["platform"], "frontend")
        self.assertEqual(result["stage"], STAGE_DEVELOPMENT)

    def test_web_uat_segment_maps_product_design(self):
        issue = _issue("VP-5", "WEB | UAT | sign-off with product", 3600)
        result = classify_issue(
            issue, MINIMAL_CONFIG["timeline"], MINIMAL_CONFIG["teams"], MINIMAL_CONFIG
        )
        self.assertEqual(result["platform"], "frontend")
        self.assertEqual(result["stage"], STAGE_UAT)
        self.assertEqual(result["team"], TEAM_PRODUCT_DESIGN)

    def test_qa_web_uat_suffix_is_stage_testing(self):
        issue = _issue("VP-6", "QA | WEB | UAT sign-off", 3600)
        result = classify_issue(
            issue, MINIMAL_CONFIG["timeline"], MINIMAL_CONFIG["teams"], MINIMAL_CONFIG
        )
        self.assertEqual(result["platform"], "frontend")
        self.assertEqual(result["stage"], STAGE_STAGE_TESTING)
        self.assertEqual(result["team"], "qa")

    def test_qa_be_final_testing_is_prod_final(self):
        issue = _issue("VP-7", "QA | BE | Final Testing | API validation", 7200)
        result = classify_issue(
            issue, MINIMAL_CONFIG["timeline"], MINIMAL_CONFIG["teams"], MINIMAL_CONFIG
        )
        self.assertEqual(result["platform"], "backend")
        self.assertEqual(result["stage"], STAGE_PROD_FINAL_TESTING)
        self.assertEqual(result["team"], "qa")


class TestBuildTimelineBreakdown(unittest.TestCase):
    def test_epic_aggregation_dates(self):
        epic = _epic("VP-100")
        t1 = _issue("VP-101", "BE || API", 28800, parent_key="VP-100")
        t2 = _issue("VP-102", "WEB || UI", 14400, parent_key="VP-100", assignee="Bob")
        schedule = {
            "scheduled": [
                {"key": "VP-101", "startDate": "2026-06-02", "dueDate": "2026-06-05"},
                {"key": "VP-102", "startDate": "2026-06-03", "dueDate": "2026-06-08"},
            ]
        }
        result = build_timeline_breakdown([epic, t1, t2], schedule, MINIMAL_CONFIG)
        epic_row = result[0]
        self.assertNotIn("deliveryStart", epic_row)
        self.assertNotIn("deliveryEnd", epic_row)
        self.assertNotIn("qaCrossPlatform", epic_row)

        be_row = _stage_row(epic_row, "backend", STAGE_DEVELOPMENT)
        self.assertNotIn("start", be_row)
        self.assertNotIn("end", be_row)
        self.assertEqual(be_row["effortsHours"], 8.0)
        bug_row = _stage_row(epic_row, "backend", "Bug fixes")
        self.assertEqual(bug_row["effortsHours"], 0.8)
        self.assertEqual(bug_row["calculatedDays"], 0.13)
        self.assertEqual(bug_row["resources"], 1.0)
        self.assertEqual(bug_row["source"], "synthetic")

        self.assertTrue(epic_row["executionStages"]["backend"]["hasWork"])
        self.assertTrue(epic_row["executionStages"]["frontend"]["hasWork"])
        self.assertFalse(epic_row["executionStages"]["mobile"]["hasWork"])

    def test_planned_leave_hours_on_side(self):
        epic = _epic("VP-200")
        dev = _issue("VP-201", "BE || work", 3600, parent_key="VP-200")
        leave = _issue("VP-202", "Leave | Planned - holiday", 7200, parent_key="VP-200")
        result = build_timeline_breakdown([epic, dev, leave], {"scheduled": []}, MINIMAL_CONFIG)
        be_row = _stage_row(result[0], "backend", STAGE_DEVELOPMENT)
        self.assertEqual(be_row["plannedLeaveHours"], 2.0)

    def test_web_preprod_separate_from_uat(self):
        epic = _epic("VP-600")
        pre = _issue(
            "VP-601",
            "QA | WEB | Pre-Prod | validation",
            7200,
            parent_key="VP-600",
        )
        uat = _issue("VP-602", "WEB | UAT | sign-off", 3600, parent_key="VP-600")
        result = build_timeline_breakdown([epic, pre, uat], {"scheduled": []}, MINIMAL_CONFIG)[0]
        pre_row = _stage_row(result, "frontend", "Pre-Prod testing")
        uat_row = _stage_row(result, "frontend", "UAT")
        self.assertEqual(pre_row["effortsHours"], 2.0)
        self.assertEqual(uat_row["effortsHours"], 1.0)

    def test_qa_web_prod_testing_is_preprod(self):
        epic = _epic("VP-605")
        task = _issue(
            "VP-606",
            "QA | WEB | Prod testing | regression",
            5400,
            parent_key="VP-605",
        )
        result = build_timeline_breakdown([epic, task], {"scheduled": []}, MINIMAL_CONFIG)[0]
        pre_row = _stage_row(result, "frontend", "Pre-Prod testing")
        stage_row = _stage_row(result, "frontend", STAGE_STAGE_TESTING)
        self.assertEqual(pre_row["effortsHours"], 1.5)
        self.assertIsNone(stage_row["effortsHours"])

    def test_qa_be_final_testing_is_prod_final(self):
        epic = _epic("VP-607")
        task = _issue(
            "VP-608",
            "QA | BE | Final Testing | API validation",
            7200,
            parent_key="VP-607",
        )
        result = build_timeline_breakdown([epic, task], {"scheduled": []}, MINIMAL_CONFIG)[0]
        prod_final = _stage_row(result, "backend", STAGE_PROD_FINAL_TESTING)
        self.assertEqual(prod_final["effortsHours"], 2.0)

    def test_product_design_team_row(self):
        epic = _epic("VP-609")
        uat = _issue(
            "VP-610",
            "WEB | UAT | done with product team",
            3600,
            parent_key="VP-609",
            assignee="Pat",
        )
        result = build_timeline_breakdown([epic, uat], {"scheduled": []}, MINIMAL_CONFIG)[0]
        self.assertIn("Product + Design", result["teamSummary"])
        self.assertEqual(result["teamSummary"]["Product + Design"]["taskCount"], 1)
        self.assertIn("Pat", [m["member"] for m in result["membersBySide"]["Product + Design"]])

    def test_mobile_preprod_not_web(self):
        epic = _epic("VP-601")
        mob = _issue(
            "VP-602",
            "QA | APP | Pre-Prod | regression",
            3600,
            parent_key="VP-601",
        )
        result = build_timeline_breakdown([epic, mob], {"scheduled": []}, MINIMAL_CONFIG)[0]
        mob_row = _stage_row(result, "mobile", "Pre-Prod testing")
        web_row = _stage_row(result, "frontend", "Pre-Prod testing")
        self.assertEqual(mob_row["effortsHours"], 1.0)
        self.assertIsNone(web_row["effortsHours"])

    def test_members_by_side_two_backend(self):
        epic = _epic("VP-300")
        t1 = _issue("VP-301", "BE || API one", 7200, parent_key="VP-300", assignee="Alice")
        t2 = _issue("VP-302", "BE || API two", 10800, parent_key="VP-300", assignee="Bob")
        schedule = {
            "scheduled": [
                {"key": "VP-301", "startDate": "2026-06-01", "dueDate": "2026-06-02"},
                {"key": "VP-302", "startDate": "2026-06-03", "dueDate": "2026-06-05"},
            ]
        }
        result = build_timeline_breakdown([epic, t1, t2], schedule, MINIMAL_CONFIG)
        backend_members = result[0]["membersBySide"]["Backend"]
        self.assertEqual(len(backend_members), 2)
        for member in backend_members:
            self.assertNotIn("start", member)
            self.assertNotIn("end", member)
        self.assertNotIn("Other", result[0]["membersBySide"])

    def test_be_tasks_bucket_backend_with_empty_side_display(self):
        epic = _epic("VP-310")
        task = _issue("VP-311", "BE || work", 3600, parent_key="VP-310", assignee="Alice")
        cfg = dict(MINIMAL_CONFIG)
        cfg["timeline"] = dict(MINIMAL_CONFIG["timeline"])
        cfg["timeline"]["sideDisplay"] = {}
        epic_row = build_timeline_breakdown([epic, task], {"scheduled": []}, cfg)[0]
        self.assertIn("Backend", epic_row["membersBySide"])
        self.assertNotIn("Other", epic_row["membersBySide"])

    def test_qa_test_planning_per_platform_only(self):
        epic = _epic("VP-700")
        qa = _issue("VP-701", "QA | App | Assessment", 9000, parent_key="VP-700")
        result = build_timeline_breakdown([epic, qa], {"scheduled": []}, MINIMAL_CONFIG)[0]
        self.assertNotIn("qaCrossPlatform", result)
        mob_planning = _stage_row(result, "mobile", STAGE_QA_TEST_PLANNING)
        self.assertEqual(mob_planning["effortsHours"], 2.5)
        for plat in ("backend", "frontend"):
            planning = _stage_row(result, plat, STAGE_QA_TEST_PLANNING)
            self.assertIsNone(planning["effortsHours"])

    def test_legacy_qa_assessment_unmapped(self):
        epic = _epic("VP-800")
        qa = _issue("VP-801", "QA | Assessment", 3600, parent_key="VP-800")
        result = build_timeline_breakdown([epic, qa], {"scheduled": []}, MINIMAL_CONFIG)[0]
        self.assertEqual(len(result["unmapped"]), 1)
        self.assertEqual(result["unmapped"][0]["key"], "VP-801")


if __name__ == "__main__":
    unittest.main()
