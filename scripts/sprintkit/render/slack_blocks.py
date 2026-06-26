"""Block Kit payload builders for epic estimation canvas JSON."""

from __future__ import annotations

from datetime import date
from typing import Any

from sprintkit.render.additional_efforts import build_additional_efforts_rows
from sprintkit.render.markdown import fmt_date
from sprintkit.timeline import format_calc_days

MAX_BLOCKS_PER_MESSAGE = 50
MAX_DATA_VISUALIZATION_BLOCKS = 2
CHART_LABEL_MAX = 20
CHART_TITLE_MAX = 50

TEAMS_HEADERS = ["Team", "Peak", "Effort (h)", "Leave (h)", "Tasks"]
STAGE_HEADERS = ["Stage", "Res", "Effort (h)", "Leave (h)", "Max days", "Dates"]
MEMBER_HEADERS = ["Team", "Member", "Effort (h)", "Leave (h)", "Days", "Tasks"]
ADDITIONAL_EFFORTS_HEADERS = ["Team", "Effort (h)", "Details"]


def fmt_display_date(value: str | None) -> str:
    return fmt_date(value)


def fmt_num(value: float | int | None) -> str:
    if value is None:
        return "—"
    return str(value)


def fmt_calc_days(value: float | int | None) -> str:
    return format_calc_days(value)


def delivery_window_caption(start: str | None, end: str | None) -> str | None:
    if not start or not end:
        return None
    try:
        a = date.fromisoformat(start)
        b = date.fromisoformat(end)
    except ValueError:
        return None
    if b < a:
        return None
    days = (b - a).days + 1
    suffix = "" if days == 1 else "s"
    return f"{days} calendar day{suffix} in delivery window"


def platform_delivery_title(platform: str) -> str:
    if platform == "Backend":
        return "Backend Delivery"
    if platform == "Web":
        return "Web Delivery"
    if platform == "Mobile":
        return "App Delivery"
    return f"{platform} Delivery"


def _plain_header(text: str) -> dict[str, Any]:
    return {"type": "header", "text": {"type": "plain_text", "text": text[:150], "emoji": False}}


def _divider() -> dict[str, Any]:
    return {"type": "divider"}


def _section_mrkdwn(text: str) -> dict[str, Any]:
    return {"type": "section", "text": {"type": "mrkdwn", "text": text[:3000]}}


def _context_mrkdwn(text: str) -> dict[str, Any]:
    return {
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": text[:3000]}],
    }


def _raw_text_cell(text: str) -> dict[str, str]:
    return {"type": "raw_text", "text": text[:3000]}


def _raw_number_cell(value: float | int | str | None) -> dict[str, Any]:
    """Format numbers as raw_text — raw_number is rejected by some Slack workspaces."""
    if value is None or value == "—":
        return _raw_text_cell("—")
    return _raw_text_cell(str(value))


def build_table_block(
    headers: list[str],
    rows: list[list[Any]],
    *,
    numeric_columns: set[int] | None = None,
    wrap_columns: set[int] | None = None,
) -> dict[str, Any]:
    """Native Slack table block — https://docs.slack.dev/reference/block-kit/blocks/table-block"""
    numeric_columns = numeric_columns or set()
    wrap_columns = wrap_columns or {0}

    def header_cell(text: str) -> dict[str, Any]:
        return {
            "type": "rich_text",
            "elements": [
                {
                    "type": "rich_text_section",
                    "elements": [
                        {"type": "text", "text": text[:3000], "style": {"bold": True}},
                    ],
                }
            ],
        }

    table_rows: list[list[dict[str, Any]]] = [[header_cell(h) for h in headers]]
    for row in rows:
        cells: list[dict[str, Any]] = []
        for idx, cell in enumerate(row):
            if idx in numeric_columns:
                cells.append(_raw_number_cell(cell))
            else:
                text = "—" if cell is None or cell == "" else str(cell)
                cells.append(_raw_text_cell(text))
        table_rows.append(cells)

    column_settings: list[dict[str, Any]] = []
    for idx in range(len(headers)):
        settings: dict[str, Any] = {}
        if idx in numeric_columns:
            settings["align"] = "right"
        if idx in wrap_columns:
            settings["is_wrapped"] = True
        column_settings.append(settings)

    return {
        "type": "table",
        "column_settings": column_settings,
        "rows": table_rows,
    }


def _field_grid_rows(headers: list[str], rows: list[list[Any]]) -> list[dict[str, Any]]:
    """Fallback table: one section per row, label + value in each field."""
    blocks: list[dict[str, Any]] = []
    for row in rows:
        fields = [
            {
                "type": "mrkdwn",
                "text": f"*{h}*\n{str(v if v is not None and v != '' else '—')}"[:2000],
            }
            for h, v in zip(headers, row)
        ]
        blocks.append({"type": "section", "fields": fields[:10]})
    return blocks


def _append_data_table(
    blocks: list[dict[str, Any]],
    title: str,
    headers: list[str],
    rows: list[list[Any]],
    *,
    numeric_columns: set[int],
    wrap_columns: set[int] | None = None,
    use_native_table: bool,
) -> None:
    if not rows:
        return
    blocks.append(_plain_header(title))
    if use_native_table:
        blocks.append(
            build_table_block(
                headers,
                rows,
                numeric_columns=numeric_columns,
                wrap_columns=wrap_columns or {0},
            )
        )
    else:
        blocks.extend(_field_grid_rows(headers, rows))


def _stage_date_range(stage: dict[str, Any]) -> str:
    start = fmt_display_date(stage.get("start"))
    end = fmt_display_date(stage.get("end"))
    if start == "—" and end == "—":
        return "—"
    return f"{start} → {end}"


def _stage_table_row(stage: dict[str, Any]) -> list[Any]:
    name = stage.get("stage") or "—"
    if stage.get("synthetic"):
        name = f"{name} (est.)"
    return [
        name,
        fmt_num(stage.get("resources")),
        fmt_num(stage.get("effortsHours")),
        fmt_num(stage.get("leaveHours") or None),
        fmt_calc_days(stage.get("calculatedDays")),
        _stage_date_range(stage),
    ]


def _chart_label(text: str) -> str:
    return (text or "—")[:CHART_LABEL_MAX]


def _chart_title(text: str) -> str:
    return text[:CHART_TITLE_MAX]


def _teams_with_tasks(canvas: dict[str, Any]) -> list[dict[str, Any]]:
    """Teams with taskCount > 0 (pie segments require positive values)."""
    rows = []
    for team in canvas.get("teamsPlan") or []:
        count = int(team.get("taskCount") or 0)
        if count > 0:
            rows.append({**team, "taskCount": count})
    return rows[:6]


def _teams_with_effort(canvas: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for team in canvas.get("teamsPlan") or []:
        hours = team.get("totalEffortHours")
        if hours is not None and float(hours) > 0:
            rows.append(team)
    return rows[:6]


def build_team_task_pie_block(canvas: dict[str, Any]) -> dict[str, Any] | None:
    """Pie chart — task count by team (data_visualization block)."""
    teams = _teams_with_tasks(canvas)
    if not teams:
        return None
    return {
        "type": "data_visualization",
        "block_id": "epic-team-task-pie",
        "title": _chart_title("Task distribution by team"),
        "chart": {
            "type": "pie",
            "segments": [
                {
                    "label": _chart_label(team.get("team", "")),
                    "value": team["taskCount"],
                }
                for team in teams
            ],
        },
    }


def build_team_effort_bar_block(canvas: dict[str, Any]) -> dict[str, Any] | None:
    """Bar chart — effort hours by team (data_visualization block)."""
    teams = _teams_with_effort(canvas)
    if not teams:
        return None
    categories = [_chart_label(t.get("team", "")) for t in teams]
    return {
        "type": "data_visualization",
        "block_id": "epic-team-effort-bar",
        "title": _chart_title("Effort by team (hours)"),
        "chart": {
            "type": "bar",
            "axis_config": {
                "categories": categories,
                "x_label": "Team",
                "y_label": "Hours",
            },
            "series": [
                {
                    "name": "Effort",
                    "data": [
                        {
                            "label": _chart_label(t.get("team", "")),
                            "value": float(t.get("totalEffortHours") or 0),
                        }
                        for t in teams
                    ],
                }
            ],
        },
    }


def _team_chart_blocks(canvas: dict[str, Any]) -> list[dict[str, Any]]:
    """Up to two data_visualization blocks (Slack limit per message)."""
    blocks: list[dict[str, Any]] = []
    pie = build_team_task_pie_block(canvas)
    if pie:
        blocks.append(pie)
    if len(blocks) < MAX_DATA_VISUALIZATION_BLOCKS:
        bar = build_team_effort_bar_block(canvas)
        if bar:
            blocks.append(bar)
    return blocks


def _team_insights_blocks(canvas: dict[str, Any]) -> list[dict[str, Any]]:
    """Charts + context caption before the teams plan table."""
    charts = _team_chart_blocks(canvas)
    if not charts:
        return []
    blocks: list[dict[str, Any]] = [_plain_header("Team overview")]
    blocks.extend(charts)
    blocks.append(
        _context_mrkdwn("Pie = mapped tasks per team · Bar = total effort hours")
    )
    blocks.append(_divider())
    return blocks


def _teams_plan_rows(canvas: dict[str, Any]) -> list[list[Any]]:
    return [
        [
            r.get("team"),
            fmt_num(r.get("peakResources")),
            fmt_num(r.get("totalEffortHours")),
            fmt_num(r.get("leaveHours") or None),
            str(r.get("taskCount", 0)),
        ]
        for r in (canvas.get("teamsPlan") or [])
    ]


def _platform_table_blocks(
    canvas: dict[str, Any],
    *,
    use_native_table: bool,
) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for plat in canvas.get("platforms") or []:
        stages = plat.get("stages") or []
        if not stages:
            continue
        rows = [_stage_table_row(s) for s in stages]
        _append_data_table(
            blocks,
            platform_delivery_title(plat.get("platform", "")),
            STAGE_HEADERS,
            rows,
            numeric_columns={1, 2, 3, 4},
            wrap_columns={0, 5},
            use_native_table=use_native_table,
        )
    return blocks


def _member_table_rows(canvas: dict[str, Any]) -> list[list[Any]]:
    return [
        [
            m.get("team"),
            m.get("member") or "—",
            fmt_num(m.get("effortsHours")),
            fmt_num(m.get("leaveHours") if m.get("leaveHours") else None),
            fmt_calc_days(m.get("calculatedDays")),
            ", ".join(m.get("tasks") or []) or "—",
        ]
        for m in (canvas.get("members") or [])
    ]


def _issue_link(site: str, key: str) -> str:
    base = site.rstrip("/")
    if base:
        return f"<{base}/browse/{key}|{key}>"
    return key


def _hero_blocks(canvas: dict[str, Any]) -> list[dict[str, Any]]:
    epic_key = canvas.get("epicKey", "")
    epic_url = canvas.get("epicUrl") or ""
    prd_name = canvas.get("prdName") or ""
    delivery_start = canvas.get("deliveryStart")
    go_live = canvas.get("goLive")
    unmapped = canvas.get("unmapped") or []

    epic_line = f"<{epic_url}|*{epic_key}*>" if epic_url else f"*{epic_key}*"
    blocks: list[dict[str, Any]] = [
        _plain_header("Epic estimation"),
        _section_mrkdwn(f"{epic_line}\n{prd_name}"),
        _divider(),
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*DELIVERY START*\n{fmt_display_date(delivery_start)}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*DELIVERY END*\n{fmt_display_date(go_live)}",
                },
            ],
        },
    ]

    caption = delivery_window_caption(delivery_start, go_live)
    if caption:
        blocks.append(_context_mrkdwn(caption))

    if unmapped:
        blocks.append(
            _section_mrkdwn(f":warning: *Additional efforts:* {len(unmapped)} task(s)")
        )
    return blocks


def _additional_efforts_table_rows(canvas: dict[str, Any]) -> list[list[str]]:
    site = canvas.get("jiraSiteUrl") or ""

    def _slack_keys(site_url: str | None, keys: list[str] | None) -> str:
        if not keys:
            return "—"
        return ", ".join(_issue_link(site_url or "", k) for k in keys)

    rows_data = canvas.get("additionalEfforts")
    if rows_data is None:
        rows_data = build_additional_efforts_rows(
            canvas.get("unmapped") or [],
            jira_site_url=site or None,
            link_keys=_slack_keys,
        )
    return [
        [row["team"], fmt_num(row.get("effortHours")), row.get("details") or "—"]
        for row in rows_data
    ]


def _additional_efforts_blocks(
    canvas: dict[str, Any], *, use_native_table: bool
) -> list[dict[str, Any]]:
    rows = _additional_efforts_table_rows(canvas)
    if not rows:
        return []
    blocks: list[dict[str, Any]] = []
    _append_data_table(
        blocks,
        "Additional efforts",
        ADDITIONAL_EFFORTS_HEADERS,
        rows,
        numeric_columns={1},
        wrap_columns={0, 2},
        use_native_table=use_native_table,
    )
    return blocks


def _data_quality_blocks(canvas: dict[str, Any]) -> list[dict[str, Any]]:
    dq = canvas.get("dataQuality") or []
    if not dq:
        return []
    site = canvas.get("jiraSiteUrl") or ""
    lines = [
        f"• {row.get('member')} · {_issue_link(site, row.get('key', ''))} · {row.get('reason')}"
        for row in dq
    ]
    return [_plain_header("Data quality"), _section_mrkdwn("\n".join(lines))]


def _build_body_blocks(canvas: dict[str, Any], *, use_native_table: bool) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    blocks.extend(_team_insights_blocks(canvas))
    teams_rows = _teams_plan_rows(canvas)
    _append_data_table(
        blocks,
        "Teams plan",
        TEAMS_HEADERS,
        teams_rows,
        numeric_columns={1, 2, 3, 4},
        wrap_columns={0},
        use_native_table=use_native_table,
    )
    blocks.extend(_platform_table_blocks(canvas, use_native_table=use_native_table))
    member_rows = _member_table_rows(canvas)
    _append_data_table(
        blocks,
        "Member breakdown",
        MEMBER_HEADERS,
        member_rows,
        numeric_columns={2, 3, 4},
        wrap_columns={0, 1, 5},
        use_native_table=use_native_table,
    )
    blocks.extend(_additional_efforts_blocks(canvas, use_native_table=use_native_table))
    blocks.extend(_data_quality_blocks(canvas))
    return blocks


def _split_blocks(blocks: list[dict[str, Any]], limit: int = MAX_BLOCKS_PER_MESSAGE) -> list[list[dict[str, Any]]]:
    if len(blocks) <= limit:
        return [blocks]
    chunks: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for block in blocks:
        if len(current) >= limit:
            chunks.append(current)
            current = []
        current.append(block)
    if current:
        chunks.append(current)
    return chunks


def build_slack_blocks(canvas: dict[str, Any]) -> dict[str, Any]:
    """Block Kit with native table blocks (Slack table block, Aug 2025+)."""
    epic_key = canvas.get("epicKey", "Epic")
    blocks: list[dict[str, Any]] = []
    blocks.extend(_hero_blocks(canvas))
    blocks.append(_divider())
    blocks.extend(_build_body_blocks(canvas, use_native_table=True))

    text = f"Epic estimation — {epic_key}"
    message_chunks = _split_blocks(blocks)
    return {
        "text": text,
        "blocks": message_chunks[0],
        "thread_blocks": message_chunks[1:],
    }


def build_slack_blocks_fallback(canvas: dict[str, Any]) -> dict[str, Any]:
    """Block Kit fallback: labeled field-grid sections when table blocks are rejected."""
    epic_key = canvas.get("epicKey", "Epic")
    blocks: list[dict[str, Any]] = []
    blocks.extend(_hero_blocks(canvas))
    blocks.append(_divider())
    blocks.extend(_build_body_blocks(canvas, use_native_table=False))

    text = f"Epic estimation — {epic_key}"
    message_chunks = _split_blocks(blocks)
    return {
        "text": text,
        "blocks": message_chunks[0],
        "thread_blocks": message_chunks[1:],
    }
