#!/usr/bin/env python3
"""Extract active sprint window from Jira issue sprint field."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore


def load_config(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        return yaml.safe_load(text) or {}
    return {}


def parse_date(value: str | None) -> str | None:
    if not value:
        return None
    return value[:10]


def sprint_field_value(fields: dict[str, Any], field_id: str) -> list[dict[str, Any]]:
    raw = fields.get(field_id)
    if raw is None and field_id.startswith("customfield_"):
        raw = fields.get("sprint")
    if raw is None:
        return []
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if isinstance(raw, dict):
        return [raw]
    return []


def extract_active_sprint(
    issues: list[dict[str, Any]],
    sprint_field: str,
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for issue in issues:
        fields = issue.get("fields") or {}
        for sprint in sprint_field_value(fields, sprint_field):
            candidates.append(sprint)

    if not candidates:
        raise ValueError(
            f"No sprint data found in field '{sprint_field}'. "
            "Re-fetch issues including the Sprint field or run field discovery."
        )

    active = [s for s in candidates if (s.get("state") or "").lower() == "active"]
    pool = active if active else candidates

    def sort_key(s: dict[str, Any]) -> str:
        return s.get("startDate") or s.get("endDate") or ""

    chosen = max(pool, key=sort_key)
    start = parse_date(chosen.get("startDate"))
    end = parse_date(chosen.get("endDate"))

    if not start or not end:
        raise ValueError(
            f"Sprint '{chosen.get('name')}' missing startDate/endDate in field '{sprint_field}'."
        )

    return {
        "sprintId": chosen.get("id"),
        "sprintName": chosen.get("name"),
        "sprintStart": start,
        "sprintEnd": end,
        "state": chosen.get("state", "active"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract active sprint metadata from Jira issues")
    parser.add_argument("--config", default=".cursor/config/em-config.yaml")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", help="Write JSON; default stdout")
    parser.add_argument("--sprint-field", help="Override config fields.sprint")
    args = parser.parse_args()

    config = load_config(Path(args.config))
    fields_cfg = config.get("fields") or {}
    sprint_field = args.sprint_field or fields_cfg.get("sprint") or "customfield_10020"

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    issues = payload if isinstance(payload, list) else payload.get("issues", payload)

    try:
        meta = extract_active_sprint(issues, sprint_field)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    out = json.dumps(meta, indent=2)
    if args.output:
        Path(args.output).write_text(out + "\n", encoding="utf-8")
    else:
        sys.stdout.write(out + "\n")


if __name__ == "__main__":
    main()
