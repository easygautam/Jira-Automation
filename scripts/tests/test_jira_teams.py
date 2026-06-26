"""Tests for pipe-prefix team detection."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from sprintkit.config import (  # noqa: E402
    DEFAULT_TEAM_DELIVERY_PLATFORM,
    DEFAULT_TEAM_FIELD_MAPPING,
    DEFAULT_TEAM_FIELD_UAT_VALUES,
)
from sprintkit.stages import STAGE_DEVELOPMENT, STAGE_UAT, classify_issue  # noqa: E402
from sprintkit.teams import (  # noqa: E402
    TEAM_OTHER,
    delivery_platform,
    team_from_first_prefix,
    team_from_issue,
)
from sprintkit.timeline import member_side_for_classification  # noqa: E402


def _issue(
    summary: str,
    issuetype: str = "Task",
    teams_field: str | None = None,
) -> dict:
    fields: dict = {
        "summary": summary,
        "issuetype": {"name": issuetype},
        "labels": [],
        "components": [],
    }
    if teams_field is not None:
        fields["customfield_10218"] = {"value": teams_field}
    return {"key": "VP-1", "fields": fields}


CONFIG = {
    "teams": {"qa": ["qa"], "mobile": ["mobile", "app"]},
    "fields": {"teams": "customfield_10218"},
    "teamFieldMapping": dict(DEFAULT_TEAM_FIELD_MAPPING),
    "teamDeliveryPlatform": dict(DEFAULT_TEAM_DELIVERY_PLATFORM),
    "teamFieldUatValues": list(DEFAULT_TEAM_FIELD_UAT_VALUES),
    "teamPrefixMapping": {
        "qa": {"aliases": ["qa"]},
        "data_engineering": {"aliases": ["ds", "de"]},
        "backend": {"aliases": ["be", "backend", "api", "dag", "ppadmin", "admin"]},
        "frontend": {"aliases": ["web", "website", "frontend", "frontent", "fe"]},
        "mobile": {"aliases": ["mobile", "app", "android", "ios"]},
    },
    "timeline": {
        "leaveTaskPrefixes": {"planned": "Leave | Planned", "unplanned": "Leave | Unplanned"},
        "sideDisplay": {
            "backend": "Backend",
            "frontend": "Web",
            "mobile": "Mobile",
            "data_engineering": "Data Engineering",
            "devops": "DevOps",
            "product_design": "Product + Design",
            "qa": "QA",
            "other": "Other",
        },
        "defaultTaskByTeam": {
            "backend": "Development",
            "frontend": "Development",
            "mobile": "Development",
        },
        "executionStages": {
            "backend": ["Development", "Stage testing"],
            "frontend": ["Development", "Stage testing"],
            "mobile": ["Development", "Stage testing"],
        },
    },
}


class TestPipePrefix(unittest.TestCase):
    def test_qa_before_app(self):
        self.assertEqual(
            team_from_first_prefix("QA | APP | EVENTS PRD — 2nd iteration"),
            "qa",
        )
        issue = _issue("QA | APP | EVENTS PRD — 2nd iteration (registration funnel)")
        self.assertEqual(team_from_issue(issue, CONFIG["teams"], CONFIG), "qa")

    def test_be_first(self):
        self.assertEqual(team_from_first_prefix("BE || Add endpoint"), "backend")

    def test_app_first(self):
        self.assertEqual(team_from_first_prefix("APP | Stage | icon"), "mobile")

    def test_android_is_mobile(self):
        self.assertEqual(team_from_first_prefix("Android | Stage | icon"), "mobile")

    def test_ppadmin_is_backend(self):
        self.assertEqual(team_from_first_prefix("PPAdmin || Create operation"), "backend")

    def test_dag_and_api_are_backend(self):
        self.assertEqual(team_from_first_prefix("DAG | flow test"), "backend")
        self.assertEqual(team_from_first_prefix("API | contract review"), "backend")

    def test_website_and_fe_are_web(self):
        self.assertEqual(team_from_first_prefix("Website | landing"), "frontend")
        self.assertEqual(team_from_first_prefix("FE | component"), "frontend")

    def test_unmatched_prefix_is_other(self):
        self.assertIsNone(team_from_first_prefix("Stage | FOMO message"))
        issue = _issue("Stage | Past Time Slots Displayed")
        self.assertEqual(team_from_issue(issue, CONFIG["teams"], CONFIG), TEAM_OTHER)
        self.assertEqual(
            team_from_issue(_issue("Enhancement: Need to check"), CONFIG["teams"], CONFIG),
            TEAM_OTHER,
        )

    def test_mixed_case_prefixes(self):
        cases = [
            ("be | Enhancement: foo", "backend"),
            ("BE | Enhancement: foo", "backend"),
            ("Qa | APP | work", "qa"),
            ("web | UI change", "frontend"),
            ("WEB | UI change", "frontend"),
            ("aNdRoId | Stage", "mobile"),
            ("iOS | build", "mobile"),
            ("PpAdmin | op", "backend"),
            ("Api | endpoint", "backend"),
        ]
        for summary, expected in cases:
            with self.subTest(summary=summary):
                self.assertEqual(
                    team_from_first_prefix(summary),
                    expected,
                    msg=summary,
                )

    def test_be_pipe_enhancement_maps_to_be_development(self):
        issue = _issue(
            "BE | Enhancement: Need to check the center ids and fomo cuttoff value while uploading"
        )
        result = classify_issue(issue, CONFIG["timeline"], CONFIG["teams"], CONFIG)
        self.assertEqual(result["kind"], "work")
        self.assertEqual(result["team"], "backend")
        self.assertEqual(result["stage"], "Development")

    def test_qa_classified_as_qa_work_not_mobile(self):
        issue = _issue(
            "QA | APP | EVENTS PRD — 2nd iteration (registration funnel)",
            "Test Execution",
        )
        result = classify_issue(issue, CONFIG["timeline"], CONFIG["teams"], CONFIG)
        self.assertEqual(result["team"], "qa")
        self.assertEqual(result["stage"], "Stage testing")
        self.assertEqual(result["platform"], "mobile")

    def test_qa_assessment_without_platform_additional_effort(self):
        issue = _issue("QA | Assessment")
        result = classify_issue(issue, CONFIG["timeline"], CONFIG["teams"], CONFIG)
        self.assertEqual(result["kind"], "additional_effort")
        self.assertEqual(result["team"], "qa")


class TestTeamsFieldFallback(unittest.TestCase):
    def test_title_wins_over_teams_field(self):
        issue = _issue("BE | work", teams_field="Web")
        self.assertEqual(team_from_issue(issue, CONFIG["teams"], CONFIG), "backend")

    def test_field_backend_when_prefix_unmatched(self):
        issue = _issue("Stage | foo", teams_field="Backend")
        self.assertEqual(team_from_issue(issue, CONFIG["teams"], CONFIG), "backend")
        result = classify_issue(issue, CONFIG["timeline"], CONFIG["teams"], CONFIG)
        self.assertEqual(result["kind"], "work")
        self.assertEqual(result["platform"], "backend")
        self.assertEqual(result["stage"], STAGE_DEVELOPMENT)

    def test_android_field_no_prefix(self):
        issue = _issue("Scholarship web view fixes", teams_field="Android")
        self.assertEqual(team_from_issue(issue, CONFIG["teams"], CONFIG), "mobile")
        result = classify_issue(issue, CONFIG["timeline"], CONFIG["teams"], CONFIG)
        self.assertEqual(result["platform"], "mobile")
        self.assertEqual(result["stage"], STAGE_DEVELOPMENT)

    def test_kmm_field_maps_mobile(self):
        issue = _issue("Shared module work", teams_field="KMM")
        self.assertEqual(team_from_issue(issue, CONFIG["teams"], CONFIG), "mobile")

    def test_data_engineering_separate_team_backend_delivery(self):
        issue = _issue("Pipeline job", teams_field="Data Engineering")
        self.assertEqual(team_from_issue(issue, CONFIG["teams"], CONFIG), "data_engineering")
        self.assertEqual(delivery_platform("data_engineering", CONFIG), "backend")
        result = classify_issue(issue, CONFIG["timeline"], CONFIG["teams"], CONFIG)
        self.assertEqual(result["kind"], "work")
        self.assertEqual(result["team"], "data_engineering")
        self.assertEqual(result["platform"], "backend")
        self.assertEqual(result["stage"], STAGE_DEVELOPMENT)
        side = member_side_for_classification(
            result, CONFIG["timeline"]["sideDisplay"]
        )
        self.assertEqual(side, "Data Engineering")

    def test_devops_separate_team_backend_delivery(self):
        issue = _issue("Deploy config", teams_field="DevOps")
        result = classify_issue(issue, CONFIG["timeline"], CONFIG["teams"], CONFIG)
        self.assertEqual(result["team"], "devops")
        self.assertEqual(result["platform"], "backend")
        self.assertEqual(result["stage"], STAGE_DEVELOPMENT)
        side = member_side_for_classification(
            result, CONFIG["timeline"]["sideDisplay"]
        )
        self.assertEqual(side, "DevOps")

    def test_product_field_uat(self):
        issue = _issue("UAT | SEO", teams_field="Product")
        result = classify_issue(issue, CONFIG["timeline"], CONFIG["teams"], CONFIG)
        self.assertEqual(result["kind"], "work")
        self.assertEqual(result["stage"], STAGE_UAT)
        self.assertEqual(result["team"], "product_design")

    def test_analytics_field_uat(self):
        issue = _issue("Dashboard review", teams_field="Analytics")
        result = classify_issue(issue, CONFIG["timeline"], CONFIG["teams"], CONFIG)
        self.assertEqual(result["stage"], STAGE_UAT)
        self.assertEqual(result["team"], "product_design")

    def test_qa_field_without_platform_additional_effort(self):
        issue = _issue("TC-040: Verify fallback", teams_field="QA")
        self.assertEqual(team_from_issue(issue, CONFIG["teams"], CONFIG), "qa")
        result = classify_issue(issue, CONFIG["timeline"], CONFIG["teams"], CONFIG)
        self.assertEqual(result["kind"], "additional_effort")

    def test_other_teams_field_unmapped(self):
        issue = _issue("Misc work", teams_field="Other Teams")
        self.assertEqual(team_from_issue(issue, CONFIG["teams"], CONFIG), TEAM_OTHER)
        result = classify_issue(issue, CONFIG["timeline"], CONFIG["teams"], CONFIG)
        self.assertEqual(result["kind"], "unmapped")

    def test_ds_prefix_data_engineering(self):
        self.assertEqual(team_from_first_prefix("DS | Assessment | BYOC"), "data_engineering")
        self.assertEqual(team_from_first_prefix("DE | pipeline work"), "data_engineering")

    def test_ds_assessment_tech_solutioning_backend_delivery(self):
        issue = _issue("DS | Assessment | BYOC | PDF input + scaling planning")
        self.assertEqual(team_from_issue(issue, CONFIG["teams"], CONFIG), "data_engineering")
        result = classify_issue(issue, CONFIG["timeline"], CONFIG["teams"], CONFIG)
        self.assertEqual(result["kind"], "work")
        self.assertEqual(result["team"], "data_engineering")
        self.assertEqual(result["platform"], "backend")
        self.assertEqual(result["stage"], "Tech Solutioning")
        side = member_side_for_classification(
            result, CONFIG["timeline"]["sideDisplay"]
        )
        self.assertEqual(side, "Data Engineering")

    def test_de_prefix_development(self):
        issue = _issue("DE | Enhancement: ETL job")
        result = classify_issue(issue, CONFIG["timeline"], CONFIG["teams"], CONFIG)
        self.assertEqual(result["team"], "data_engineering")
        self.assertEqual(result["platform"], "backend")
        self.assertEqual(result["stage"], STAGE_DEVELOPMENT)


if __name__ == "__main__":
    unittest.main()
